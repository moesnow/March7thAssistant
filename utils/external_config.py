"""Keep external tool settings across tool updates and respect edits made in their own UI."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import tempfile

from utils import paths
from utils.data_files import atomic_json, file_hash


def _hash(file):
    return file_hash(file).hex() if file.is_file() else None


def _copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
        tmp = Path(stream.name)
    try:
        shutil.copyfile(source, tmp)
        if file_hash(source) != file_hash(tmp):
            raise OSError(f"复制期间配置发生了变化：{source}")
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


@contextmanager
def tool_settings(kind, directory, logger, *, collect_on_exit=True):
    current = paths.layout()
    if current.mode == "legacy":
        yield
        return
    local = Path(directory).resolve()
    central = current.root / "external" / kind
    state_file = central / ".sync.json"
    before = {}
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        known = state.setdefault(str(local), {})
        if not isinstance(known, dict):
            raise ValueError("同步记录格式无效")
    except FileNotFoundError:
        known = {}
        state = {str(local): known}
    except (OSError, ValueError, AttributeError) as exc:
        logger.warning(f"无法读取上次同步记录，优先保留工具目录中的配置：{exc}")
        known = dict.fromkeys(paths.EXTERNAL[kind])
        state = {str(local): known}

    def save_state():
        try:
            atomic_json(state_file, state)
        except OSError as exc:
            logger.warning(f"无法记录外部工具配置的同步状态：{exc}")

    for name in paths.EXTERNAL[kind]:
        tool, saved = local / name, central / name
        try:
            old = before[name] = _hash(tool)
            stored = _hash(saved)
            if old != stored:
                if old and (stored is None or name in known and old != known[name]):
                    _copy(tool, saved)
                elif stored:
                    _copy(saved, tool)
            before[name] = known[name] = _hash(tool)
        except (OSError, ValueError) as exc:
            logger.warning(f"外部工具配置同步失败，本次使用工具目录中的 {name}：{exc}")
    save_state()
    if not collect_on_exit:
        # A detached GUI can save after the launcher returns. Keep this baseline for the next run.
        yield
        return
    try:
        yield
    finally:
        for name, previous in before.items():
            try:
                tool = local / name
                after = _hash(tool)
                if after and after != previous:
                    _copy(tool, central / name)
                    known[name] = after
                    save_state()
            except (OSError, ValueError) as exc:
                logger.warning(f"未能收回外部工具配置，{name} 仍在工具目录：{exc}")


def reset(kind, directory):
    current = paths.layout()
    central = current.storage / "external" / kind
    targets = [Path(directory) / name for name in paths.EXTERNAL[kind]]
    targets += [central / name for name in (*paths.EXTERNAL[kind], ".sync.json")]
    failures = []
    for target in targets:
        try:
            target.unlink(missing_ok=True)
        except OSError as exc:
            failures.append(str(exc))
    return failures
