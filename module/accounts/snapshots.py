"""登录快照。只允许选定客户端的一节数据，校验和导入使用同一份字节。"""

import logging
import os
import re
import subprocess
import time

from utils.registry import gameaccount as registry
from .files import retry, staging, write_bytes
from .store import uid_string


class SnapshotError(ValueError):
    def __init__(self, reason, message):
        self.reason = reason
        super().__init__(message)


def snapshot_server(raw, uid):
    invalid = SnapshotError("invalid_snapshot", "登录快照损坏或不属于所选账号")
    try:
        text = raw.decode("utf-16") if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else raw.decode("utf-8-sig")
    except UnicodeError:
        raise invalid from None
    text = text.replace("\r\n", "\n")
    if any(ord(c) < 32 and c not in "\n\t" for c in text):
        raise invalid
    lines = iter(text.split("\n"))
    if next(lines, "") != "Windows Registry Editor Version 5.00":
        raise invalid
    sections = {
        "[hkey_current_user\\" + p.casefold() + "]": server
        for p, server in ((registry.reg_path_cn, "cn"), (registry.reg_path_oversea, "global"))
    }
    server = seen_uid = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if server is None:
            server = sections.get(line.casefold())
            if not server:
                raise invalid
            continue
        pair = re.fullmatch(r'"((?:[^"\\]|\\["\\])*)"=(.*)', line)
        if not pair:
            raise invalid
        name, value = pair.groups()
        if value.startswith("hex"):
            while value.endswith("\\"):
                more = next(lines, "").strip()
                if not re.fullmatch(r"[0-9a-fA-F,]+\\?", more):
                    raise invalid
                value = value[:-1] + more
            if not re.fullmatch(r"hex(?:\([0-9a-fA-F]+\))?:(?:[0-9a-fA-F]{2}(?:,[0-9a-fA-F]{2})*)?", value):
                raise invalid
        elif not re.fullmatch(r'dword:[0-9a-fA-F]{8}|"(?:[^"\\]|\\["\\])*"', value):
            raise invalid
        if name.casefold() == registry.uid_key.casefold():
            if seen_uid is not None:
                raise invalid
            if value.startswith("dword:"):
                seen_uid = str(int(value[6:], 16))
            elif value.startswith("hex(b):"):
                seen_uid = str(int.from_bytes(bytes.fromhex(value[7:].replace(",", "")), "little"))
            else:
                seen_uid = value.strip('"')
    if not server or seen_uid != uid_string(uid):
        raise invalid
    return server


def _idle():
    from utils.temporary_graphics import (
        WindowsGraphicsRegistry,
        backup_exists,
        backup_path,
        recover_temporary_graphics,
        restore_temporary_graphics,
    )

    if WindowsGraphicsRegistry().game_running():
        raise SnapshotError("game_running", "请先关闭游戏，再切换登录")
    if not restore_temporary_graphics(final=True):
        raise SnapshotError("graphics_pending", "临时画质尚未恢复，请稍后再试")
    recover_temporary_graphics(logging.getLogger(__name__))
    if backup_exists(backup_path()):
        raise SnapshotError("graphics_pending", "临时画质尚未恢复，请稍后再试")


def _capture(store, uid, game_path):
    """导出当前登录并替换快照，留一份上一版。调用方已确认登录的就是这个账号。"""
    target = store.path(uid, "login.reg")
    with store.lock(), staging(target) as tmp:
        try:
            registry.gamereg_export(str(tmp), game_path)
            data = tmp.read_bytes()
            server = snapshot_server(data, uid)
            if registry.server_for_path(game_path) != server:
                raise SnapshotError("invalid_snapshot", "导出的登录快照与所选客户端不符")
            if registry.gamereg_uid(game_path) != int(uid):
                raise SnapshotError("account_mismatch", "保存期间登录账号发生变化")
            if target.is_file():
                previous = retry(target.read_bytes)
                try:
                    snapshot_server(previous, uid)
                except SnapshotError:
                    store.issue("snapshot_backup")
                else:
                    write_bytes(target.with_suffix(".reg.bak"), previous)
            write_bytes(target, data)
        except (OSError, subprocess.SubprocessError):
            raise SnapshotError("registry_failed", "保存登录快照失败，请检查客户端和文件权限") from None
    return server


