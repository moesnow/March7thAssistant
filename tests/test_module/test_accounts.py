"""本地账号数据、快照、配置和身份隔离。只使用 tmp_path 和假的客户端。"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from module.accounts import layers, runtime, snapshots, switching
from module.accounts.differences import differences
from module.accounts.store import AccountStore, masked_uid, xor_encrypt_to_base64
from module.settings_registry import Scope
from utils import paths
from utils.registry import gameaccount

A, B = "100000789", "100000456"


def snapshot(uid=A, server="cn"):
    path = gameaccount.reg_path_cn if server == "cn" else gameaccount.reg_path_oversea
    return (
        f"Windows Registry Editor Version 5.00\r\n\r\n[HKEY_CURRENT_USER\\{path}]\r\n"
        f'"{gameaccount.uid_key}"=dword:{int(uid):08x}\r\n'
    ).encode("utf-16")


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.delenv("MARCH7TH_CONFIG_READONLY", raising=False)
    monkeypatch.delenv("MARCH7TH_DESKTOP_TWIN", raising=False)
    monkeypatch.delenv(paths.RECOVERY_ENV, raising=False)
    s = AccountStore(tmp_path / "accounts", role="ui")
    for uid in (A, B):
        p = s.path(uid, "login.reg")
        p.parent.mkdir(parents=True)
        p.write_bytes(snapshot(uid))
    s.index()
    return s


@pytest.fixture
def config(tmp_path, store, monkeypatch):
    from module.config.config import Config
    from module.config import config as config_module

    monkeypatch.setattr(config_module, "_DIAG_FILE", str(tmp_path / "diag.log"))
    monkeypatch.setattr(Config, "_readonly", False)
    instance = object.__new__(Config)
    Config.__init__(
        instance,
        "assets/config/version.txt",
        "assets/config/config.example.yaml",
        str(tmp_path / "config.yaml"),
    )
    instance.set_values({"control_backend": "local", "auto_update": True})
    monkeypatch.setattr(layers, "server_for_path", lambda p: "cn")
    monkeypatch.setattr(runtime, "server_for_path", lambda p: "cn")
    monkeypatch.setattr(runtime, "check_client", lambda *a, **k: None)
    monkeypatch.setattr(runtime, "running_clients", lambda: [])
    return instance


@pytest.mark.parametrize(("encoding", "system_encoding", "name"), [
    ("utf-8", "cp1252", "虚构名称"),
    ("gb18030", "utf-8", "虚构名称"),
    ("cp1252", "cp1252", "Renée"),
], ids=["utf-8", "gb18030-fallback", "windows-code-page"])
@pytest.mark.skipif(sys.platform != "win32", reason="旧密码转换使用 Windows DPAPI")
def test_legacy_conversion_and_readonly(tmp_path, encoding, system_encoding, name, monkeypatch):
    monkeypatch.setattr("module.accounts.store.locale", SimpleNamespace(getencoding=lambda: system_encoding))
    root = tmp_path / "accounts"
    root.mkdir()
    (root / (A + ".reg")).write_bytes(snapshot(server="global"))
    (root / (A + ".name")).write_bytes(name.encode(encoding))
    text = xor_encrypt_to_base64("fictional,example,only")
    (root / (A + ".acc")).write_text(text, encoding="ascii")
    observer = AccountStore(root)
    assert observer.index()["accounts"][0]["name"] == name
    assert not observer.index_path.exists()
    with pytest.raises(PermissionError):
        observer.update(A, rotate=False)
    store = AccountStore(root, role="ui")
    row = store.index()["accounts"][0]
    assert row["name"] == name and row["server"] == "global" and row["auto_login"]
    assert store.credentials(A) == ("fictional", "example,only")
    assert b"fictional" not in store.path(A, "secret.bin").read_bytes()
    assert not (root / (A + ".acc")).exists()
    assert not list((tmp_path / "backup").rglob("*.acc"))
    assert len(list((tmp_path / "backup").rglob("*.reg"))) == 1
    assert store.index()["accounts"] == [row]


def test_bad_or_missing_legacy_and_interrupted_archive(tmp_path, monkeypatch):
    import module.accounts.store as module

    root = tmp_path / "accounts"
    root.mkdir()
    (root / (A + ".reg")).write_bytes(snapshot())
    (root / (A + ".name")).write_text("样例", encoding="utf-8")
    (root / (A + ".acc")).write_text("?", encoding="ascii")
    (root / (B + ".name")).write_text("待恢复", encoding="utf-8")
    s = AccountStore(root, role="ui")
    with monkeypatch.context() as patch:
        patch.setattr(module, "move", Mock(side_effect=PermissionError))
        assert s.index()["accounts"][0]["name"] == "样例"
        assert (root / (A + ".reg")).exists()
    assert s.index()["accounts"][0]["uid"] == A
    assert not (root / (A + ".reg")).exists()
    assert (root / (A + ".acc")).exists() and (root / (B + ".name")).exists() and s.issues


def test_corruption_and_unknown_fields(store):
    store.edit_index(lambda i: i.update(added={"field": 7}))
    store.update(A, name="虚构名称", rotate=False, plan="independent")
    assert store.index()["added"] == {"field": 7}
    store.reorder([B, A])
    assert [r["uid"] for r in store.index()["accounts"]] == [B, A]
    for filename in ("state.yaml", "plan.yaml"):
        path = store.path(A, filename)
        path.write_text("[", encoding="utf-8")
        assert store.read(A, filename) == {} and list(path.parent.glob(filename + ".broken-*"))
    store.index_path.write_text("accounts: invalid", encoding="utf-8")
    assert AccountStore(store.root).index()["enabled"] is False and store.index_path.exists()
    assert len(store.index()["accounts"]) == 2 and list(store.root.glob("accounts.yaml.broken-*"))
    assert store.issues


def test_problems_are_translated_and_old_copies_expire(store):
    store.path(A, "state.yaml").write_text("[", encoding="utf-8")
    store.read(A, "state.yaml")
    name = store.account(A)["name"]
    # 另一个进程修复过的损坏文件也要提示，过几天不再提示，副本仍保留。
    fresh = AccountStore(store.root, role="ui")
    assert [text for text in fresh.problems() if name in text and "state.yaml" in text]
    copy = next(store.path(A, "state.yaml").parent.glob("state.yaml.broken-*"))
    copy.rename(copy.with_name("state.yaml.broken-20200101_000000_000000"))
    assert fresh.problems() == ()
    assert any("state.yaml" in text for text in store.problems())  # 本次遇到的一直提示


@pytest.mark.parametrize("role", ["task", "observer", "ui"])
def test_unconverted_password_still_works(tmp_path, monkeypatch, role):
    """只用命令行、还没打开过账号页的用户，登录过期时的自动填写不能失效。"""
    monkeypatch.delenv("MARCH7TH_CONFIG_READONLY", raising=False)
    root = tmp_path / "accounts"
    root.mkdir()
    (root / (A + ".reg")).write_bytes(snapshot())
    (root / (A + ".acc")).write_text(xor_encrypt_to_base64("fictional,ex,ample"), encoding="ascii")
    (root / (B + ".acc")).write_text("?", encoding="ascii")
    s = AccountStore(root, role=role)
    if role == "ui":
        monkeypatch.setattr(AccountStore, "_migrate", Mock(side_effect=OSError("占用")))
    assert s.account(A)["auto_login"] and s.credentials(A) == ("fictional", "ex,ample")
    assert s.password_status(A) == "saved" and s.password_status(B) == "resave"
    assert s.credentials(B) == (None, None) and (root / (A + ".acc")).exists()
    assert s.password_status("100000001") == "missing"


def test_concurrent_state_and_readonly(store):
    def increment(_):
        worker = AccountStore(store.root, role="task")
        worker.modify(A, "state.yaml", lambda s: s.update(count=s.get("count", 0) + 1))

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(increment, range(16)))
    assert store.read(A, "state.yaml")["count"] == 16
    with pytest.raises(PermissionError):
        AccountStore(store.root, role="task").update(A, rotate=False)
    with pytest.raises(PermissionError):
        AccountStore(store.root).modify(A, "state.yaml", lambda s: s.clear())
    assert masked_uid(A) == "1•••789"


def test_delete_never_archives_password(store):
    store.path(A, "secret.bin").write_bytes(b"test-unreadable")
    assert store.password_status(A) == "resave"
    store.delete(A)
    assert store.account(A) is None
    assert not list(store.storage.rglob("secret.bin"))
    assert list((store.storage / "backup" / "已删除账号").rglob("login.reg"))
    store.delete(A)


@pytest.mark.parametrize(
    "case", ["wrong_uid", "foreign_section", "nested", "delete", "double_uid", "truncated", "nul"]
)
def test_snapshot_validation(case):
    text = snapshot().decode("utf-16")
    bad = {
        "wrong_uid": snapshot(B),
        "foreign_section": (text + "\n[HKEY_CURRENT_USER\\Other]").encode("utf-16"),
        "nested": (text + "\n[HKEY_CURRENT_USER\\Software\\other]").encode("utf-16"),
        "delete": (text + '\n"item"=-').encode("utf-16"),
        "double_uid": (text + text.splitlines()[-1]).encode("utf-16"),
        "truncated": b"invalid",
        "nul": (text + "\0").encode("utf-16"),
    }[case]
    with pytest.raises(snapshots.SnapshotError, match="损坏") as error:
        snapshots.snapshot_server(bad, A)
    assert error.value.reason == "invalid_snapshot"


@pytest.mark.parametrize(
    "fail, expected",
    [
        (None, None),
        ("running", "game_running"),
        ("import", "registry_failed"),
        ("uid", "account_mismatch"),
        ("missing", "missing_snapshot"),
        ("bad", "invalid_snapshot"),
    ],
)
def test_manual_snapshot_restore(store, monkeypatch, fail, expected):
    actual = [B]
    monkeypatch.setattr(gameaccount, "gamereg_uid", lambda *_: int(actual[0]))
    monkeypatch.setattr(gameaccount, "get_reg_path", lambda *_: gameaccount.reg_path_cn)
    local = {"local setting": (b"fictional", 3)}
    monkeypatch.setattr(gameaccount, "local_settings", lambda _: local)
    restored = Mock()
    monkeypatch.setattr(gameaccount, "restore_settings", restored)

    def fake_import(tmp):
        assert Path(tmp).read_bytes() == snapshot()
        if fail == "import":
            raise OSError()
        if fail != "uid":
            actual[0] = A

    monkeypatch.setattr(gameaccount, "gamereg_import", fake_import)

    def idle():
        if fail == "running":
            raise snapshots.SnapshotError("game_running", "请关闭游戏")

    if fail == "missing":
        store.path(A, "login.reg").unlink()
    if fail == "bad":
        store.path(A, "login.reg").write_bytes(snapshot(B))
    if expected:
        with pytest.raises(snapshots.SnapshotError) as error:
            snapshots.switch_login(store, A, ensure_idle=idle)
        assert error.value.reason == expected
    else:
        assert snapshots.switch_login(store, A, ensure_idle=idle)
    assert restored.called == (fail in (None, "import", "uid"))


def test_manual_snapshot_publish_and_backup(store, monkeypatch):
    monkeypatch.setattr(gameaccount, "server_for_path", lambda *_: "cn")
    monkeypatch.setattr(gameaccount, "gamereg_uid", lambda *_: int(A))
    content = snapshot().decode("utf-16") + '"test"="fake"\r\n'
    monkeypatch.setattr(
        gameaccount, "gamereg_export", lambda path, _: Path(path).write_bytes(content.encode("utf-16"))
    )
    assert snapshots.save_current(store) == A
    assert store.read(A, "state.yaml")["login_status"] == "ready"
    assert store.path(A, "login.reg").with_suffix(".reg.bak").read_bytes() == snapshot()
    monkeypatch.setattr(gameaccount, "gamereg_export", lambda path, _: Path(path).write_bytes(snapshot(B)))
    with pytest.raises(snapshots.SnapshotError):
        snapshots.save_current(store)
    assert store.path(A, "login.reg").read_bytes() == content.encode("utf-16")


def test_every_template_key_has_scope(config):
    assert set(config.config) <= layers.SCOPES.keys()
    assert layers.SCOPES["redemption_code"] == Scope.GLOBAL
    assert layers.SCOPES["already_used_codes"] == Scope.STATE


@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows 本地账号开关生效")
def test_binding_isolation_plan_and_notifications(config, store, monkeypatch):
    config.set_value("last_run_timestamp", 13)
    layers.set_enabled(store, config, True, logged_uid=A)
    assert config.last_run_timestamp == 13
    events = []
    config.subscribe(lambda keys, reload: events.append((keys, reload)))
    config.bind_account(B, store=store)
    assert config.last_run_timestamp == 0
    config.save_timestamp("last_run_timestamp")
    assert config.shared_value("last_run_timestamp") == 13
    assert store.read(A, "state.yaml")["last_run_timestamp"] == 13
    assert all(not reload for _, reload in events)
    store.update(B, plan="independent", refresh_hour=0)
    config.reload_account_files()
    assert config.refresh_hour == 0
    base = config.instance_names
    first, second = list(base)[:2]
    config.set_values(
        {"power_enable": not config.power_enable, "instance_names": {**base, first: "虚构副本"}}
    )
    assert config.account_overrides()["instance_names"] == {first: "虚构副本"}
    assert any(r.subkey == first and r.account_text == "虚构副本" for r in differences(config))
    config._write_shared_values({"instance_names": {**base, second: "虚构共享"}})
    assert config.instance_names[second] == "虚构共享"
    config.restore_shared("instance_names", first)
    assert "instance_names" not in config.account_overrides()
    store.update(B, plan="shared")
    config.reload_account_files()
    assert config.power_enable == config.shared_value("power_enable")
    store.update(B, plan="independent")
    config.reload_account_files()
    assert config.power_enable != config.shared_value("power_enable")
    config.set_value("notify_level", "error")
    assert config.shared_value("notify_level") == "error"
    config.set_value("github_token", "fictional-value")
    assert "github_token" not in store.read(B, "plan.yaml")
    with config.standalone_switches(["power_enable"]):
        assert config.power_enable
    monkeypatch.setenv("MARCH7TH_AFTER_FINISH", "Exit")
    assert config.after_finish == "Exit"
    assert {p.name for p in config.account_files()} == {"accounts.yaml", "state.yaml", "plan.yaml"}


@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows 本地账号开关生效")
def test_disable_enable_merge_and_power(config, store):
    stamp = "divergent_universe_daily_completed_timestamp"
    count = stamp.replace("timestamp", "count")
    config.set_values(
        {
            stamp: 10,
            count: 3,
            "already_used_codes": ["sample-a"],
            "overview_power": {"value": 10, "timestamp": 15},
        }
    )
    store.modify(
        A, "state.yaml", lambda s: s.update({stamp: 12, count: 4, "already_used_codes": ["sample-b"]})
    )
    layers.set_enabled(store, config, True, logged_uid=A)
    assert config.get_value(count) == 4 and set(config.already_used_codes) == {"sample-a", "sample-b"}
    assert config.overview_power["value"] == 10
    config.set_value("power_plan", [["sample", "first", 3]])
    base = config.power_plan
    config.consume_power_plan([["sample", "first", 1]], base=base)
    assert config.remaining_power_plan() == [["sample", "first", 1]]
    assert config.shared_value("power_plan") == base and "power_plan" not in config.account_overrides()
    config.set_value("power_plan", [["sample", "second", 2]])
    assert config.remaining_power_plan() == config.power_plan
    config.bind_account(B, store=store)
    assert config.get_value(count) == 0 and config.already_used_codes == []
    config.set_values({stamp: 18, count: 9})
    layers.set_enabled(store, config, False, logged_uid=B)
    assert config.bound_account is None and config.get_value(count) == 9


def test_disabled_same_config_bytes(config, store):
    config.set_value("last_run_timestamp", 42)
    before = Path(config.config_path).read_bytes()
    config.bind_account(A, store=store)
    assert config.bound_account is None
    config.set_value("last_run_timestamp", 42)
    assert Path(config.config_path).read_bytes() == before
    assert not store.path(A, "state.yaml").exists()


@pytest.mark.parametrize("task", ["currencywarstemp", "divergenttemp", "workflow"])
@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows 本地账号开关生效")
def test_identity_mismatch_blocks_writes(config, store, monkeypatch, task):
    layers.set_enabled(store, config, True, logged_uid=A)
    monkeypatch.setattr(runtime, "gamereg_uid", lambda _: int(B))
    with pytest.raises(runtime.AccountError) as error:
        runtime.prepare(config, A, task, Mock(), store=AccountStore(store.root, role="task"))
    assert error.value.reason == "account_mismatch"
    with pytest.raises(runtime.AccountError):
        config.save_timestamp("last_run_timestamp")
    assert config.shared_value("last_run_timestamp") == 0 and not store.read(B, "state.yaml")
    monkeypatch.setattr(runtime, "gamereg_uid", lambda _: int(A))
    runtime.verify_ready(config)
    config.save_timestamp("last_run_timestamp")
    monkeypatch.setattr(runtime, "gamereg_uid", lambda _: int(B))
    with pytest.raises(runtime.AccountError):
        config.set_value("already_used_codes", ["fake"])
    assert not store.read(B, "state.yaml")


@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows 本地账号开关生效")
def test_unsupported_and_implicit_binding(config, store, monkeypatch):
    session = Mock()
    with pytest.raises(runtime.AccountError, match="启用多账号"):
        runtime.prepare(config, A, "daily", session, store=store)
    layers.set_enabled(store, config, True, logged_uid=A)
    monkeypatch.setattr(runtime, "gamereg_uid", lambda _: int(B))
    monkeypatch.setenv("MARCH7TH_DESKTOP_TWIN", "1")
    runtime.prepare(config, None, "daily", session, store=store)
    assert config.bound_account == B
    with pytest.raises(runtime.AccountError):
        runtime.prepare(config, B, "daily", session, store=store)
    runtime.prepare(config, A, "app_update", session, store=store)


@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows 本地账号开关生效")
def test_all_state_keys_are_account_local(config, store):
    layers.set_enabled(store, config, True, logged_uid=A)
    for key in layers.STATE_KEYS:
        original = config.shared_value(key)
        value = (
            ["fictional"]
            if key == "already_used_codes"
            else {"value": 1, "timestamp": 30}
            if key.startswith("overview_")
            else 30
        )
        config.set_value(key, value)
        assert store.read(A, "state.yaml")[key] == value
        assert config.shared_value(key) == original
    config.bind_account(B, store=store)
    assert all(config.get_value(k) == config._account_defaults[k] for k in layers.STATE_KEYS)


def test_region_of_actual_process(monkeypatch):
    import psutil
    from utils import windows_session

    proc = Mock(pid=100, info={"name": "StarRail.exe"})
    proc.exe.return_value = "second"
    monkeypatch.setattr(psutil, "process_iter", lambda attrs: [proc])
    monkeypatch.setattr(windows_session, "process_session_id", lambda pid=None: 3)
    monkeypatch.setattr(runtime, "server_for_path", lambda path: "cn" if path == "first" else "global")
    with pytest.raises(runtime.AccountError) as error:
        runtime.check_client("first", require_running=True)
    assert error.value.reason == "account_server_mismatch"
    runtime.check_client("second", require_running=True)
    monkeypatch.setattr(psutil, "process_iter", lambda attrs: [])
    with pytest.raises(runtime.AccountError) as error:
        runtime.check_client("first", require_running=True)
    assert error.value.reason == "account_no_login"


@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows 本地账号开关生效")
def test_login_expiration_and_deadline(config, store, monkeypatch):
    layers.set_enabled(store, config, True, logged_uid=A)
    monkeypatch.setattr(runtime, "gamereg_uid", lambda _: int(A))
    runtime.prepare(config, A, "daily", Mock(), store=AccountStore(store.root, role="task"))
    runtime.mark_expired(config)
    assert store.read(A, "state.yaml")["login_status"] == "expired"
    monkeypatch.setattr(runtime, "gamereg_uid", lambda _: None)
    with pytest.raises(runtime.AccountError):
        runtime.verify_ready(config, timeout=0)
    assert store.read(A, "state.yaml")["login_status"] == "expired"
    monkeypatch.setattr(runtime, "gamereg_uid", lambda _: int(A))
    runtime.verify_ready(config)
    assert store.read(A, "state.yaml")["login_status"] == "ready"


def test_name_resolution_and_options(store):
    store.update(A, name="虚构重复")
    store.update(B, name="虚构重复")
    for selector in ("虚构重复", "不存在"):
        with pytest.raises(runtime.AccountError) as error:
            runtime.resolve(store.index(), selector)
        assert error.value.exit_code == 2 and A not in str(error.value) and masked_uid(A) in str(error.value)
    assert runtime.resolve(store.index(), B)["uid"] == B


@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows 本地账号开关生效")
def test_local_view_follows_backend(config, store):
    layers.set_enabled(store, config, True, logged_uid=A)
    config.set_value("last_run_timestamp", 103)
    config.set_value("control_backend", "cloud")
    assert config.bound_account is None and config.last_run_timestamp == 0
    config.set_value("control_backend", "local")
    assert config.bound_account == A and config.last_run_timestamp == 103


@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows 本地账号开关生效")
def test_shared_updates_keep_external_changes_to_other_subkeys(config, store):
    layers.set_enabled(store, config, True, logged_uid=A)
    store.update(A, plan="independent")
    config.reload_account_files()
    original = config.instance_names
    first, second = list(original)[:2]
    store.modify(A, "plan.yaml", lambda data: data.update(instance_names={second: "虚构外部编辑"}))
    config.set_value("instance_names", {**original, first: "虚构当前编辑"})
    assert config.instance_names[second] == "虚构外部编辑"
    assert config.instance_names[first] == "虚构当前编辑"
    assert config.account_value(B, "instance_names") == original


def test_locked_file_retry_and_never_touch_readonly_corruption(store, monkeypatch):
    from module.accounts import files

    path = store.path(A, "state.yaml")
    original = files.os.replace
    attempts = []

    def busy_then_ok(tmp, target):
        if target == path:
            attempts.append(target)
            if len(attempts) < 3:
                raise PermissionError()
        original(tmp, target)

    monkeypatch.setattr(files.os, "replace", busy_then_ok)
    store.modify(A, "state.yaml", lambda d: d.update(last_run_timestamp=17))
    assert len(attempts) == 3
    path.write_bytes(b"[")
    assert AccountStore(store.root).read(A, "state.yaml") == {}
    assert path.read_bytes() == b"["


@pytest.mark.skipif(sys.platform != "win32", reason="验证 Windows DPAPI")
def test_enabled_credentials_respect_policy_and_foreign_machine(config, store, monkeypatch):
    import module.accounts.store as data

    store.save_credentials(A, "fictional", "example,only")
    monkeypatch.setattr(runtime, "AccountStore", lambda: store)
    assert runtime.load_acc_and_pwd(A) == ("fictional", "example,only")
    store.update(A, auto_login=False)
    assert runtime.load_acc_and_pwd(A) == (None, None)
    monkeypatch.setattr(data, "wdp_decrypt", Mock(side_effect=OSError))
    assert store.password_status(A) == "resave"
    store.clear_credentials(A)
    assert store.password_status(A) == "missing"


@pytest.mark.parametrize("alive,graphics_fail", [(True, False), (False, True), (False, False)])
def test_cross_client_close_is_bounded(monkeypatch, alive, graphics_fail):
    import psutil

    previous = Mock()
    monkeypatch.setattr(runtime, "running_clients", lambda: [(previous, "other")])
    monkeypatch.setattr(runtime, "server_for_path", lambda p: "global" if p == "target" else "cn")
    wait = Mock(return_value=([], [previous] if alive else []))
    monkeypatch.setattr(psutil, "wait_procs", wait)
    idle = Mock(
        side_effect=snapshots.SnapshotError("graphics_pending", "测试画质未恢复") if graphics_fail else None
    )
    monkeypatch.setattr(snapshots, "_idle", idle)
    if alive or graphics_fail:
        with pytest.raises(runtime.AccountError) as error:
            runtime.check_client("target", require_running=False, switch=True)
        assert error.value.reason == "account_switch_failed"
    else:
        runtime.check_client("target", require_running=False, switch=True)
    previous.terminate.assert_called_once()
    wait.assert_called_once_with([previous], timeout=8)


def test_instance_difference_translates_stored_names_once(monkeypatch):
    from module.accounts import differences as module
    translate = Mock(side_effect={"收容舱段": "Storage Zone", "拟造花萼（金）": "Calyx (Golden)"}.__getitem__)
    monkeypatch.setattr(module, "tr", translate)
    monkeypatch.setattr(module, "get_instance_names", lambda: {"Calyx (Golden)": {"Storage Zone": ""}})
    assert module.value_text("instance_names", "收容舱段", "拟造花萼（金）") == "Storage Zone"
    assert translate.call_count == 2


def test_team_difference_identifies_character_and_technique():
    from module.accounts.differences import value_text

    first = value_text("forgottenhall_team1", [["Asta", -1]])
    second = value_text("forgottenhall_team1", [["Asta", 1]])
    assert first != second and "秘技" in first and "1" in second


@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows 本地账号开关生效")
def test_actual_uid_is_rechecked_before_client_selection(config, store, monkeypatch):
    layers.set_enabled(store, config, True, logged_uid=A)
    check = Mock()
    monkeypatch.setattr(runtime, "check_client", check)
    monkeypatch.setattr(runtime, "gamereg_uid", lambda path: int(A))
    runtime.prepare(config, A, "daily", Mock(), store=AccountStore(store.root, role="task"))
    check.assert_not_called()
    # 启动前发现登录的是别的账号：先切号，切完仍不符才停止。
    monkeypatch.setattr(runtime, "gamereg_uid", lambda path: int(B))
    switched = Mock()
    monkeypatch.setattr(switching, "switch", switched)
    with pytest.raises(runtime.AccountError) as error:
        runtime.prepare_launch(config)
    assert error.value.reason == "account_mismatch"
    switched.assert_called_once_with(config)
    check.assert_not_called()


@pytest.fixture
def client(config, store, monkeypatch):
    """假的客户端：actual[0] 是注册表里登录的 UID，calls 记录动作顺序。"""
    layers.set_enabled(store, config, True, logged_uid=A)
    state = {"uid": B, "calls": [], "import_ok": True}

    def uid(*_):
        return int(state["uid"]) if state["uid"] else None

    for target in (gameaccount, runtime, switching):
        monkeypatch.setattr(target, "gamereg_uid", uid)
    monkeypatch.setattr(gameaccount, "get_reg_path", lambda *_: gameaccount.reg_path_cn)
    monkeypatch.setattr(gameaccount, "server_for_path", lambda *_: "cn")
    monkeypatch.setattr(gameaccount, "local_settings", lambda _: {"画质": (b"1", 3)})
    monkeypatch.setattr(gameaccount, "restore_settings", lambda *_: state["calls"].append("settings"))
    monkeypatch.setattr(snapshots, "_idle", lambda: state["calls"].append("idle"))
    monkeypatch.setattr(switching, "close_clients", lambda: state["calls"].append("close"))

    def fake_import(tmp):
        state["calls"].append("import")
        if state["import_ok"] is None:
            raise OSError("拒绝访问")
        if state["import_ok"]:
            state["uid"] = A if Path(tmp).read_bytes() == snapshot(A) else B

    monkeypatch.setattr(gameaccount, "gamereg_import", fake_import)
    return state


def worker(store):
    return AccountStore(store.root, role="task")


@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows 本地账号开关生效")
def test_selected_account_is_switched_before_launch(config, store, client):
    runtime.prepare(config, A, "main", Mock(), store=worker(store))
    assert client["calls"] == []  # 准备阶段只检查，不动游戏
    runtime.prepare_launch(config)
    assert client["calls"] == ["close", "idle", "import", "settings"] and client["uid"] == A
    runtime.verify_ready(config)
    config.save_timestamp("last_run_timestamp")
    assert store.read(A, "state.yaml")["last_run_timestamp"] and not store.read(B, "state.yaml")
    # 已经是目标账号时什么都不做。
    client["calls"].clear()
    runtime.prepare(config, A, "main", Mock(), store=worker(store))
    runtime.prepare_launch(config)
    assert client["calls"] == []


@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows 本地账号开关生效")
def test_wrong_account_after_switch_never_writes(config, store, client):
    runtime.prepare(config, A, "main", Mock(), store=worker(store))
    runtime.prepare_launch(config)
    client["uid"] = B  # 例如登录过期后，用户在登录页选了别的账号
    with pytest.raises(runtime.AccountError) as error:
        runtime.verify_ready(config)
    assert error.value.reason == "account_mismatch"
    with pytest.raises(runtime.AccountError):
        config.save_timestamp("last_run_timestamp")
    assert not switching.renew(config)
    assert store.path(A, "login.reg").read_bytes() == snapshot(A)


@pytest.mark.parametrize(
    "fault, reason, calls",
    [
        ("missing", "account_no_login", []),
        ("damaged", "account_switch_failed", []),
        ("other_account", "account_switch_failed", []),
        ("server", "account_server_mismatch", []),
        ("close", "account_switch_failed", []),
        ("running", "account_switch_failed", ["close"]),
        ("import", "account_switch_failed", ["close", "idle", "import", "settings"]),
        ("unchanged", "account_switch_failed", ["close", "idle", "import", "settings"]),
        ("stopped", None, ["close"]),
    ],
)
@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows 本地账号开关生效")
def test_switch_faults_keep_the_game_when_they_can(config, store, client, monkeypatch, fault, reason, calls):
    runtime.prepare(config, A, "main", Mock(), store=worker(store))
    path = store.path(A, "login.reg")
    if fault == "missing":
        path.unlink()
    elif fault == "damaged":
        path.write_bytes(b"broken")
    elif fault == "other_account":
        path.write_bytes(snapshot(B))
    elif fault == "server":
        monkeypatch.setattr(gameaccount, "get_reg_path", lambda *_: gameaccount.reg_path_oversea)
    elif fault == "close":
        def refuse():
            raise runtime.AccountError("account_switch_failed", "关不掉")
        monkeypatch.setattr(switching, "close_clients", refuse)
    elif fault == "running":
        def busy():
            raise snapshots.SnapshotError("game_running", "请关闭游戏")
        monkeypatch.setattr(snapshots, "_idle", busy)
    elif fault in ("import", "unchanged"):
        client["import_ok"] = None if fault == "import" else False
    elif fault == "stopped":
        from utils.pause import RunStopRequested, pause_ctl
        monkeypatch.setattr(pause_ctl, "check_stop", Mock(side_effect=RunStopRequested()))
    expected = runtime.AccountError
    if fault == "stopped":
        from utils.pause import RunStopRequested
        expected = RunStopRequested
    with pytest.raises(expected) as error:
        runtime.prepare_launch(config)
    assert client["calls"] == calls
    if reason:
        assert error.value.reason == reason
    assert client["uid"] == B and not store.read(B, "state.yaml")


@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows 本地账号开关生效")
def test_missing_snapshot_fails_before_anything_heavy(config, store, client, monkeypatch):
    store.path(A, "login.reg").unlink()
    with pytest.raises(runtime.AccountError) as error:
        runtime.prepare(config, A, "main", Mock(), store=worker(store))
    assert error.value.reason == "account_no_login" and client["calls"] == []
    # 客户端从没登录过、又保存了账号密码时，交给登录页。
    client["uid"] = None
    monkeypatch.setattr(AccountStore, "password_status", lambda *_: "saved")
    store.update(A, auto_login=True)
    runtime.prepare(config, A, "main", Mock(), store=worker(store))
    runtime.prepare_launch(config)
    assert client["calls"] == []


@pytest.mark.parametrize("stuck", [False, True])
def test_closing_the_game_is_bounded(monkeypatch, stuck):
    import psutil

    process = Mock()
    alive = [[process], [process] if stuck else []]
    monkeypatch.setattr(switching, "running_clients", Mock(side_effect=[[(process, "game.exe")], []]))
    monkeypatch.setattr(psutil, "wait_procs", lambda procs, timeout: ([], alive.pop(0)))
    monkeypatch.setattr(switching.time, "sleep", lambda _: None)
    if stuck:
        with pytest.raises(runtime.AccountError) as error:
            switching.close_clients()
        assert error.value.reason == "account_switch_failed"
    else:
        switching.close_clients()
    process.terminate.assert_called_once()
    process.kill.assert_called_once()


@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows 本地账号开关生效")
def test_snapshot_is_renewed_once_after_the_identity_is_verified(config, store, client, monkeypatch):
    client["uid"] = A
    fresh = snapshot(A).decode("utf-16") + '"token"="new"\r\n'
    exported = Mock(side_effect=lambda path, _: Path(path).write_bytes(fresh.encode("utf-16")))
    monkeypatch.setattr(gameaccount, "gamereg_export", exported)
    runtime.prepare(config, A, "main", Mock(), store=worker(store))
    assert not switching.renew(config)  # 还没核对 UID
    runtime.verify_ready(config)
    assert switching.renew(config) and not switching.renew(config)
    exported.assert_called_once()
    assert store.path(A, "login.reg").read_bytes() == fresh.encode("utf-16")
    assert store.path(A, "login.reg").with_suffix(".reg.bak").read_bytes() == snapshot(A)
    assert store.read(A, "state.yaml")["snapshot_saved_at"]


@pytest.mark.parametrize("case", ["expired", "twin", "no_snapshot", "export_fails", "unbound"])
@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows 本地账号开关生效")
def test_snapshot_is_kept_when_it_should_not_be_renewed(config, store, client, monkeypatch, case):
    client["uid"] = A
    exported = Mock(side_effect=OSError("拒绝访问"))
    monkeypatch.setattr(gameaccount, "gamereg_export", exported)
    runtime.prepare(config, A, "main", Mock(), store=worker(store))
    runtime.verify_ready(config)
    if case == "expired":
        runtime.mark_expired(config)
    elif case == "twin":
        monkeypatch.setenv("MARCH7TH_DESKTOP_TWIN", "1")
    elif case == "no_snapshot":
        store.path(A, "login.reg").unlink()
    elif case == "unbound":
        config.bind_account(None)
    assert not switching.renew(config)
    assert exported.called == (case == "export_fails")
    if case == "no_snapshot":
        assert not store.path(A, "login.reg").exists()
    else:
        assert store.path(A, "login.reg").read_bytes() == snapshot(A)
