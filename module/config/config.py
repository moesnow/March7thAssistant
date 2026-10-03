import sys
import time
import copy
import hashlib
import os
import shutil
import tempfile
import threading
import traceback
from ruamel.yaml import YAML
from utils.singleton import SingletonMeta

# ── 配置读写诊断日志 ──────────────────────────────────────────────────
# 用于排查“更新后配置文件损坏/丢失”这类低概率问题：所有配置读写、
# 原子替换失败降级、损坏备份等关键路径都会留下带 PID/线程名的日志。
# 日志始终追加写入 logs/config_diag.log；若全局 log（module.logger）
# 已初始化则同时转发一份。注意 module.logger 反过来依赖 module.config，
# 因此这里绝不能主动 import module.logger，只能在它已加载时转发。

_DIAG_FILE = os.path.join("logs", "config_diag.log")
_DIAG_FILE_MAX_BYTES = 5 * 1024 * 1024
_DIAG_FILE_LOCK = threading.Lock()


def _diag_rotated_path():
    """轮转文件名：config_diag.log -> config_diag.1.log

    必须保留 .log 后缀：utils.logger 的 _cleanup_old_logs 按 *.log + 保留天数
    回收 logs/ 下的日志，命名成 config_diag.log.1 会永远残留（即使将来移除
    本诊断模块，历史文件也应能被正常清理）。
    """
    root, ext = os.path.splitext(_DIAG_FILE)
    return f"{root}.1{ext or '.log'}"


