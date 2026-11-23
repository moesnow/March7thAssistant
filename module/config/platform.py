from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

from module.connection_values import configured_backend, configured_profile
from module.config import cfg
from module.config.config import _get_env_override
from module.localization import tr


ControlBackend = Literal["local", "cloud", "adb"]


class ProfileAssetNotFoundError(FileNotFoundError):
    """所选 UI 形态缺少所需文件。"""


class InvalidGameConnection(ValueError):
    """配置中的游戏后端或界面形态无效。"""


class TouchProfileInputError(RuntimeError):
    def __init__(self, method):
        super().__init__(tr("触屏模式不支持 {method}，请改用触摸操作").format(method=method))


@dataclass(frozen=True)
class UIProfile:
    name: str
    resolution: tuple[int, int]
    screens_path: Path
    images_root: Path

    def resolve_image_path(self, path: str | Path) -> str | Path:
        """将旧素材路径映射到同名触屏素材，或使用调用方指定的文件。"""
        if self.name == "pc_1080":
            return path

        image_path = Path(path)
        legacy_root = _UI_PROFILES["pc_1080"].images_root.resolve()
        absolute_path = image_path.resolve()
        if absolute_path.is_relative_to(legacy_root):
            image_path = self.images_root / absolute_path.relative_to(legacy_root)
        if not image_path.is_file():
            raise ProfileAssetNotFoundError(tr("触屏素材文件不存在：{path}").format(path=image_path))
        return str(image_path)


_UI_PROFILES = {
    "pc_1080": UIProfile("pc_1080", (1920, 1080), Path("assets/config/screens.json"), Path("assets/images")),
    "touch_720": UIProfile("touch_720", (1280, 720), Path("assets/touch_720/screens.json"), Path("assets/touch_720/images")),
}
_pinned_connection = None


def read_game_connection_config(config):
    """读取磁盘上供新进程使用的连接设置，保留当前进程的配置。"""
    status, values, _ = config._read_config_file(config.config_path)
    if status != "ok":
        raise InvalidGameConnection(tr("配置加载失败"))
    connection = {}
    for key in ("control_backend", "cloud_game_enable", "ui_profile"):
        overridden, value = _get_env_override(key)
        connection[key] = value if overridden else values.get(key)
    return SimpleNamespace(**connection)


@contextmanager
def pin_game_connection(config, *, connection=None):
    """本轮完成前固定实际使用的游戏连接，配置保存仍可合并外部改动。"""
    global _pinned_connection
    previous = _pinned_connection
    if connection is None:
        connection = get_control_backend(config), get_ui_profile(config)
    _pinned_connection = (config, *connection)
    try:
        yield connection
    except BaseException as error:
        # 退出连接后，最外层的错误处理仍须使用本轮实际连接。
        error.game_connection = connection
        raise
    finally:
        _pinned_connection = previous


def get_control_backend(config=None) -> ControlBackend:
    config = cfg if config is None else config
    if _pinned_connection is not None and _pinned_connection[0] is config:
        return _pinned_connection[1]
    backend = configured_backend(config)
    if backend in ("local", "cloud", "adb"):
        return backend
    raise InvalidGameConnection(tr("无效的 control_backend：{value}，可选值为 local、cloud、adb").format(value=backend))


def get_ui_profile(config=None) -> UIProfile:
    config = cfg if config is None else config
    if _pinned_connection is not None and _pinned_connection[0] is config:
        return _pinned_connection[2]
    name = configured_profile(config)
    if isinstance(name, str) and name in _UI_PROFILES:
        return _UI_PROFILES[name]
    raise InvalidGameConnection(tr("无效的 ui_profile：{value}，可选值为 pc_1080、touch_720").format(value=name))
