"""桌面插画。QPixmap 请在 GUI 线程中加载。"""
from enum import Enum
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPixmapCache


class Mascot(str, Enum):
    FULL = "chibi_full"
    TYPING = "chibi_typing"
    WAVE = "chibi_wave"
    LOST = "chibi_lost"
    OK = "chibi_ok"
    CAMERA = "chibi_camera"
    GIFT = "chibi_gift"
    SERIOUS = "chibi_serious"
    SEARCH = "chibi_search"
    VIEWFINDER = "chibi_viewfinder"
    CLOUD = "chibi_cloud"
    DIZZY = "chibi_dizzy"
    LATER = "chibi_later"
    STAMP = "chibi_stamp"
    STARTLED = "chibi_startled"
    BOX = "chibi_box"


def mascot_path(pose: Mascot, *, evernight: bool = False) -> str:
    root = "./assets/app/images/mascot"
    filename = f"{pose.value}.webp"
    if evernight and Path(root, "evernight", filename).is_file():
        return f"{root}/evernight/{filename}"
    return f"{root}/{filename}"


def load_mascot(pose: Mascot, height: int, dpr: float = 1.0, *, evernight: bool = False) -> QPixmap:
    path = mascot_path(pose, evernight=evernight)
    if height <= 0 or dpr <= 0:
        return QPixmap()
    key = f"mascot:{Path(path).absolute()}:{height}:{dpr}"
    cached = QPixmapCache.find(key)
    if cached is not None:
        return cached
    pixmap = QPixmap(path)
    if not pixmap.isNull():
        pixmap = pixmap.scaledToHeight(max(1, round(height * dpr)), Qt.SmoothTransformation)
        pixmap.setDevicePixelRatio(dpr)
        QPixmapCache.insert(key, pixmap)
    return pixmap
