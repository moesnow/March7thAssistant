from app.common.mascot import load_mascot
from app.components.mascot_dialog import MASCOT_HEIGHT
from app.pages.common import is_evernight


def assert_pose(pixmap, pose):
    assert pixmap is not None and not pixmap.isNull()
    expected = load_mascot(pose, MASCOT_HEIGHT, pixmap.devicePixelRatio(), evernight=is_evernight())
    assert pixmap.toImage() == expected.toImage()
