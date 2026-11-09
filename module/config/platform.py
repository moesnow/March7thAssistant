from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from module.config import cfg
from module.localization import tr


ControlBackend = Literal["local", "cloud", "adb"]


class ProfileAssetNotFoundError(FileNotFoundError):
    """所选 UI 形态缺少所需文件。"""


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


def get_control_backend(config=None) -> ControlBackend:
    config = cfg if config is None else config
    backend = getattr(config, "control_backend", None)
    if backend is None:
        return "cloud" if getattr(config, "cloud_game_enable", False) else "local"
    if backend in ("local", "cloud", "adb"):
        return backend
    raise ValueError(tr("无效的 control_backend：{value}，可选值为 local、cloud、adb").format(value=backend))


def get_ui_profile(config=None) -> UIProfile:
    config = cfg if config is None else config
    name = getattr(config, "ui_profile", None)
    if name is None:
        name = "pc_1080"
    if isinstance(name, str) and name in _UI_PROFILES:
        return _UI_PROFILES[name]
    raise ValueError(tr("无效的 ui_profile：{value}，可选值为 pc_1080、touch_720").format(value=name))