def _saved(store, uid):
    store.modify(uid, "state.yaml", lambda s: s.update(login_status="ready", snapshot_saved_at=time.time()))


def save_current(store, game_path=None, *, expected_uid=None):
    store._require(ui=True)
    uid = registry.gamereg_uid(game_path)
    if uid is None:
        raise SnapshotError("account_no_login", "未找到已登录的游戏账号")
    uid = uid_string(uid)
    if expected_uid is not None and uid != str(expected_uid):
        raise SnapshotError("account_mismatch", "当前登录的 UID 与所选账号不符")
    fields = {"server": _capture(store, uid, game_path)}
    if game_path:
        fields["game_path"] = os.fspath(game_path)
    store.update(uid, **fields)
    _saved(store, uid)
    return uid


def renew(store, uid, game_path):
    """任务进程更新已有的快照。只在本次运行核对过这个账号之后调用，不新建快照、不改账号列表。"""
    store._require()
    uid = uid_string(uid)
    if not store.path(uid, "login.reg").is_file() or registry.gamereg_uid(game_path) != int(uid):
        return False
    _capture(store, uid, game_path)
    _saved(store, uid)
    return True


def _load(store, uid, game_path):
    """读出并校验快照，确认它属于这个账号、对应这个客户端。"""
    try:
        data = retry(store.path(uid, "login.reg").read_bytes)
    except FileNotFoundError:
        raise SnapshotError("missing_snapshot", "账号没有登录快照") from None
    server = snapshot_server(data, uid)
    resolved = registry.get_reg_path(game_path)
    expected = registry.reg_path_cn if server == "cn" else registry.reg_path_oversea
    if not resolved or resolved.casefold() != expected.casefold():
        raise SnapshotError("account_server_mismatch", "请为这个账号设置对应服务器的客户端")
    return data


def check(store, uid, game_path):
    """切号前的检查：快照能用才值得去关游戏。"""
    try:
        _load(store, uid_string(uid), game_path)
    except OSError:
        raise SnapshotError("registry_failed", "登录快照暂时无法读取") from None


def restore(store, uid, game_path=None, *, ensure_idle=None):
    """把快照写回游戏注册表，只改登录：本机的画质、分辨率和按键写回原值。已经是目标账号时返回 False。"""
    store._require()
    uid = uid_string(uid)
    try:
        with store.lock():
            data = _load(store, uid, game_path)
            (ensure_idle or _idle)()
            if registry.gamereg_uid(game_path) == int(uid):
                return False
            try:
                original = registry.local_settings(game_path)
            except FileNotFoundError:
                original = {}
            with staging(store.path(uid, "login.reg")) as tmp:
                write_bytes(tmp, data)
                try:
                    registry.gamereg_import(str(tmp))
                finally:
                    registry.restore_settings(game_path, original)
            if registry.gamereg_uid(game_path) != int(uid):
                raise SnapshotError("account_mismatch", "恢复快照后登录账号不符，请手动登录")
            return True
    except (OSError, subprocess.SubprocessError):
        raise SnapshotError("registry_failed", "恢复登录快照或本机游戏设置失败") from None


def switch_login(store, uid, game_path=None, *, ensure_idle=None):
    store._require(ui=True)
    uid = uid_string(uid)
    row = store.account(uid)
    if not row:
        raise SnapshotError("missing_snapshot", "账号没有登录快照")
    if game_path is None:
        from .layers import own_game_path

        game_path = own_game_path(row, store.read(uid, "state.yaml")) or None
    return restore(store, uid, game_path, ensure_idle=ensure_idle)


def clear_login(store, game_path=None):
    store._require(ui=True)
    _idle()
    registry.gamereg_delete_all(game_path)
