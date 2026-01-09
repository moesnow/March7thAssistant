import sys
import time
import copy
import os
from ruamel.yaml import YAML
from utils.singleton import SingletonMeta

# 环境变量覆盖映射：环境变量名 -> (配置键, 转换函数)
# 环境变量值为 "true"/"1" 时为 True，"false"/"0" 时为 False
_ENV_OVERRIDE_MAP = {
    "MARCH7TH_CLOUD_GAME_ENABLE": ("cloud_game_enable", lambda v: v.lower() in ("true", "1")),
    "MARCH7TH_BROWSER_HEADLESS_ENABLE": ("browser_headless_enable", lambda v: v.lower() in ("true", "1")),
    "MARCH7TH_BROWSER_HEADLESS_RESTART_ON_NOT_LOGGED_IN": ("browser_headless_restart_on_not_logged_in", lambda v: v.lower() in ("true", "1")),
    "MARCH7TH_BROWSER_DOWNLOAD_USE_MIRROR": ("browser_download_use_mirror", lambda v: v.lower() in ("true", "1")),
    "MARCH7TH_LOG_LEVEL": ("log_level", lambda v: v.upper()),  # 日志等级：INFO, DEBUG, WARNING, ERROR
    "MARCH7TH_AFTER_FINISH": ("after_finish", lambda v: v),  # 任务完成后操作：None, Exit, Loop, Shutdown, Sleep, Hibernate, Restart, Logoff, TurnOffDisplay, RunScript
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
            sys.exit("版本文件未找到")

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
        """加载用户配置信息，如未找到则保存默认配置"""
        path = path or self.config_path
        try:
            with open(path, 'r', encoding='utf-8') as file:
                loaded_config = self.yaml.load(file)
                if loaded_config:
                    # self.config.update(loaded_config)
                    self._update_config(self.config, loaded_config)
            if save:
                self.save_config()
        except FileNotFoundError:
            self.save_config()
        except Exception as e:
            print(f"配置文件 {path} 加载错误: {e}")

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
        """保存配置到文件"""
        with open(self.config_path, 'w', encoding='utf-8') as file:
            self.yaml.dump(self.config, file)

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
