from datetime import datetime, timedelta
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

from module.channel_catalog import CHANNELS
from module.content_samples import SampleConfig, sample_state
from module.navigation import resolve_link
from module.notification import channels, results
from module.overview.cards import preview
from module.search import SearchIndex, current_value
from module.search.documents import heading_pairs
from module.settings_registry import SETTINGS, Scope, find_setting
from module.task_catalog import BY_ID, estimate, power_order, status


def test_notification_forms_match_template_and_registry():
    config = SampleConfig()
    actual = {c.enable_key for c in CHANNELS} | {f.key for c in CHANNELS for f in c.fields}
    expected = {key for key in config.config if any(key.startswith(f"notify_{c.id}_") for c in CHANNELS)}
    assert actual == expected
    for channel in CHANNELS:
        assert {f.key for f in channel.fields} <= channels.form(config, channel.id).keys()
        assert all(find_setting(f.key).page == "notify" for f in channel.fields)


@pytest.mark.parametrize("query, links", [
    ("后台", {"setting:local_control_mode"}), ("体力", {"task:power"}),
    ("刷本", {"task:power", "task:power#instance_type"}), ("抽卡", {"page:warp"}),
    ("关机", {"setting:after_finish"}), ("通知", {"category:notify"}),
    ("模拟器", {"setting:control_backend"}),
    ("代理", {"setting:update_download_proxy"}),
])
def test_common_search_top_three(query, links):
    if query == "后台" and sys.platform != "win32":
        pytest.skip("本地操作模式仅在 Windows 显示")
    config = SampleConfig()
    config.set_value("control_backend", "local")
    results = SearchIndex(config).query(query, limit=3)
    assert links.intersection(r.link for r in results), results
    if query == "模拟器":
        assert any(r.name == "安卓设备" and r.link == "setting:control_backend" for r in results)


def test_channel_lifecycle_and_secret_values(tmp_path):
    cfg = SampleConfig()
    assert channels.save(cfg, "telegram", {}) == {"notify_telegram_token": "请填写此项", "notify_telegram_userid": "请填写此项"}
    assert not channels.save(cfg, "telegram", {"notify_telegram_token": "SENTINEL", "notify_telegram_userid": "004"})
    assert not channels.save(cfg, "telegram", {"notify_telegram_userid": "002"})
    assert cfg.notify_telegram_userid == "002"
    assert not channels.set_enabled(cfg, "telegram", False)
    row = next(r for r in channels.added(cfg, {}) if r.channel.id == "telegram")
    assert not row.enabled and "SENTINEL" not in row.summary
    assert current_value(find_setting("notify_telegram_token"), cfg) == "已设置"
    assert not channels.set_enabled(cfg, "telegram", True)
    assert not channels.remove(cfg, "telegram")
    assert not cfg.notify_telegram_token and all(r.channel.id != "telegram" for r in channels.added(cfg, {}))
    if sys.platform == "win32":
        channels.set_enabled(cfg, "winotify", False)
        assert "winotify" in {r.channel.id for r in channels.added(cfg, {})}
        channels.remove(cfg, "winotify")
        assert "winotify" not in {r.channel.id for r in channels.added(cfg, {})}


@pytest.mark.parametrize("channel", CHANNELS, ids=lambda channel: channel.id)
def test_every_channel_can_be_removed(channel):
    cfg = SampleConfig()
    original = channels.form(cfg, channel.id)
    cfg.set_values({**{f.key: "x" for f in channel.fields if f.kind not in ("switch", "choice", "number")},
                    channel.enable_key: True, channels.ADDED: [channel.id]})
    assert not channels.remove(cfg, channel.id)
    assert channel.id not in {row.channel.id for row in channels.added(cfg, {})}
    assert channels.form(cfg, channel.id) == original and not cfg.get_value(channel.enable_key)