def _diag(level, message):
    """写诊断日志（绝不抛错）。level: debug/info/warning/error"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    millis = int((time.time() % 1) * 1000)
    thread_name = threading.current_thread().name
    line = f"{timestamp}.{millis:03d} [{level.upper()}] [pid={os.getpid()}] [thread={thread_name}] {message}"
    try:
        with _DIAG_FILE_LOCK:
            log_dir = os.path.dirname(_DIAG_FILE)
            if log_dir and not os.path.isdir(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            try:
                if os.path.exists(_DIAG_FILE) and os.path.getsize(_DIAG_FILE) > _DIAG_FILE_MAX_BYTES:
                    os.replace(_DIAG_FILE, _diag_rotated_path())
            except OSError:
                pass
            with open(_DIAG_FILE, "a", encoding="utf-8") as file:
                file.write(line + "\n")
    except Exception:
        pass
    try:
        logger_module = sys.modules.get("module.logger")
        logger = getattr(logger_module, "log", None)
        method = getattr(logger, level, None)
        if callable(method):
            method(f"[config] {message}")
    except Exception:
        pass


def _file_fingerprint(path):
    """返回文件的简要指纹（大小/sha256 前 12 位/开头字节），用于对比损坏前后内容"""
    try:
        with open(path, "rb") as file:
            data = file.read()
    except OSError as e:
        return f"<读取失败: {e}>"
    digest = hashlib.sha256(data).hexdigest()[:12]
    return f"size={len(data)} sha256={digest} head={data[:120]!r}"


# 读取重试：并发读写冲突（如另一进程正在 os.replace）只持续毫秒级，重试几次即可避开
_READ_RETRY_ATTEMPTS = 5
_READ_RETRY_BASE_DELAY = 0.03

# 原子替换重试：同上，短暂重试可避免退化为危险的非原子原地写入
_REPLACE_RETRY_ATTEMPTS = 5
_REPLACE_RETRY_BASE_DELAY = 0.03


def _is_io_conflict_error(e):
    """判断是否为 IO 占用/权限冲突（而非内容损坏）

    Windows 下 os.replace 目标被其他进程打开（无 FILE_SHARE_DELETE）时报
    WinError 5/32，读取撞上替换瞬间时报 Permission denied（errno 13）；
    Docker 单文件挂载 rename 报 EBUSY（errno 16）。这些都是占用/权限冲突，
    不代表文件内容损坏，绝不能据此判定损坏并移走文件。
    """
    if isinstance(e, PermissionError):
        return True
    if getattr(e, "winerror", None) in (5, 32):
        return True
    return getattr(e, "errno", None) in (13, 16)


def _is_retryable_io_error(e):
    """判断占用冲突是否值得短暂重试

    只有“稍纵即逝”的并发占用才值得重试：Windows 下其他进程读取配置只持有
    文件毫秒级，替换撞上共享冲突（PermissionError / WinError 5/32）重试几次
    即可避开——这类错误带 winerror 或是 PermissionError/errno 13，行为不变。
    而 EBUSY（errno 16，Docker 单文件挂载的 rename 撞上挂载点）是永久性的，
    重试注定失败，应立即走降级路径，避免每次保存都空等重试。
    """
    if getattr(e, "winerror", None) is None and not isinstance(e, PermissionError) and getattr(e, "errno", None) == 16:
        return False
    return _is_io_conflict_error(e)

# 环境变量覆盖映射：环境变量名 -> (配置键, 转换函数)
# 环境变量值为 "true"/"1" 时为 True，"false"/"0" 时为 False
_ENV_OVERRIDE_MAP = {
    "MARCH7TH_CLOUD_GAME_ENABLE": ("cloud_game_enable", lambda v: v.lower() in ("true", "1")),
    "MARCH7TH_CLOUD_GAME_USE_PAID_TIME": ("cloud_game_use_paid_time", lambda v: v.lower() in ("true", "1")),
    "MARCH7TH_BROWSER_HEADLESS_ENABLE": ("browser_headless_enable", lambda v: v.lower() in ("true", "1")),
    "MARCH7TH_BROWSER_HEADLESS_RESTART_ON_NOT_LOGGED_IN": ("browser_headless_restart_on_not_logged_in", lambda v: v.lower() in ("true", "1")),
    "MARCH7TH_BROWSER_DOWNLOAD_USE_MIRROR": ("browser_download_use_mirror", lambda v: v.lower() in ("true", "1")),
    "MARCH7TH_LOG_LEVEL": ("log_level", lambda v: v.upper()),  # 日志等级：INFO, DEBUG, WARNING, ERROR
    "MARCH7TH_AFTER_FINISH": ("after_finish", lambda v: v),  # 任务完成后操作：None, Exit, Loop, Shutdown, Sleep, Hibernate, Restart, Logoff, TurnOffDisplay, RunScript
    "MARCH7TH_BROWSER_TYPE": ("browser_type", lambda v: v),  # 浏览器类型：integrated, edge, chrome
}

# 反向映射：配置键 -> 环境变量名
_CONFIG_KEY_TO_ENV = {v[0]: k for k, v in _ENV_OVERRIDE_MAP.items()}


def _get_env_override(config_key):
    """
    检查配置键是否有环境变量覆盖
    :param config_key: 配置键名
    :return: (has_override, value) 如果有覆盖返回 (True, 覆盖值)，否则返回 (False, None)
    """
    env_name = _CONFIG_KEY_TO_ENV.get(config_key)
    if env_name:
        env_value = os.environ.get(env_name)
        if env_value is not None:
            _, converter = _ENV_OVERRIDE_MAP[env_name]
            return True, converter(env_value)
    return False, None


class Config(metaclass=SingletonMeta):
    """
    配置管理类，用于加载、更新和保存配置信息
    """

    # 配置文件损坏提示只弹一次，避免反复打扰
    _config_error_notified = False

    # 只读角色（更新器/清理器等旁观进程）：只读取配置、绝不写入。
    # 进程启动时通过环境变量 MARCH7TH_CONFIG_READONLY=1 声明。
    _readonly = False

    def __init__(self, version_path, example_path, config_path):
        Config._readonly = os.environ.get("MARCH7TH_CONFIG_READONLY", "").lower() in ("1", "true")
        if Config._readonly:
            _diag("info", "当前进程以只读模式加载配置（更新器/清理器等旁观进程），不会写入配置文件")
        _diag("info", f"Config 初始化: config_path={os.path.abspath(config_path)} "
                      f"exists={os.path.exists(config_path)} {_file_fingerprint(config_path) if os.path.exists(config_path) else ''}")
        self.yaml = YAML()
        self.version = self._load_version(version_path)
        self.config = self._load_default_config(example_path)
        self.config_path = config_path
        self._load_config()

    def _load_version(self, version_path):
        """加载版本信息"""
        try:
            with open(version_path, 'r', encoding='utf-8') as file:
                return file.read().strip()
        except FileNotFoundError:
            raise FileNotFoundError("版本文件未找到")

    def _update_config(self, config, new_config):
        """递归更新配置信息"""
        for key, value in new_config.items():
            if key in config:
                if isinstance(config[key], dict) and isinstance(value, dict):
                    self._update_config(config[key], value)
                else:
                    config[key] = value

    def _load_default_config(self, config_example_path):
        """加载默认配置信息"""
        try:
            with open(config_example_path, 'r', encoding='utf-8') as file:
                return self.yaml.load(file) or {}
        except FileNotFoundError:
            sys.exit("默认配置文件未找到")

    def _read_config_file(self, path):
        """读取并解析配置文件，区分三种情况并做有限重试

        返回 (status, data, detail)：
        - ("ok", dict, "")        读取并解析成功
        - ("missing", None, ...)  文件不存在
        - ("unreadable", None, ...) 持续的占用冲突（非损坏，绝不能走损坏保护）
        - ("broken", None, ...)   重试后仍为空/解析失败/非映射（真损坏）

        瞬时并发冲突（Windows 共享冲突）与“读到写入中间态”都会短暂重试，
        避免把完好文件误判为损坏；永久性占用（挂载点 EBUSY）不空转重试。
        """
        last_status, last_detail, last_retryable = "broken", "未知原因", True
        for attempt in range(1, _READ_RETRY_ATTEMPTS + 1):
            try:
                with open(path, 'r', encoding='utf-8') as file:
                    loaded = self.yaml.load(file)
            except FileNotFoundError:
                return "missing", None, "文件不存在"
            except Exception as e:
                if _is_io_conflict_error(e):
                    last_status, last_detail = "unreadable", f"读取冲突（文件正被其他进程替换/占用）: {e}"
                    last_retryable = _is_retryable_io_error(e)
                else:
                    last_status, last_detail, last_retryable = "broken", f"解析失败: {e}", True
            else:
                if loaded is None:
                    last_status, last_detail, last_retryable = "broken", "文件为空或不包含有效内容（可能是写入过程被中断）", True
                elif not isinstance(loaded, dict):
                    last_status, last_detail, last_retryable = "broken", "文件内容不是有效的配置映射", True
                else:
                    if attempt > 1:
                        _diag("warning", f"配置读取在第 {attempt} 次尝试成功（此前撞上并发读写窗口）: {os.path.abspath(path)}")
                    return "ok", loaded, ""
            if attempt < _READ_RETRY_ATTEMPTS and last_retryable:
                time.sleep(_READ_RETRY_BASE_DELAY * attempt)
            elif not last_retryable:
                break
        return last_status, None, last_detail

    def _load_config(self, path=None, save=True):
        """加载用户配置信息

        - 文件缺失（首次运行）：保存默认配置
        - 并发占用冲突：短暂重试，仍失败则放弃本次加载（不动文件，更不判损坏）
        - 文件为空或损坏：备份损坏文件并提示用户，不静默覆盖为默认配置
        """
        path = path or self.config_path
        _diag("debug", f"_load_config 开始: path={os.path.abspath(path)} save={save}")
        status, loaded_config, detail = self._read_config_file(path)

        if status == "missing":
            _diag("info", f"配置文件不存在（首次运行或已被移走），写入默认配置: {os.path.abspath(path)}")
            self.save_config()
            return
        if status == "unreadable":
            # 典型场景：读取撞上另一进程 os.replace 的瞬间（Permission denied）。
            # 文件大概率完好，走损坏保护会把好文件移走并重置配置——绝不能做。
            _diag("error", f"配置文件暂时无法读取，放弃本次加载（不判定损坏、不改动文件）: "
                           f"{os.path.abspath(path)} 原因={detail}\n文件内容: {_file_fingerprint(path)}")
            return
        if status == "broken":
            _diag("error", f"配置文件损坏: {os.path.abspath(path)} 原因={detail}\n"
                           f"文件内容: {_file_fingerprint(path)}")
            self._handle_broken_config(path, detail)
            return

        self._update_config(self.config, loaded_config)
        _diag("debug", f"_load_config 成功: 合并 {len(loaded_config)} 个顶层键")
        if save:
            self.save_config()

    def _handle_broken_config(self, path, reason):
        """处理损坏的配置文件：备份损坏内容并提示用户，避免静默重置为默认配置"""
        _diag("error", f"检测到配置文件损坏: {os.path.abspath(path)} 原因={reason}")
        backup_path = self._backup_broken_config(path)
        message = f"配置文件无法读取，已使用默认配置启动。\n文件: {path}\n原因: {reason}"
        if backup_path:
            message += f"\n为避免数据丢失，损坏的文件已备份到:\n{backup_path}\n如需恢复，请将其内容复制回:\n{path}"
        else:
            message += f"\n注意：损坏的文件未能自动备份，请手动检查 {path}"
        self._notify_config_error(message)

    def _backup_broken_config(self, path):
        """备份损坏的配置文件（保留原始字节）；无法移走时退化为复制，返回备份路径；失败返回 None"""
        try:
            backup_path = f"{path}.bak"
            if os.path.exists(backup_path):
                # 保留更早的备份，改用时间戳命名
                backup_path = f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
            # 移动可能撞上 Windows 并发占用（WinError 32），短暂重试再降级复制；
            # 挂载点 EBUSY 是永久性的，不空转重试，直接降级复制
            move_error = None
            for attempt in range(1, _REPLACE_RETRY_ATTEMPTS + 1):
                try:
                    os.replace(path, backup_path)
                    move_error = None
                    break
                except OSError as e:
                    move_error = e
                    if not _is_retryable_io_error(e):
                        break
                    if attempt < _REPLACE_RETRY_ATTEMPTS:
                        time.sleep(_REPLACE_RETRY_BASE_DELAY * attempt)
            if move_error is None:
                _diag("warning", f"损坏的配置文件已移至备份: {os.path.abspath(backup_path)}")
            else:
                # 目标是挂载点（如 Docker 单文件挂载）时无法移动，退化为复制备份
                _diag("warning", f"无法移动损坏的配置文件（{move_error}），退化为复制备份")
                shutil.copyfile(path, backup_path)
                _diag("warning", f"损坏的配置文件已复制到备份: {os.path.abspath(backup_path)}")
            return backup_path
        except Exception:
            _diag("error", f"备份损坏的配置文件失败: {os.path.abspath(path)}\n{traceback.format_exc()}")
            return None

    def _notify_config_error(self, message):
        """向用户提示配置文件损坏（进程内只提示一次）"""
        _diag("error", f"配置文件错误提示: {message}")
        if Config._config_error_notified:
            return
        Config._config_error_notified = True
        print(f"[配置错误] {message}")
        # 仅在打包后的 Windows 图形界面环境弹窗，避免测试/命令行/服务场景被阻塞
        if os.name == "nt" and getattr(sys, "frozen", False):
            try:
                import ctypes
                # MB_OK | MB_ICONERROR | MB_TOPMOST
                ctypes.windll.user32.MessageBoxW(None, message, "March7th Assistant - 配置文件错误", 0x00040010)
            except Exception:
                pass

    def _read_file_config(self, path=None):
        """读取配置文件内容（不修改内存中的 self.config），返回 dict 或 None

        - 文件缺失/持续并发占用冲突：返回 None（表示“读不到”，不判损坏）
        - 文件损坏：返回 {}，让 is_config_changed 报告“有变化”，
          从而走 _load_config 的损坏保护流程（备份并提示用户）
        """
        path = path or self.config_path
        status, loaded, detail = self._read_config_file(path)
        if status == "ok":
            return loaded
        if status == "missing":
            _diag("debug", f"_read_file_config: 文件不存在 {os.path.abspath(path)}")
            return None
        if status == "unreadable":
            # 并发冲突，不是损坏；静默跳过本次比对即可
            _diag("warning", f"_read_file_config 暂时无法读取（并发冲突，跳过本次比对）: "
                             f"{os.path.abspath(path)} 原因={detail}")
            return None
        _diag("error", f"_read_file_config 发现配置损坏: {os.path.abspath(path)} 原因={detail} "
                       f"文件内容: {_file_fingerprint(path)}")
        return {}

    def _configs_equal(self, a, b):
        """递归比较两个配置结构是否相等（逐项比较）"""
        # 统一 None -> {}
        if a is None:
            a = {}
        if b is None:
            b = {}

        if isinstance(a, dict) and isinstance(b, dict):
            # 比较所有键和值（对字典中每个键进行递归比较）
            a_keys = set(a.keys())
            b_keys = set(b.keys())
            if a_keys != b_keys:
                return False
            for k in a_keys:
                if not self._configs_equal(a[k], b[k]):
                    return False
            return True

        if isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                return False
            for x, y in zip(a, b):
                if not self._configs_equal(x, y):
                    return False
            return True

        # 其他可直接比较（数值、字符串、布尔等）
        return a == b

    def is_config_changed(self):
        """
        按照读取配置文件的方式逐项比较文件内容与内存中的 self.config，
        若存在差异则返回 True（表示外部已修改）
        """
        file_conf = self._read_file_config()
        if file_conf is None:
            return False
        changed = not self._configs_equal(file_conf, self.config)
        return changed

    def save_config(self):
        """保存配置到文件（先写临时文件再原子替换；替换持续失败时先备份再降级为原地覆盖写入）"""
        if Config._readonly:
            # 更新器/清理器等旁观进程不写配置：多进程并发写是配置损坏的根源之一
            _diag("info", f"save_config 跳过（当前进程为只读角色，不写配置文件）: {os.path.abspath(self.config_path)}")
            return
        config_dir = os.path.dirname(os.path.abspath(self.config_path))
        self._warn_stale_tmp_files(config_dir)
        # 临时文件名唯一，避免多进程同时保存时互相截断
        tmp_fd, tmp_path = tempfile.mkstemp(
            prefix=f"{os.path.basename(self.config_path)}.", suffix=".tmp", dir=config_dir
        )
        _diag("debug", f"save_config 开始: 目标={os.path.abspath(self.config_path)} 临时文件={os.path.basename(tmp_path)}")
        try:
            with os.fdopen(tmp_fd, 'w', encoding='utf-8') as file:
                self.yaml.dump(self.config, file)
                file.flush()
                os.fsync(file.fileno())
            _diag("debug", f"save_config 临时文件写入完成: {_file_fingerprint(tmp_path)}")

            replace_error = self._replace_with_retry(tmp_path, self.config_path)
            if replace_error is not None:
                # 两类情况会走到这里：
                # 1. Docker 单文件挂载的 config.yaml：rename 撞上挂载点报 EBUSY（永久性，未重试）；
                # 2. Windows 共享冲突重试用尽（WinError 5/32）或其他替换错误。
                # 降级为原地覆盖写入（非原子，写入中途被中断会截断配置文件），
                # 因此降级前先把当前配置复制一份留底。
                backup_path = self._backup_before_inplace_write(self.config_path)
                _diag("warning", f"save_config os.replace 失败（{replace_error}），"
                                 f"退化为非原子的原地覆盖写入（写入中途被中断会截断配置文件）；"
                                 f"原文件已备份至 {backup_path or '<备份失败>'}")
                with open(tmp_path, 'rb') as src, open(self.config_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                    dst.flush()
                    os.fsync(dst.fileno())
                os.remove(tmp_path)
                _diag("warning", f"save_config 原地覆盖写入完成: {_file_fingerprint(self.config_path)}")
        except Exception:
            _diag("error", f"save_config 写入失败，原文件应保持不变: {os.path.abspath(self.config_path)} "
                           f"当前文件: {_file_fingerprint(self.config_path)}\n{traceback.format_exc()}")
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            raise

    def _replace_with_retry(self, tmp_path, target_path):
        """原子替换，对瞬时并发冲突做有限重试。

        Windows 下其他进程读取配置只持有文件毫秒级，共享冲突短暂重试基本必然
        成功，从而避免退化为危险的非原子原地写入；挂载点 EBUSY 是永久性的，
        不重试、直接交给调用方走降级路径（与 Docker 单文件挂载的历史行为一致）。
        成功返回 None，失败返回最后的异常。
        """
        replace_error = None
        for attempt in range(1, _REPLACE_RETRY_ATTEMPTS + 1):
            try:
                os.replace(tmp_path, target_path)
                if attempt > 1:
                    _diag("warning", f"save_config os.replace 在第 {attempt} 次尝试成功（此前撞上并发读写窗口）")
                _diag("debug", f"save_config 原子替换成功: {_file_fingerprint(target_path)}")
                return None
            except OSError as e:
                replace_error = e
                if not _is_retryable_io_error(e):
                    break
                if attempt < _REPLACE_RETRY_ATTEMPTS:
                    _diag("warning", f"save_config os.replace 第 {attempt} 次失败（并发占用，稍后重试）: {e}")
                    time.sleep(_REPLACE_RETRY_BASE_DELAY * attempt)
        return replace_error

    def _backup_before_inplace_write(self, path):
        """降级原地覆盖写入前留底当前配置（尽力而为），避免写入中断导致配置丢失"""
        try:
            backup_path = f"{path}.prefallback"
            shutil.copyfile(path, backup_path)
            _diag("warning", f"降级写入前已备份当前配置: {os.path.abspath(backup_path)}")
            return backup_path
        except Exception:
            _diag("error", f"降级写入前备份失败: {os.path.abspath(path)}\n{traceback.format_exc()}")
            return None

    def _warn_stale_tmp_files(self, config_dir):
        """检测疑似写入中断残留的临时文件（进程被强杀时可能留下）"""
        try:
            prefix = f"{os.path.basename(self.config_path)}."
            now = time.time()
            for name in os.listdir(config_dir):
                if name.startswith(prefix) and name.endswith(".tmp"):
                    full = os.path.join(config_dir, name)
                    try:
                        age = now - os.path.getmtime(full)
                    except OSError:
                        continue
                    if age > 60:
                        _diag("warning", f"发现残留的配置临时文件（疑似写入过程中被中断）: {full} 残留 {int(age)} 秒")
        except Exception:
            pass

    def get_value(self, key, default=None):
        """获取配置项的值，环境变量优先，如果值是可变对象，则返回其拷贝"""
        # 先检查环境变量覆盖
        has_override, override_value = _get_env_override(key)
        if has_override:
            return override_value
        value = self.config.get(key, default)
        # 如果是可变对象（如列表、字典等），返回拷贝
        if isinstance(value, (list, dict, set)):
            return copy.deepcopy(value)  # 使用深拷贝确保嵌套对象安全
        return value

    def set_value(self, key, value):
        """设置配置项的值并保存"""
        _diag("debug", f"set_value: {key}={value!r}")
        # 读取外部改动但不再多写一次：save_config 只在最后落盘一次
        self._load_config(save=False)
        if isinstance(value, (list, dict, set)):
            self.config[key] = copy.deepcopy(value)
        else:
            self.config[key] = value
        self.save_config()

    def set_values(self, values):
        """批量设置配置项并一次性保存。

        与逐个调用 `set_value` 等价，但只落盘一次：
        `save_config` 带 fsync，逐项保存在批量恢复配置等场景会产生明显卡顿。
        """
        _diag("debug", f"set_values: {list(values.keys())}")
        self._load_config(save=False)
        for key, value in values.items():
            if isinstance(value, (list, dict, set)):
                self.config[key] = copy.deepcopy(value)
            else:
                self.config[key] = value
        self.save_config()

    def save_timestamp(self, key):
        """保存当前时间戳到指定的配置项"""
        self.set_value(key, time.time())

    def __getattr__(self, attr):
        """允许通过属性访问配置项的值，环境变量优先"""
        if attr in self.config:
            # 先检查环境变量覆盖
            has_override, override_value = _get_env_override(attr)
            if has_override:
                return override_value
            value = self.config[attr]
            if isinstance(value, (list, dict, set)):
                return copy.deepcopy(value)
            return value
        raise AttributeError(f"'{type(self).__name__}' 对象没有属性 '{attr}'")
