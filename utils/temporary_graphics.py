"""临时画质：只修改可验证的自定义模型，先备份，再写注册表。

注册表不是游戏内的实时设置接口。启动加载后即恢复持久配置，任务结束再
检查一次；崩溃留下的备份由下次助手启动/GUI 子进程结束时恢复。
本模块导入时不读取注册表，测试可注入内存后端。
"""
import atexit
import base64
import json
import os
import sys
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

import psutil


REGISTRY_PATHS = {
    ("miHoYo", "崩坏：星穹铁道"): r"SOFTWARE\miHoYo\崩坏：星穹铁道",
    ("Cognosphere", "Star Rail"): r"SOFTWARE\Cognosphere\Star Rail",
}
MODEL = "GraphicsSettings_Model_h2986158309"
QUALITY = "GraphicsSettings_GraphicsQuality_h523255858"
VERSION = "GraphicsSettings_Version_h3593268432"
AB_TEST = "App_Settings_h2319593470"

# 数值来自游戏的 Quality 枚举；阴影/角色的低档为 2，其余为 1。
# 不修改 FPS、RenderScale、ResolutionQuality、抗锯齿、DLSS 或色彩相关设置。
# https://github.com/CollapseLauncher/Collapse/blob/main/CollapseLauncher/Classes/GameManagement/GameSettings/StarRail/RegistryClass/Model.cs
LOW_QUALITY = {"ShadowQuality": 2, "LightQuality": 1, "CharacterQuality": 2,
               "EnvDetailQuality": 1, "ReflectionQuality": 1, "SFXQuality": 1}


class UnsupportedGraphics(ValueError):
    """未知/不兼容格式：跳过优化，绝不猜测后写入。"""


def decode_model(value):
    if not isinstance(value, bytes) or not 0 < len(value) <= 65536:
        raise UnsupportedGraphics("画质数据不是有效的二进制 JSON")
    data = json.loads(value.rstrip(b"\0").decode("utf-8"))
    if not isinstance(data, dict):
        raise UnsupportedGraphics("画质数据不是 JSON 对象")
    return data


def lower_graphics(value):
    """保留未知字段，只降低已知档位；返回完整 JSON，不能套用游戏低画质预设。"""
    data = decode_model(value)
    if (type(data.get("FPS")) is not int or data["FPS"] <= 0
            or type(data.get("RenderScale")) not in (int, float)
            or not 0 < data["RenderScale"] <= 2):
        raise UnsupportedGraphics("缺少有效的帧率或渲染比例，请先在游戏内保存自定义画质")
    for field, target in LOW_QUALITY.items():
        current = data.get(field)
        if type(current) is not int or current not in range(6):
            raise UnsupportedGraphics(f"不支持的画质字段：{field}")
        data[field] = min(current, target)
    if data == decode_model(value):
        return value
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\0"


class WindowsGraphicsRegistry:
    def __init__(self):
        import winreg
        self.reg = winreg

    def path_for_game(self, game_path):
        # Unity 自带的公司/产品名称对应 HKCU 路径，不使用“优先找到国服”的全局缓存。
        if Path(game_path).name.lower() != "starrail.exe":
            raise UnsupportedGraphics("游戏主程序不是 StarRail.exe")
        info = Path(game_path).parent / "StarRail_Data" / "app.info"
        names = info.read_text(encoding="utf-8-sig").strip().splitlines()
        path = REGISTRY_PATHS.get(tuple(line.strip() for line in names))
        if path is None:
            raise UnsupportedGraphics("无法根据游戏安装目录确认注册表区域")
        return path

    def read(self, path, name):
        try:
            with self.reg.OpenKey(self.reg.HKEY_CURRENT_USER, path) as key:
                return self.reg.QueryValueEx(key, name)
        except FileNotFoundError:
            return None

    def write_model(self, path, value):
        # 只打开已存在的游戏项；不创建未知项，不写账号或其它设置。
        with self.reg.OpenKey(self.reg.HKEY_CURRENT_USER, path, 0, self.reg.KEY_SET_VALUE) as key:
            self.reg.SetValueEx(key, MODEL, 0, self.reg.REG_BINARY, value)
            self.reg.FlushKey(key)

    def game_running(self):
        for process in psutil.process_iter(["name"]):
            try:
                if (process.info["name"] or "").lower() == "starrail.exe":
                    return True
            except psutil.NoSuchProcess:
                continue
        return False