def test_unsaved_channel_test_and_recording(tmp_path, monkeypatch):
    from module.notification import NotifierFactory
    from module.notification.notification import Notification
    cfg = SampleConfig()
    calls = []
    error = TimeoutError("https://host/SENTINEL")
    notifier = Mock()
    notifier.send.side_effect = error
    def create(name, values, logger):
        calls.append((name, values))
        return notifier
    monkeypatch.setattr(NotifierFactory, "create_notifier", create)
    result = channels.send_test(cfg, "telegram", {"notify_telegram_token": "SENTINEL", "notify_telegram_userid": "2"})
    assert not result.success and result.code == "timeout"
    assert calls == [("telegram", {"token": "SENTINEL", "userid": "2"})]
    assert not cfg.notify_telegram_token
    path = tmp_path / "state.db"
    monkeypatch.setattr(results, "database_path", lambda: path)
    delivery = Notification.__new__(Notification)
    Notification.__init__(delivery, "T")
    ok = Mock()
    delivery.set_notifier("telegram", notifier)
    delivery.set_notifier("smtp", ok)
    delivery.notify("body")
    stored = results.read_results()
    assert not stored["telegram"].success and stored["smtp"].success
    assert "SENTINEL" not in str(stored) and b"SENTINEL" not in path.read_bytes()
    monkeypatch.setattr(results, "database_path", lambda: path / "impossible")
    delivery.notify("again")
    assert ok.send.call_count == 2


def test_provider_rejection_is_not_logged_as_success(monkeypatch):
    from module.notification.serverchan3 import ServerChanNotifier
    reply = Mock()
    reply.json.return_value = {"code": 40001, "message": "SENTINEL"}
    monkeypatch.setattr("module.notification.serverchan3.requests.post", Mock(return_value=reply))
    result = results.send_one(ServerChanNotifier({"sendkey": "test"}, Mock()), "title", "text")
    assert not result.success and "SENTINEL" not in result.reason


@pytest.mark.parametrize("scenario", ["desktop", "touch", "empty"])
def test_samples_and_plan_agree(scenario):
    sample = sample_state(scenario)
    cfg = sample.config
    now = datetime(2026, 11, 23, 13, 20)
    rows = preview(cfg, now, touch=scenario == "touch", backend=cfg.control_backend)
    for key, task in BY_ID.items():
        assert sample.tasks[key] == status(task, rows, cfg, supported=scenario != "touch" or task.touch)
        assert len(sample.tasks[key].text) <= 16
    assert sample.empty_results == () and sample.results and sample.suggestions
    assert bool(sample.channels) == (scenario != "empty")
    if scenario == "empty":
        assert sample.estimates["power"] is None
    else:
        assert "3 次" in sample.estimates["power"].text and sample.estimates["power"].ratio == 186 / 300
        assert {r.last.success for r in sample.channels} == {True, False}
        later = estimate("power", cfg, now + timedelta(hours=1))
        assert "196" in later.text and later.ratio == 196 / 300
        cfg.set_value("overview_power", {"value": 50, "timestamp": now.timestamp()})
        assert "5 轮" in estimate("power", cfg, now).text and "0 次" not in estimate("power", cfg, now).text
    cfg.set_value("overview_power", {"value": "invalid", "timestamp": None})
    assert estimate("power", cfg) is None


PLAN = [["凝滞虚影", "空海之形", 2]]


@pytest.mark.parametrize("values,expected", [
    ({}, ("skip", "skip", "first")),
    ({"build_target_enable": True}, ("skip", "first", "then")),
    ({"power_plan": PLAN}, ("first", "skip", "then")),
    ({"power_plan": PLAN, "build_target_enable": True}, ("first", "then", "then")),
    ({"power_plan": PLAN, "build_target_enable": True, "power_plan_continue": False}, ("first", "skip", "skip")),
    ({"instance_names": {"侵蚀隧洞": "无"}}, ("skip", "skip", "warning")),
    ({"instance_names": {"侵蚀隧洞": "无"}, "power_plan": PLAN}, ("first", "skip", "skip")),
    ({"build_target_enable": True, "control_backend": "adb", "ui_profile": "touch_720"}, ("skip", "skip", "first")),
])
def test_power_order_says_what_the_next_run_will_use(values, expected):
    cfg = SampleConfig()
    cfg.set_values({"control_backend": "local", "ui_profile": "pc_1080", "instance_type": "侵蚀隧洞", "power_plan": [],
                    "instance_names": {"侵蚀隧洞": "睿治之径"}, "power_plan_continue": True,
                    "build_target_enable": False, **values})
    states = power_order(cfg)
    assert [state.id for state in states] == ["plan", "target", "default"]
    assert tuple(state.kind for state in states) == expected
    assert states[2].detail == ("侵蚀隧洞" if "instance_names" in values else "侵蚀隧洞 · 睿治之径")


