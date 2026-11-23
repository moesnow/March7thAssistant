"""Undo an interrupted multi-UID import before exposing its files. Caller owns the data lock."""
import hashlib
import io
import json

from module.localization import tr
from utils import paths
from utils.data_files import install_stream


PENDING = ".import-pending.json"


def checksum(raw):
    return hashlib.sha256(raw).hexdigest() if raw is not None else None


def recover_import(layout):
    directory = layout.path(paths.GACHA)
    marker = directory / PENDING
    try:
        journal = json.loads(marker.read_bytes())
    except FileNotFoundError:
        return
    for entry in reversed(journal["started"]):
        target = directory / entry["file"]
        if not paths.UID_FILE.fullmatch(entry["file"]):
            raise ValueError(tr("抽卡导入恢复记录无效：{path}").format(path=marker))
        current = checksum(target.read_bytes()) if target.is_file() else None
        if current == entry["before"]:
            continue
        if current != entry["after"]:
            raise ValueError(tr("导入中断后文件又发生了变化，请核对原件与备份：{path}").format(path=target))
        if entry["before"] is None:
            target.unlink()
            continue
        name = entry["backup"]
        if not paths.UID_BACKUP.fullmatch(name) or not name.startswith(target.name + "."):
            raise ValueError(tr("抽卡导入备份名称无效：{path}").format(path=marker))
        backup = directory / name
        original = backup.read_bytes()
        if checksum(original) != entry["before"]:
            raise ValueError(tr("抽卡记录备份校验失败：{path}").format(path=backup))
        install_stream(target, io.BytesIO(original))
    marker.unlink()
