"""账号文件的原子发布和有限占用重试。调用方在修改前持有跨进程锁。"""

from contextlib import contextmanager
from io import BytesIO, StringIO
import os
from pathlib import Path
import tempfile
import time

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from utils.data_files import linked, stamp


def retry(operation):
    for attempt in range(5):
        try:
            return operation()
        except OSError as error:
            if attempt == 4 or not (
                isinstance(error, PermissionError) or getattr(error, "winerror", None) in (5, 32, 33)
            ):
                raise
            time.sleep(0.03 * (attempt + 1))


@contextmanager
def staging(target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=target.parent, prefix=".account-", suffix=target.suffix, delete=False
    ) as f:
        tmp = Path(f.name)
    try:
        yield tmp
    finally:
        tmp.unlink(missing_ok=True)


def write_bytes(path, data):
    with staging(path) as tmp:
        with tmp.open("wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        retry(lambda: os.replace(tmp, path))


def plain(value):
    if isinstance(value, dict):
        return {plain(k): plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    if isinstance(value, str):
        return str(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, float):
        return float(value)
    return value


def write_yaml(path, data):
    output = StringIO()
    yaml = YAML(typ="safe", pure=True)
    yaml.default_flow_style = False
    yaml.dump(plain(data), output)
    write_bytes(path, output.getvalue().encode("utf-8"))


def read_yaml(path, *, repair=False, issue, validate=None, writing=False):
    if linked(path):
        raise ValueError("账号文件不能是链接")
    try:
        raw = retry(path.read_bytes)
    except FileNotFoundError:
        return {}
    try:
        value = YAML(typ="safe", pure=True).load(BytesIO(raw))
        if not isinstance(value, dict) or validate and not validate(value):
            raise ValueError()
        return value
    except (ValueError, TypeError, UnicodeError, YAMLError, RecursionError):
        issue("damaged", name=path.name)
        if repair:
            try:
                retry(lambda: path.rename(path.with_name(path.name + ".broken-" + stamp())))
            except OSError:
                issue("busy", name=path.name)
                if writing:
                    raise
        return {}