def test_power_order_uses_the_rest_of_an_account_plan():
    class Progress(SampleConfig):
        def remaining_power_plan(self):
            return []

    cfg = Progress()
    cfg.set_values({"power_plan": PLAN, "power_plan_continue": False})
    plan, _, default = power_order(cfg)
    assert (plan.kind, plan.text, default.kind) == ("skip", "计划已刷完，跳过", "first")


def test_search_ranking_secrets_and_every_link():
    cfg = SampleConfig()
    cfg.set_values({"control_backend": "local", "github_token": "SENTINEL"})
    index = SearchIndex(cfg)
    assert index.query("ＳＭＴＰ")[0].link.endswith("notify_smtp_enable") or index.query("ＳＭＴＰ")[0].name.startswith("SMTP")
    assert index.query("清体力")[0].link == "task:power"
    local_mode_results = index.query("不占鼠标", limit=100)
    assert any(row.link == "setting:local_control_mode" for row in local_mode_results) == (sys.platform == "win32")
    assert any(row.link == "task:power" for row in index.query("刷本"))
    assert all(row.kind == "setting" and row.location.startswith("设置") for row in index.query("后台", settings_only=True))
    assert index.query("GitHub Token")[0].value == "已设置"
    assert not index.query("SENTINEL")
    assert index.query("后台 鼠标")
    for entry in index._entries:
        assert entry.result.description, entry.result.link
        target = resolve_link(entry.result.link)
        assert target, entry.result
        if target.kind == "doc" and target.anchor:
            assert target.anchor in {h.anchor for h, _ in heading_pairs(target.page)}
    assert index.query("xz97239048") == []


def test_search_rebuilds_on_language_change(monkeypatch, compiled_locales):
    from module import localization
    monkeypatch.setattr(localization, "_locale_dir", str(compiled_locales))
    cfg = SampleConfig()
    index = SearchIndex(cfg)
    old = localization.get_current_language()
    try:
        localization.load_language("zh_CN")
        assert index.query("使用燃料")
        entries = index._entries
        localization.load_language("en_US")
        rows = index.query("后台模式", kinds={"doc"}, limit=100)
        assert rows and index._entries is not entries
        assert any(r.name.startswith("Windows") for r in rows)
    finally:
        localization.load_language(old)


def test_secret_masking_for_all_registered_fields():
    cfg = SampleConfig()
    secrets = {k for item in SETTINGS for k in item.keys if item.key_scope(k) == Scope.SECRET}
    cfg.set_values(dict.fromkeys(secrets, "SENTINEL"))
    for key in secrets:
        assert current_value(find_setting(key), cfg) == "已设置"
    assert all("SENTINEL" not in row.summary for row in channels.added(cfg, {}))


def test_manual_page_switches_are_local_and_released_on_failure(tmp_path):
    from module.config.config import Config
    from ruamel.yaml import YAML
    cfg = Config.__new__(Config)
    cfg.config = {"echo_of_war_enable": False, "power_enable": False, "state": 0}
    cfg.config_path = str(tmp_path / "config.yaml")
    cfg.yaml = YAML()
    with pytest.raises(RuntimeError):
        with cfg.standalone_switches(("power_enable", "echo_of_war_enable")):
            assert cfg.power_enable and cfg.echo_of_war_enable
            cfg.set_value("state", 1)
            raise RuntimeError()
    assert cfg.state == 1 and not cfg.power_enable and not cfg.echo_of_war_enable
    assert not YAML(typ="safe").load(Path(cfg.config_path))["power_enable"]


