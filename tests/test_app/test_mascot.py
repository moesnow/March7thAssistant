import re
from pathlib import Path

from PIL import Image
from PySide6.QtGui import QImage, QImageReader

from app.common.mascot import Mascot, load_mascot, mascot_path
from assets.scripts.prepare_mascot import POSES, prepare


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


def test_evernight_partial_and_cache(tmp_path, monkeypatch, qapp):
    source = tmp_path / "source"
    source.mkdir()
    original = Image.new("RGBA", (620, 690))
    original.paste((255, 70, 80, 255), (8, 10, 412, 610))
    original.save(source / "全身站立.png")
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
