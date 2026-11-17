"""Transparent dark portraits with textures from the original artwork."""
from functools import lru_cache
from pathlib import Path

from PySide6.QtGui import QImage, QPainter, QPixmap

from .evernight import EVERNIGHT_AVATAR


_IMAGE_ROOT = Path('./assets/app/images')
_DARK_PORTRAITS = {
    str((_IMAGE_ROOT / f'{name}.jpg').resolve()): str(_IMAGE_ROOT / 'dark' / f'{name}.png')
    for name in ('March7th', 'JingYuan', 'Yanqing', 'Herta', 'SilverWolf', 'Bronya')
}
_DARK_PORTRAITS[str(Path(EVERNIGHT_AVATAR).resolve())] = str(_IMAGE_ROOT / 'dark/Evernight.png')


def themed_icon_path(path, dark):
    if not path or not dark:
        return path
    return _DARK_PORTRAITS.get(str(Path(path).resolve()), path)


def portrait_texture(reference):
    """Strengthen the original colours without moving or inverting the artwork."""
    pattern = reference.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(pattern)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
    for _ in range(7):
        painter.drawPixmap(0, 0, reference)
    painter.end()
    return QPixmap.fromImage(pattern)


@lru_cache(maxsize=14)  # Seven bundled portraits, each with a light/dark variant.
def _builtin_portrait_artwork(source, dark):
    foreground = QPixmap(themed_icon_path(source, dark))
    texture = portrait_texture(QPixmap(source)) if dark else QPixmap()
    return foreground, texture


def portrait_artwork(path, dark):
    source = str(Path(path).resolve()) if path else path
    if source in _DARK_PORTRAITS:
        return _builtin_portrait_artwork(source, dark)
    # Custom files are re-read when cards are rebuilt, including edits in place.
    return QPixmap(path), QPixmap()


def application_icon_path(evernight=False, *, titlebar=False):
    """Keep the original March 7th icon until the Easter egg is displayed."""
    if not evernight:
        return './assets/logo/March7th.ico'
    filename = 'titlebar.ico' if titlebar else 'icon.ico'
    return str(Path('./assets/logo/evernight') / filename)
