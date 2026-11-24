"""一个安装中的本地账号。任务只写账号自己的状态，列表由界面管理。"""

import base64
from datetime import date, datetime
import json
import locale
import os
import re
from pathlib import Path

from module.localization import tr
from utils import paths
from utils.data_files import data_lock, linked, move, stamp
from utils.encryption import wdp_decrypt, wdp_encrypt
from .files import read_yaml, retry, write_bytes, write_yaml

_UID = re.compile(r"[0-9]{1,20}", re.ASCII)
_BROKEN = re.compile(r"\.broken-(\d{8})_")
# 账号页显示的问题。损坏的副本只提醒几天，之后仍留在原处。
BROKEN_DAYS = 7
ISSUES = {
    "index_copy": "账号列表曾经损坏，已按登录快照重建，损坏的副本留在账号文件夹里",
    "copy": "{account} 的 {name} 曾经损坏，已从空数据开始，损坏的副本留在账号文件夹里",
    "name": "旧账号名称无法读取，可重新命名",
    "snapshot": "部分登录快照无法校验，请在客户端重新保存",
    "snapshot_backup": "旧快照损坏，已保留此前可用的备份",
    "readonly": "暂时无法整理账号目录，本次按只读方式显示资料",
    "legacy": "部分旧账号文件尚未转换，原件已保留，下次打开时重试",
    "orphan": "旧账号缺少登录快照，相关文件已保留",
    "damaged": "{name} 损坏，已按空数据读取",
    "busy": "{name} 暂时无法留存损坏副本，请稍后重试",
}
_LEGACY_KEY = b"TI4ftRSDaP63kBxxoLoZ5KpVmRBz00JikzLNweryzZ4wecWJxJO9tbxlH9YDvjAr"


def uid_string(value):
    uid = str(value)
    if not _UID.fullmatch(uid):
        raise ValueError("账号 UID 格式无效")
    return uid


def masked_uid(value):
    uid = uid_string(value)
    return uid[:1] + "•••" + (uid[-3:] if len(uid) > 4 else "")


def _legacy_xor(data):
    return bytes(c ^ _LEGACY_KEY[i % len(_LEGACY_KEY)] for i, c in enumerate(data))


def xor_encrypt_to_base64(text):
    return base64.b64encode(_legacy_xor(text.encode())).decode("ascii")


def xor_decrypt_from_base64(text):
    return _legacy_xor(base64.b64decode(text, validate=True)).decode("utf-8")


def _account(uid, **values):
    return dict(
        {
            "uid": uid,
            "name": masked_uid(uid),
            "server": "cn",
            "rotate": True,
            "plan": "shared",
            "game_path": "",
            "refresh_hour": None,
            "auto_login": False,
        },
        **values,
    )


def _valid_index(data):
    items = data.get("accounts")
    if not isinstance(items, list) or type(data.get("enabled", False)) is not bool:
        return False
    if any(data.get(key) is not None and not isinstance(data[key], str) for key in ("current", "inherited")):
        return False
    ids = set()
    for item in items:
        if not isinstance(item, dict) or not all(isinstance(k, str) for k in item):
            return False
        uid = item.get("uid")
        if not isinstance(uid, str) or not _UID.fullmatch(uid) or uid in ids:
            return False
        ids.add(uid)
        if not _valid_fields(item):
            return False
    return True


def _valid_fields(item):
    hour = item.get("refresh_hour")
    return (
        isinstance(item.get("name", ""), str)
        and isinstance(item.get("game_path", ""), str)
        and item.get("plan", "shared") in ("shared", "independent")
        and item.get("server", "cn") in ("cn", "global")
        and type(item.get("rotate", True)) is bool
        and type(item.get("auto_login", False)) is bool
        and (hour is None or type(hour) is int and 0 <= hour <= 23)
    )


