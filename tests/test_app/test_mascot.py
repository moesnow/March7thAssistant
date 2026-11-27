import re
from pathlib import Path

from PIL import Image
from PySide6.QtGui import QImage, QImageReader
from qfluentwidgets import qconfig, setThemeColor

from app.common.accent import EVERNIGHT_RED
from app.common.mascot import Mascot, load_mascot, mascot_path
from app.overview.greeting import SQUASH_WIDTH
from app.pages.common import is_evernight
from app.setup.rail import StepRail
from assets.scripts.prepare_mascot import EVERNIGHT, POSES, prepare
from module.overview.samples import sample_snapshot


def test_all_assets():
    directory = Path(mascot_path(Mascot.FULL)).parent
    names = {p.stem for p in directory.glob("*.webp")}
    readme = (directory / "README.md").read_text(encoding="utf-8")
    assert names == {m.value for m in Mascot} == set(POSES.values()) == set(re.findall(r"(chibi_\w+)\.webp", readme))
    assert len(names) == 16
    assert b"webp" in [bytes(fmt) for fmt in QImageReader.supportedImageFormats()]
    assert sum(p.stat().st_size for p in directory.glob("*.webp")) < 1_200_000
    for pose in Mascot:
        img = QImage(mascot_path(pose))
        assert img.hasAlphaChannel() and max(img.width(), img.height()) == 512


def test_evernight_assets():
    directory = Path(mascot_path(Mascot.FULL)).parent / "evernight"
    assert {p.stem for p in directory.glob("*.webp")} == {POSES[name] for name in EVERNIGHT}
    assert sum(p.stat().st_size for p in directory.glob("*.webp")) < 75_000 * len(EVERNIGHT)
    for asset in directory.rglob("*.webp"):
        image = QImage(str(asset))
        assert image.hasAlphaChannel() and max(image.width(), image.height()) == 512
    for state in ("ready", "running", "completed", "failed", "setup", "stopped"):
        pose = Mascot(sample_snapshot(state).greeting.mascot)
        path = Path(mascot_path(pose, evernight=True, overview=True))
        if state == "setup":
            assert path.parent == directory / "overview"
            assert Path(mascot_path(pose, evernight=True)).parent == directory
        else:
            assert path.parent == directory
        regular = Path(mascot_path(pose, overview=True))
        if state == "setup":
            assert regular == directory.parent / "overview" / "chibi_ok.webp"
            assert Path(mascot_path(pose)) == directory.parent / "chibi_ok.webp"
            full_body = QImage(str(regular))
            assert full_body.hasAlphaChannel() and 0 < full_body.width() < full_body.height() == 512
        else:
            assert regular == Path(mascot_path(pose))


def test_same_default_art_uses_same_evernight_art():
    root = Path(mascot_path(Mascot.FULL)).parent
    for pose in Mascot:
        for overview in (False, True):
            regular = Path(mascot_path(pose, overview=overview))
            themed = root / "evernight" / regular.relative_to(root)
            expected = themed if themed.is_file() else regular
            assert Path(mascot_path(pose, evernight=True, overview=overview)) == expected


def test_empty_pages_use_a_bust_and_overview_uses_a_full_figure():
    for evernight in (False, True):
        bust = QImage(mascot_path(Mascot.OK, evernight=evernight))
        overview = QImage(mascot_path(Mascot.OK, evernight=evernight, overview=True))
        assert bust.width() > bust.height() > 0
        assert overview.height() > overview.width() > 0


def test_setup_rail_keeps_march7th_in_evernight(qtbot):
    color = qconfig.get(qconfig.themeColor)
    setThemeColor(EVERNIGHT_RED, save=False)
    try:
        rail = StepRail(5)
        qtbot.addWidget(rail)
        for pose in Mascot:
            rail.setPose(pose)
            assert is_evernight() and rail.mascot.pose() is pose and not rail.mascot._evernight
            assert rail.mascot.imageRect().width() * (1 + SQUASH_WIDTH) <= rail.width()
    finally:
        setThemeColor(color, save=False)


def test_evernight_partial_and_cache(tmp_path, monkeypatch, qapp):
    source = tmp_path / "source"
    source.mkdir()
    original = Image.new("RGBA", (620, 690))
    original.paste((255, 70, 80, 255), (8, 10, 412, 610))
    original.save(source / "长夜月_全身站立.png")
    monkeypatch.chdir(tmp_path)
    dest = Path(mascot_path(Mascot.FULL)).parent
    assert mascot_path(Mascot.FULL, evernight=True) == mascot_path(Mascot.FULL)
    prepare(source, dest, evernight=True)
    path = Path(mascot_path(Mascot.FULL, evernight=True))
    assert path.parent == dest / "evernight"
    first = path.read_bytes()
    prepare(source, dest, evernight=True)
    assert path.read_bytes() == first
    assert mascot_path(Mascot.OK, evernight=True) == mascot_path(Mascot.OK)
    pix = load_mascot(Mascot.FULL, 120, 1.5, evernight=True)
    assert pix.height() == 180 and pix.devicePixelRatio() == 1.5
    assert load_mascot(Mascot.FULL, 120, 1.5, evernight=True).cacheKey() == pix.cacheKey()
