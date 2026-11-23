import zipfile
from unittest.mock import Mock

import pytest

from module.update.update_engine import UpdateEngine, UpdateError
from utils import paths


@pytest.mark.parametrize("package", ["update", "March7thAssistant_full"])
def test_package_preserves_data_through_cover_and_cleanup(tmp_path, monkeypatch, package):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(paths, "_layout", paths.select(tmp_path))
    data = tmp_path / paths.USERDATA
    data.mkdir()
    (data / "saved").write_bytes(b"original")
    engine = UpdateEngine(logger=Mock())
    engine.set_package('unused-local-fixture', package + '.zip')
    with zipfile.ZipFile(engine.download_file_path, "w") as archive:
        archive.writestr(package + "/userdata/saved", b"stale")
        archive.writestr(package + "/UserData/unwanted", b"extra")
        archive.writestr(package + "/program.txt", b"new")
    engine.extract_file()
    engine.cover_folder()
    engine.cleanup()
    assert (tmp_path / "program.txt").read_bytes() == b"new"
    assert (data / "saved").read_bytes() == b"original"
    assert not (data / "unwanted").exists()
    assert not (tmp_path / "UserData/unwanted").exists()


def test_finalize_rejects_data_root_as_staging(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(paths, "_layout", paths.select(tmp_path))
    root = paths.layout().storage
    root.mkdir()
    config = root / paths.CONFIG
    config.write_bytes(b"keep")
    engine = UpdateEngine(logger=Mock())
    engine.set_local_package("update.zip", str(root))
    with pytest.raises(UpdateError):
        engine.cover_folder()
    with pytest.raises(UpdateError):
        engine.cleanup()
    assert config.read_bytes() == b"keep"


def test_flat_package_keeps_other_cache_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(paths, "_layout", paths.select(tmp_path))
    engine = UpdateEngine(logger=Mock())
    engine.set_package("local-fixture", "update.zip")
    control = paths.layout().storage / "cache/paused.control"
    control.write_bytes(b"pause")
    with zipfile.ZipFile(engine.download_file_path, "w") as archive:
        archive.writestr("program.txt", b"new")
    engine.extract_file()
    engine.cover_folder()
    engine.cleanup()
    assert control.read_bytes() == b"pause"
    assert (tmp_path / "program.txt").read_bytes() == b"new"