class AccountStore:
    def __init__(self, root=None, *, role="observer", storage=None):
        self.root = Path(paths.accounts_dir() if root is None else root)
        self.storage = Path(storage or (paths.layout().storage if root is None else self.root.parent))
        if role not in ("ui", "task", "observer"):
            raise ValueError("未知的账号数据访问角色")
        self.role = "observer" if paths.readonly_role() or os.getenv(paths.RECOVERY_ENV) == "1" else role
        self.issues = []

    def issue(self, code, **args):
        entry = (code, tuple(sorted(args.items())))
        if entry not in self.issues:
            self.issues.append(entry)

    @staticmethod
    def _recently_broken(folder, name):
        today = date.today()
        for file in folder.glob(name + ".broken-*"):
            found = _BROKEN.search(file.name)
            try:
                if found and (today - datetime.strptime(found[1], "%Y%m%d").date()).days < BROKEN_DAYS:
                    return True
            except ValueError:
                continue
        return False

    def problems(self):
        """本次遇到的问题，加上前几天别的进程修复过的损坏文件。按当前语言返回，供界面提示。"""
        found = list(self.issues)
        if self.root.is_dir() and not linked(self.root):
            if self._recently_broken(self.root, "accounts.yaml"):
                found.append(("index_copy", ()))
            for row in self._read_index()[0]["accounts"]:
                folder = self.path(row["uid"], "state.yaml").parent
                for name in ("state.yaml", "plan.yaml"):
                    if self._recently_broken(folder, name):
                        found.append(("copy", (("account", row["name"]), ("name", name))))
        return tuple(dict.fromkeys(tr(ISSUES[code]).format(**dict(args)) for code, args in found))

    def _require(self, *, ui=False):
        if self.role == "observer" or ui and self.role != "ui":
            raise PermissionError("当前进程只能读取这项账号数据")
        if linked(self.root):
            raise ValueError("账号目录不能是链接")

    def lock(self):
        return data_lock(self.storage, timeout=4, name=".accounts.lock")

    def path(self, uid, name):
        if name not in ("login.reg", "plan.yaml", "state.yaml", "secret.bin"):
            raise ValueError("未知的账号文件")
        folder = self.root / uid_string(uid)
        path = folder / name
        if any(linked(p) for p in (self.root, folder, path)):
            raise ValueError("账号数据不能指向其他目录")
        return path

    @property
    def index_path(self):
        return self.root / "accounts.yaml"

    def _name(self, uid):
        path = self.root / (uid + ".name")
        if linked(path):
            raise ValueError("账号名称文件不能是链接")
        try:
            data = retry(path.read_bytes)
        except FileNotFoundError:
            return masked_uid(uid)
        for encoding in ("utf-8-sig", locale.getencoding(), "gb18030"):
            try:
                return data.decode(encoding).strip() or masked_uid(uid)
            except UnicodeError:
                continue
        self.issue("name")
        return masked_uid(uid)

    def _recovered(self, uid, path):
        from .snapshots import SnapshotError, snapshot_server

        row = _account(uid)
        try:
            row["server"] = snapshot_server(retry(path.read_bytes), uid)
        except SnapshotError:
            self.issue("snapshot")
        return row

    def _read_index(self, repair=False):
        if linked(self.root):
            raise ValueError("账号目录不能是链接")
        raw = read_yaml(
            self.index_path, repair=repair, issue=self.issue, validate=_valid_index, writing=repair
        )
        data = {"schema": 1, "enabled": False, "current": None, "inherited": None, **raw}
        rows = {item["uid"]: _account(**item) for item in data.get("accounts", [])}
        legacy = set()
        if self.root.exists():
            for entry in sorted(self.root.iterdir()):
                if linked(entry):
                    continue
                if entry.suffix in (".reg", ".name", ".acc") and _UID.fullmatch(entry.stem):
                    legacy.add(entry.stem)
                elif _UID.fullmatch(entry.name) and self.path(entry.name, "login.reg").is_file():
                    if entry.name not in rows:
                        rows[entry.name] = self._recovered(entry.name, self.path(entry.name, "login.reg"))
        for uid in sorted(legacy):
            reg = self.root / (uid + ".reg")
            if reg.is_file() and not linked(reg) and uid not in rows:
                rows[uid] = self._recovered(uid, reg)
                rows[uid]["name"] = self._name(uid)
                rows[uid]["auto_login"] = (self.root / (uid + ".acc")).is_file()
        # 为旧账号和新发现的快照分配固定头像色；已有颜色不随列表顺序变化。
        colors = [row.get("color") for row in rows.values()]
        used = [colors.count(i) for i in range(6)]
        for row in rows.values():
            if type(row.get("color")) is not int or not 0 <= row["color"] < 6:
                color = used.index(min(used))
                row["color"] = color
                used[color] += 1
        data["accounts"] = list(rows.values())
        if data.get("current") not in rows:
            data["current"] = next(iter(rows), None)
        if not rows:
            data["enabled"] = False
        return data, legacy, raw

    def index(self):
        if self.role != "ui" or not self.root.exists():
            return self._read_index()[0]
        try:
            return self._maintain_index()
        except OSError:
            self.issue("readonly")
            return self._read_index()[0]

    def _maintain_index(self):
        with self.lock():
            data, legacy, raw = self._read_index(repair=True)
            archive = self.storage / "backup" / ("账号转换前_" + stamp())
            for uid in sorted(legacy):
                try:
                    self._migrate(uid, data, archive)
                except (OSError, ValueError, UnicodeError, AttributeError):
                    self.issue("legacy")
            if data != raw and (raw or data["accounts"] or self.issues):
                write_yaml(self.index_path, data)
            return data

    def _migrate(self, uid, index, archive):
        row = next((item for item in index["accounts"] if item["uid"] == uid), None)
        if row is None:
            self.issue("orphan")
            return
        old = self.root / (uid + ".reg")
        snapshot = self.path(uid, "login.reg")
        if old.is_file() and not linked(old):
            from .snapshots import snapshot_server

            raw = retry(old.read_bytes)
            if not snapshot.exists():
                row["server"] = snapshot_server(raw, uid)
                write_bytes(snapshot, raw)
            else:
                # Existing destination is authoritative only if its UID can be confirmed.
                row["server"] = snapshot_server(retry(snapshot.read_bytes), uid)
        name = self.root / (uid + ".name")
        if name.is_file() and row["name"] == masked_uid(uid):
            row["name"] = self._name(uid)
        # Publish metadata before retiring either source. Re-entry after any rename is safe.
        if old.exists() or name.exists():
            write_yaml(self.index_path, index)
        for source in (old, name):
            if source.is_file() and not linked(source) and snapshot.is_file():
                retry(lambda: move(source, archive / source.name))
        acc = self.root / (uid + ".acc")
        if not acc.is_file() or linked(acc):
            return
        text = xor_decrypt_from_base64(retry(acc.read_bytes).strip().decode("ascii"))
        login, separator, password = text.partition(",")
        if not separator or not login or not password:
            raise ValueError("旧密码文件无法转换")
        target = self.path(uid, "secret.bin")
        if not target.exists():
            self._save_secret(uid, login, password)
        if self.credentials(uid) != (login, password):
            raise ValueError("新旧密码不一致，请重新保存")
        row["auto_login"] = True
        write_yaml(self.index_path, index)
        retry(acc.unlink)

    def edit_index(self, change):
        self._require(ui=True)
        self.index()
        with self.lock():
            data, _, _ = self._read_index(repair=True)
            change(data)
            if not _valid_index(data):
                raise ValueError("账号设置无效")
            write_yaml(self.index_path, data)
            return data

    def account(self, uid):
        uid = uid_string(uid)
        return next((a for a in self.index()["accounts"] if a["uid"] == uid), None)

    def update(self, uid, **fields):
        uid = uid_string(uid)
        if fields.keys() - {"name", "rotate", "plan", "game_path", "refresh_hour", "auto_login", "server"}:
            raise ValueError("未知的账号设置")
        if "name" in fields and not fields["name"].strip():
            raise ValueError("账户名不能为空")

        def change(data):
            row = next((a for a in data["accounts"] if a["uid"] == uid), None)
            if row is None:
                raise ValueError("找不到账号")
            if "game_path" in fields:
                path = self.path(uid, "state.yaml")
                state = read_yaml(path, repair=True, issue=self.issue, writing=True)
                if "detected_game_path" in state:
                    del state["detected_game_path"]
                    write_yaml(path, state)
            row.update(fields)

        self.edit_index(change)

    def reorder(self, uids):
        order = list(map(uid_string, uids))

        def change(data):
            rows = {a["uid"]: a for a in data["accounts"]}
            if len(rows) != len(order) or set(order) != rows.keys():
                raise ValueError("账号列表已变化，请刷新后再排序")
            data["accounts"] = [rows[uid] for uid in order]

        self.edit_index(change)

    def set_current(self, uid):
        uid = uid_string(uid)

        def change(data):
            if not any(a["uid"] == uid for a in data["accounts"]):
                raise ValueError("找不到账号")
            data["current"] = uid

        self.edit_index(change)

    def read(self, uid, name):
        path = self.path(uid, name)
        if name not in ("plan.yaml", "state.yaml"):
            raise ValueError("只支持读取方案和状态")
        writable = self.role in ("ui", "task")
        if not writable or not path.exists():
            return read_yaml(path, issue=self.issue)
        try:
            with self.lock():
                return read_yaml(path, repair=True, issue=self.issue)
        except OSError:
            return read_yaml(path, issue=self.issue)

    def modify(self, uid, name, change):
        if name not in ("plan.yaml", "state.yaml"):
            raise ValueError("只支持修改方案和状态")
        self._require()
        path = self.path(uid, name)
        with self.lock():
            if not any(a["uid"] == uid_string(uid) for a in self._read_index()[0]["accounts"]):
                raise ValueError("账号已经移除，本次没有写入")
            data = read_yaml(path, repair=True, issue=self.issue, writing=True)
            change(data)
            write_yaml(path, data)
            return data

    def _save_secret(self, uid, login, password):
        if not login or not password:
            raise ValueError("账号和密码不能为空")
        raw = json.dumps([login, password], ensure_ascii=False).encode("utf-8")
        encoded = wdp_encrypt(raw)
        if wdp_decrypt(encoded) != raw:
            raise ValueError("Windows 加密校验失败")
        write_bytes(self.path(uid, "secret.bin"), encoded)

    def _legacy_credentials(self, uid):
        """还没打开过账号页时，旧密码没有转换。任务进程直接读旧文件，转换仍由界面完成。"""
        path = self.root / (uid_string(uid) + ".acc")
        if linked(path):
            return None, None
        try:
            text = xor_decrypt_from_base64(retry(path.read_bytes).strip().decode("ascii"))
        except (OSError, ValueError):
            return None, None
        login, separator, password = text.partition(",")
        return (login, password) if separator and login and password else (None, None)

    def credentials(self, uid):
        if not self.path(uid, "secret.bin").exists():
            return self._legacy_credentials(uid)
        try:
            raw = retry(self.path(uid, "secret.bin").read_bytes)
            pair = json.loads(wdp_decrypt(raw))
            if isinstance(pair, list) and len(pair) == 2 and all(isinstance(v, str) and v for v in pair):
                return tuple(pair)
        except (OSError, ValueError, UnicodeError, AttributeError):
            pass
        return None, None

    def password_status(self, uid):
        if not self.path(uid, "secret.bin").exists() and not (self.root / (uid_string(uid) + ".acc")).exists():
            return "missing"
        return "saved" if self.credentials(uid)[0] else "resave"

    def save_credentials(self, uid, login, password, *, auto_login=True):
        def change(data):
            row = next((a for a in data["accounts"] if a["uid"] == uid_string(uid)), None)
            if row is None:
                raise ValueError("找不到账号")
            self._save_secret(uid, login, password)
            row["auto_login"] = bool(auto_login)

        self.edit_index(change)

    def clear_credentials(self, uid):
        def change(data):
            row = next((a for a in data["accounts"] if a["uid"] == uid_string(uid)), None)
            if row is None:
                raise ValueError("找不到账号")
            for path in (self.path(uid, "secret.bin"), self.root / (uid_string(uid) + ".acc")):
                retry(lambda: path.unlink(missing_ok=True))
            row["auto_login"] = False

        self.edit_index(change)

    def delete(self, uid):
        uid = uid_string(uid)

        def change(data):
            row = next((a for a in data["accounts"] if a["uid"] == uid), None)
            if row is None:
                return
            # Remove passwords before moving anything to the recovery directory.
            for file in (self.path(uid, "secret.bin"), self.root / (uid + ".acc")):
                retry(lambda: file.unlink(missing_ok=True))
            archive = self.storage / "backup" / "已删除账号" / (uid + "_" + stamp())
            for suffix in (".reg", ".name"):
                source = self.root / (uid + suffix)
                if source.exists():
                    move(source, archive / source.name)
            directory = self.path(uid, "login.reg").parent
            if directory.exists():
                move(directory, archive / uid)
            data["accounts"].remove(row)
            if data["current"] == uid:
                data["current"] = next((a["uid"] for a in data["accounts"]), None)
            if not data["accounts"]:
                data["enabled"] = False

        self.edit_index(change)