def backup_exists(path):
    # Python 3.14 的 Path.exists() 会把访问失败也视为不存在，不能据此覆盖旧备份。
    try:
        path.stat()
        return True
    except FileNotFoundError:
        return False


def backup_path():
    # 同一 Windows 用户的多个助手安装共用备份，避免 --force/不同目录互相覆盖。
    return Path(os.environ.get("LOCALAPPDATA", "settings")) / "March7thAssistant" / "temporary-graphics.json"


@contextmanager
def journal_lock(path):
    """短时文件锁。进程被强杀后 OS 自动释放，不删除锁文件以避免 inode 竞争。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if sys.platform == "win32":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def owner_alive(record):
    try:
        return psutil.Process(record["pid"]).create_time() == record["created"]
    except psutil.NoSuchProcess:
        return False
    except psutil.AccessDenied:
        return True  # 无法确认时，不动其它进程正在使用的配置。


class GraphicsSession:
    def __init__(self, registry, path, logger):
        self.registry, self.path, self.log = registry, Path(path), logger
        self.owner = {"pid": os.getpid(), "created": psutil.Process().create_time()}
        self.active = False

    def _read_backup(self):
        record = json.loads(self.path.read_text(encoding="utf-8"))
        if (record.get("schema") != 1 or record.get("registry") not in REGISTRY_PATHS.values()
                or type(record.get("completed", False)) is not bool
                or type(record.get("pid")) is not int or record["pid"] <= 0
                or type(record.get("created")) not in (int, float)):
            raise ValueError("画质备份格式无效，已保留备份且不写注册表")
        for field in ("original", "temporary"):
            record[field] = base64.b64decode(record[field], validate=True)
            decode_model(record[field])
        if lower_graphics(record["original"]) != record["temporary"]:
            raise ValueError("画质备份校验失败，已保留备份且不写注册表")
        return record

    def _save_backup(self, path, original, temporary, completed=False):
        record = {"schema": 1, "registry": path, "completed": completed, **self.owner,
                  "original": base64.b64encode(original).decode("ascii"),
                  "temporary": base64.b64encode(temporary).decode("ascii")}
        # 同目录原子替换；落盘成功前绝不修改游戏。不会覆盖尚未恢复的旧备份。
        fd, name = tempfile.mkstemp(dir=self.path.parent, prefix="graphics-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(record, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def _restore(self, record):
        path = record["registry"]
        current = self.registry.read(path, MODEL)
        if current == (record["original"], 3):
            return True
        if (self.registry.read(path, QUALITY) != (0, 4)
                or self.registry.read(path, VERSION) != (10, 4)
                or self.registry.read(path, AB_TEST) is not None
                or current is None or current[1] != 3
                or decode_model(current[0]) != decode_model(record["temporary"])):
            self.log.warning(f"画质设置已被其它来源修改，未覆盖；原始备份保留在 {self.path}")
            return False
        self.registry.write_model(path, record["original"])
        if self.registry.read(path, MODEL) != (record["original"], 3):
            raise OSError("恢复画质后的校验失败")
        self.log.info("已恢复原有画质配置；运行中的游戏画面需重启游戏后恢复")
        return True

    def recover(self):
        if not backup_exists(self.path):
            return True
        with journal_lock(self.path):
            if not backup_exists(self.path):
                return True
            record = self._read_backup()
            if not record.get("completed", False) and owner_alive(record):
                return False
            if not self._restore(record):
                return False
            # 游戏还在运行时保留备份，防止它在稍后的退出过程中写回临时模型。
            if self.registry.game_running():
                return False
            self.path.unlink()
            return True

    def begin(self, game_path):
        # 不能把上一次的临时值备份成“原始值”。同进程重试也必须先完成上次恢复。
        if self.active and not self.restore(final=True):
            return False
        if not self.recover():
            self.log.warning("已有未结束或尚未恢复的画质调整，本次跳过降低画质")
            return False
        with journal_lock(self.path):
            if backup_exists(self.path):
                return False
            if self.registry.game_running():
                self.log.info("游戏进程已运行，本次不降低画质")
                return False
            path = self.registry.path_for_game(game_path)
            if self.registry.read(path, AB_TEST) is not None:
                raise UnsupportedGraphics("检测到不兼容的 A/B 测试画质格式")
            if self.registry.read(path, VERSION) != (10, 4):
                raise UnsupportedGraphics("未知的画质配置版本")
            if self.registry.read(path, QUALITY) != (0, 4):
                raise UnsupportedGraphics("请先在游戏内将图像质量设为自定义并保存；预设画质暂不调整")
            original = self.registry.read(path, MODEL)
            if original is None or original[1] != 3:
                raise UnsupportedGraphics("未找到二进制画质配置")
            temporary = lower_graphics(original[0])
            if temporary == original[0]:
                return False
            self._save_backup(path, original[0], temporary)
            self.active = True
            # 写前复核，避免在备份阶段发生的用户改动被覆盖。
            if (self.registry.game_running() or self.registry.read(path, MODEL) != original
                    or self.registry.read(path, QUALITY) != (0, 4)
                    or self.registry.read(path, VERSION) != (10, 4)
                    or self.registry.read(path, AB_TEST) is not None):
                self.path.unlink()
                self.active = False
                return False
            self.registry.write_model(path, temporary)
            if self.registry.read(path, MODEL) != (temporary, 3):
                raise OSError("临时画质写入校验失败")
            self.log.info("已临时降低画质，保留帧率、渲染比例、抗锯齿及未知设置")
            return True

    def restore(self, final=False):
        if not self.active:
            return True
        with journal_lock(self.path):
            record = self._read_backup()
            if any(record[k] != v for k, v in self.owner.items()):
                raise ValueError("画质备份不属于本次运行")
            success = self._restore(record)
            if success and final:
                if self.registry.game_running():
                    self._save_backup(record["registry"], record["original"], record["temporary"], completed=True)
                else:
                    self.path.unlink()
                self.active = False
            return success


_session = None
_lock = threading.RLock()


def begin_temporary_graphics(game_path, logger):
    global _session
    if sys.platform != "win32":
        return
    with _lock:
        if _session is None:
            _session = GraphicsSession(WindowsGraphicsRegistry(), backup_path(), logger)
        try:
            _session.begin(game_path)
        except Exception as error:
            logger.warning(f"本次跳过降低画质：{error}")
            restore_temporary_graphics(final=True)


def restore_temporary_graphics(final=False, *, blocking=True):
    # 强制停止计时器不能卡在另一个线程持有的锁上，已有落盘备份可在退出后恢复。
    if not _lock.acquire(blocking=blocking):
        return False
    try:
        if _session is not None:
            try:
                return _session.restore(final=final)
            except Exception as error:
                _session.log.warning(f"恢复画质失败，备份已保留，将在下次启动助手时重试：{error}")
                return False
    finally:
        _lock.release()
    return True


def recover_temporary_graphics(logger):
    """恢复已退出任务遗留的配置，与当前功能开关无关；不触碰存活任务的备份。"""
    if sys.platform != "win32":
        return
    with _lock:
        try:
            if not backup_exists(backup_path()):
                return
            GraphicsSession(WindowsGraphicsRegistry(), backup_path(), logger).recover()
        except Exception as error:
            logger.warning(f"恢复上次临时画质失败，备份已保留：{error}")


atexit.register(restore_temporary_graphics, final=True)
