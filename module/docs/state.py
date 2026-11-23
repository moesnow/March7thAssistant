"""Per-installation release badge. One short SQLite transaction also covers concurrent readers."""
from contextlib import closing
from pathlib import Path
import logging
import sqlite3

from utils import paths
from utils.version import Version
from .catalog import current_version

log = logging.getLogger(__name__)


def _seen(version, path, mark):
    version = current_version() if version is None else version
    try:
        current = Version(version, strict=True)
        file = Path(path) if path is not None else paths.layout().storage / "state" / "help.sqlite3"
        file.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(file, timeout=0.05)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS changelog (id INTEGER PRIMARY KEY, seen TEXT NOT NULL)")
            saved = db.execute("SELECT seen FROM changelog WHERE id=1").fetchone()
            if saved is None or mark:
                db.execute("BEGIN IMMEDIATE")
                db.execute("INSERT OR IGNORE INTO changelog VALUES (1, ?)", (version,))
                previous = Version(db.execute("SELECT seen FROM changelog WHERE id=1").fetchone()[0], strict=True)
                if mark and current > previous:
                    db.execute("UPDATE changelog SET seen=? WHERE id=1", (version,))
                return True if mark else current > previous
            return current > Version(saved[0], strict=True)
    except (OSError, ValueError, sqlite3.Error) as exc:
        log.warning("无法读写帮助页更新日志的已读状态：%s", exc)
        return False


def changelog_is_new(version=None, path=None):
    return _seen(version, path, False)


def mark_changelog_seen(version=None, path=None):
    return _seen(version, path, True)