@pytest.mark.parametrize("provider, draft, errors", [
    ("qqbot", {"notify_qqbot_appid": "a", "notify_qqbot_client_secret": "b"}, ("openid", "group_openid")),
    ("wechatworkbot", {}, ("key", "webhook_url")),
    ("smtp", {"notify_smtp_host": "mail", "notify_smtp_user": "a", "notify_smtp_port": 80000}, ("port",)),
    ("lark", {"notify_lark_webhook": "https://example.invalid", "notify_lark_imageenable": True}, ("appid", "secret")),
    ("webhook", {"notify_webhook_url": "https://example.invalid", "notify_webhook_headers": "[]"}, ("headers",)),
])
def test_channel_field_validation(provider, draft, errors):
    cfg = SampleConfig()
    before = channels.form(cfg, provider)
    assert set(channels.save(cfg, provider, draft)) == {f"notify_{provider}_{s}" for s in errors}
    assert channels.form(cfg, provider) == before


def test_samples_do_not_load_user_configuration(tmp_path):
    import os
    import subprocess
    env = dict(os.environ, M7A_DATA_DIR=str(tmp_path / "unused"))
    subprocess.run([sys.executable, "-B", "-c",
                    "import sys; from module.content_samples import sample_state; sample_state(); "
                    "assert 'module.config' not in sys.modules and 'PySide6' not in sys.modules"],
                   check=True, env=env)
    assert not (tmp_path / "unused").exists()


def test_manual_page_reuses_selected_actions(monkeypatch):
    from contextlib import contextmanager
    from tasks.page_actions import run_page
    from tasks.daily.daily import Daily
    from tasks.reward import quest
    from tasks import reward
    from tasks.daily import redemption
    from tasks.touch import rewards
    cfg = SampleConfig()
    cfg.set_values({"reward_enable": False, "reward_redemption_code_enable": False, "reward_quest_enable": True})
    @contextmanager
    def switches(keys):
        before = {k: cfg.get_value(k) for k in keys}
        cfg.set_values(dict.fromkeys(keys, True))
        try:
            yield
        finally:
            cfg.set_values(before)
    cfg.standalone_switches = switches
    seen = []
    monkeypatch.setattr(reward, "start", lambda: seen.append(("reward", cfg.reward_enable)))
    monkeypatch.setattr(redemption.Redemption, "get", lambda: pytest.fail("unchecked redemption ran"))
    monkeypatch.setattr(quest.Quest, "settle", lambda: seen.append(("quest", cfg.reward_enable)))
    assert run_page("reward", cfg) and seen == [("reward", True), ("quest", True)]
    assert not cfg.reward_enable
    prepare = Mock(return_value=True)
    monkeypatch.setattr(Daily, "prepare_daily", prepare)
    assert run_page("activity", cfg)
    prepare.assert_called_once_with(ignore_refresh=True, only="activity")
    touch = Mock(return_value=True)
    monkeypatch.setattr(rewards, "routine", touch)
    assert run_page("echo", cfg, touch=True)
    touch.assert_called_once_with(only="echo")


@pytest.mark.parametrize("status, code", [(None, "timeout"), (403, "http_403")])
def test_webhook_keeps_transport_reason_without_revealing_url(monkeypatch, status, code):
    import requests
    from module.notification.webhook import WebhookNotifier
    url = "https://example.invalid/SENTINEL"
    if status is None:
        failure = requests.Timeout(url)
    else:
        response = requests.Response()
        response.status_code = status
        failure = requests.HTTPError(url, response=response)
    monkeypatch.setattr("module.notification.webhook.requests.post", Mock(side_effect=failure))
    delivery = results.send_one(WebhookNotifier({"url": url}, Mock()), "title", "text")
    assert not delivery.success and delivery.code == code
    assert "SENTINEL" not in delivery.reason
