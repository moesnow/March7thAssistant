import sys
import time
import copy
import os
from ruamel.yaml import YAML
from ruamel.yaml.tokens import CommentToken
from ruamel.yaml.error import CommentMark
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


# 支持的 UI 语言（与 assets/locales 下的语言文件保持一致）
SUPPORTED_LANGUAGES = ("zh_CN", "zh_TW", "ja_JP", "ko_KR", "en_US")


def _detect_ui_language(config_path):
    """
    在加载配置前确定 UI 语言，用于选择对应语言的示例配置文件（如 config.example.zh_CN.yaml）。
    优先读取用户 config.yaml 中的 ui_language；为 auto / 未设置 / 无法读取时使用系统语言检测。
    """
    lang = None
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            user_config = YAML(typ='safe').load(file) or {}
        if isinstance(user_config, dict):
            lang = user_config.get("ui_language")
    except Exception:
        lang = None

    if isinstance(lang, str) and lang in SUPPORTED_LANGUAGES:
        return lang

    try:
        from module.localization import detect_lang
        return detect_lang()
    except Exception:
        return "zh_CN"


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
        self.config_path = config_path
        # 多语言支持：根据 UI 语言优先加载对应语言的示例配置，如 config.example.zh_CN.yaml
        self.lang = _detect_ui_language(config_path)
        lang_example_path = self._get_language_example_path(example_path)
        if lang_example_path:
            self.config = self._load_default_config(lang_example_path)
            # 语言示例配置可能未及时同步新增配置项，用基础示例配置补齐缺失的键
            self._fill_missing_keys(self._load_default_config(example_path))
        else:
            self.config = self._load_default_config(example_path)
        self._load_config()

    def _get_language_example_path(self, example_path):
        """根据 UI 语言获取对应语言的示例配置文件路径，不存在时返回 None"""
        root, ext = os.path.splitext(example_path)
        lang_path = f"{root}.{self.lang}{ext}"
        if lang_path != example_path and os.path.exists(lang_path):
            return lang_path
        return None

    def _fill_missing_keys(self, base_config):
        """
        将基础示例配置中存在、而当前默认配置缺失的键补充进来（保留注释），
        防止语言示例配置文件未同步时丢失配置项

        ruamel 注释模型说明：
        - 键的行内（EOL）注释存储在该键自己的 ca 条目中
        - 键上方的独立注释行存储在前一个键的尾随 CommentToken 中
        因此补充缺失键时，需要同时处理这两种注释的迁移
        """
        if not base_config:
            return

        def _extract_standalone(token):
            """从前一个键的尾随 token 中提取独立注释部分（去掉属于前一个键的 EOL 注释）"""
            value = token.value
            if token.start_mark is not None and token.start_mark.column > 0:
                # token 起始于行内（EOL 注释），第一行属于前一个键，去掉
                nl = value.find('\n')
                value = value[nl + 1:] if nl >= 0 else ''
            return value

        def _clone_token(value):
            return CommentToken(value, CommentMark(0))

        def _append_trailing(dst, standalone):
            """把独立注释追加到 dst 最后一个键的尾随位置"""
            if not standalone:
                return
            last_key = list(dst.keys())[-1]
            entry = dst.ca.items.get(last_key)
            if entry is None:
                entry = [None, None, None, None]
                dst.ca.items[last_key] = entry
            token = entry[2]
            if token is None:
                entry[2] = _clone_token(standalone)
            elif standalone.startswith('\n'):
                entry[2] = _clone_token(token.value + standalone[1:])
            else:
                entry[2] = _clone_token(token.value + standalone)

        def _fill(dst, src):
            src_keys = list(src.keys())
            for idx, key in enumerate(src_keys):
                if key in dst:
                    if isinstance(dst[key], dict) and isinstance(src[key], dict):
                        _fill(dst[key], src[key])
                    continue
                # 先把该键前面的独立注释追加到 dst 当前最后一个键的尾随位置
                if idx > 0:
                    prev_entry = src.ca.items.get(src_keys[idx - 1])
                    if prev_entry is not None and prev_entry[2] is not None:
                        standalone = _extract_standalone(prev_entry[2])
                        if standalone:
                            _append_trailing(dst, standalone)
                # 再插入键及其值
                dst[key] = src[key]
                entry = src.ca.items.get(key)
                if entry is not None:
                    # 只保留该键自己的 EOL 注释（去掉属于下一个键的独立注释部分）
                    new_entry = list(entry)
                    token = entry[2]
                    if token is not None and token.start_mark is not None and token.start_mark.column > 0:
                        nl = token.value.find('\n')
                        new_entry[2] = _clone_token(token.value if nl < 0 else token.value[:nl + 1])
                    else:
                        new_entry[2] = None
                    dst.ca.items[key] = new_entry

        _fill(self.config, base_config)

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
