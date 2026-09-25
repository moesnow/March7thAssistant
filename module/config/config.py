import sys
import time
import copy
import os
import shutil
import tempfile
from ruamel.yaml import YAML
from utils.singleton import SingletonMeta

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

    def __init__(self, version_path, example_path, config_path):
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

    def _load_config(self, path=None, save=True):
        """加载用户配置信息

        - 文件缺失（首次运行）：保存默认配置
        - 文件为空或损坏：备份损坏文件并提示用户，不静默覆盖为默认配置
        """
        path = path or self.config_path
        try:
            with open(path, 'r', encoding='utf-8') as file:
                loaded_config = self.yaml.load(file)
        except FileNotFoundError:
            self.save_config()
            return
        except Exception as e:
            self._handle_broken_config(path, f"解析失败: {e}")
            return

        if loaded_config is None:
            # 空文件（或仅含注释）：多半是写入过程被中断导致的损坏
            self._handle_broken_config(path, "文件为空或不包含有效内容（可能是写入过程被中断）")
            return
        if not isinstance(loaded_config, dict):
            self._handle_broken_config(path, "文件内容不是有效的配置映射")
            return

        self._update_config(self.config, loaded_config)
        if save:
            self.save_config()

    def _handle_broken_config(self, path, reason):
        """处理损坏的配置文件：备份损坏内容并提示用户，避免静默重置为默认配置"""
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
            try:
                os.replace(path, backup_path)
            except OSError:
                # 目标是挂载点（如 Docker 单文件挂载）时无法移动，退化为复制备份
                shutil.copyfile(path, backup_path)
            return backup_path
        except Exception:
            return None

    def _notify_config_error(self, message):
        """向用户提示配置文件损坏（进程内只提示一次）"""
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
        """读取配置文件内容（不修改内存中的 self.config），返回 dict 或 None"""
        path = path or self.config_path
        try:
            with open(path, 'r', encoding='utf-8') as file:
                return self.yaml.load(file) or {}
        except FileNotFoundError:
            return None
        except Exception:
            return None

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
        """保存配置到文件（先写临时文件再原子替换；目标为挂载点时退化为原地覆盖写入）"""
        config_dir = os.path.dirname(os.path.abspath(self.config_path))
        # 临时文件名唯一，避免多进程同时保存时互相截断
        tmp_fd, tmp_path = tempfile.mkstemp(
            prefix=f"{os.path.basename(self.config_path)}.", suffix=".tmp", dir=config_dir
        )
        try:
            with os.fdopen(tmp_fd, 'w', encoding='utf-8') as file:
                self.yaml.dump(self.config, file)
                file.flush()
                os.fsync(file.fileno())
            try:
                os.replace(tmp_path, self.config_path)
            except OSError:
                # 目标是挂载点（如 Docker 单文件挂载的 config.yaml）时 rename 会报 EBUSY，
                # 退化为原地覆盖写入（非原子，但保证可保存）
                with open(tmp_path, 'rb') as src, open(self.config_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                    dst.flush()
                    os.fsync(dst.fileno())
                os.remove(tmp_path)
        except Exception:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            raise

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
        self._load_config()
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
