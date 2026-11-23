"""Load the optional Long Night artwork, on the GUI thread, only after unlock."""
from functools import lru_cache

from PySide6.QtGui import QIcon, QPixmap

from .theme_assets import application_icon_path


def _pixmap(path):
    image = QPixmap(path)
    if image.isNull():
        raise OSError(f'无法读取图片：{path}')
    return image


@lru_cache(maxsize=1)
def evernight_artwork():
    """Publish a complete set or raise OSError, leaving the ordinary theme intact."""
    icon = application_icon_path(True)
    if QIcon(icon).pixmap(32, 32).isNull():
        raise OSError(f'无法读取图标：{icon}')
    names = ('evey-decoration-folded.png', 'evey-decoration-upright.png', 'evey-decoration-wide.png')
    return {name: _pixmap(f'./assets/app/images/evernight/{name}') for name in names}
