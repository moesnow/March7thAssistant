"""Load bundled portraits with their backgrounds already baked into the images."""
from functools import lru_cache
from pathlib import Path

from PySide6.QtGui import QPixmap


_IMAGE_ROOT = Path('./assets/app/images')
_DARK_PORTRAITS = {
    str((_IMAGE_ROOT / f'{name}.jpg').resolve()): str(_IMAGE_ROOT / 'dark' / f'{name}.png')
    for name in ('March7th', 'JingYuan', 'Yanqing', 'Herta', 'SilverWolf', 'Bronya')
}


@lru_cache(maxsize=12)  # Six ordinary light/dark pairs.
def _builtin_portrait_artwork(path):
    return QPixmap(path)


def portrait_artwork(path, dark):
    source = str(Path(path).resolve()) if path else path
    if source in _DARK_PORTRAITS:
        return _builtin_portrait_artwork(_DARK_PORTRAITS[source] if dark else source)
    # Custom files are re-read when cards are rebuilt, including edits in place.
    return QPixmap(path)


def application_icon_path(evernight=False):
    """Keep the original March 7th icon until the Easter egg is displayed."""
    if not evernight:
        return './assets/logo/March7th.ico'
    return './assets/logo/evernight/icon.ico'
