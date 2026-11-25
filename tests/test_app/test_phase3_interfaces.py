"""Integration through the desktop pages, with external operations replaced at their boundaries."""
from math import ceil
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetricsF
from PySide6.QtWidgets import QApplication
from qfluentwidgets import PushButton, getFont, qconfig

from app.common.design_tokens import EVERNIGHT_RED
from module import localization
from module.config import cfg
from tests.test_app.test_language_switch import window, switch_language


@pytest.fixture
def editable(window, monkeypatch):
    for method in ("set_value", "set_values"):
        monkeypatch.setattr(cfg, method, getattr(type(cfg), method).__get__(cfg))
    return window


def test_search_shortcut_sidebar_keyboard_filters_and_empty_state(window, qtbot):
    window.stackedWidget.setAnimationEnabled(False)
    QApplication.setActiveWindow(window)
    qtbot.keyClick(window, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)
    qtbot.waitUntil(lambda: window._search_popup is not None and window._search_popup.isVisible())
    popup = window._search_popup
    popup.input.setText("下载代理")
    qtbot.waitUntil(lambda: bool(popup.rows))
    from app.search_popup import result_group
    groups = list(dict.fromkeys(map(result_group, popup.results)))
    assert [r.result for r in popup.rows] == sorted(popup.results, key=lambda r: groups.index(result_group(r)))
    assert len({row.result.kind for row in popup.rows}) >= 1
    assert popup.rows[0].result.link == "setting:update_download_proxy"
    qtbot.keyClick(popup.input, Qt.Key.Key_Down)
    assert popup.selected == 1
    qtbot.keyClick(popup.input, Qt.Key.Key_Up)
    assert popup.selected == 0
    qtbot.keyClick(popup.input, Qt.Key.Key_Tab)
    assert popup.filter == "setting"
    assert all(row.result.kind in ("setting", "category") for row in popup.rows)
    qtbot.mouseClick(popup.pills["doc"], Qt.MouseButton.LeftButton)
    assert popup.rows and all(row.result.kind == "doc" for row in popup.rows)
    qtbot.keyClick(popup.input, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: window.stackedWidget.currentWidget() is window.helpInterface)
    assert popup.isHidden()
    qtbot.mouseClick(window.searchBox, Qt.MouseButton.LeftButton)
    assert popup.isVisible()
    popup.input.setText("zzzz-no-such-item")
    qtbot.waitUntil(lambda: popup.empty.isVisible())
    assert popup.selected == -1 and not popup.rows and popup.suggestionRow.count() > 1
    qtbot.keyClick(popup.input, Qt.Key.Key_Escape)
    assert popup.isHidden()
    window.openSearch()
    popup.input.setText("抽卡")
    # A fast Enter must use the new query, even before the debounce timer fires.
    qtbot.keyClick(popup.input, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: window.stackedWidget.currentWidget() is window.warpInterface)


def test_external_yaml_refreshes_task_cards_notifications_and_open_search(window, qtbot, monkeypatch):
    monkeypatch.setattr("module.notification.init_notifiers", Mock())
    monkeypatch.setattr(window.runController, "reloadConfigState", Mock())
    window.stackedWidget.setAnimationEnabled(False)
    assert window.navigate("category:notify")
    assert window.taskInterface.showTask("reward")
    window.openSearch()
    window._search_popup.input.setText("代理")
    qtbot.waitUntil(lambda: bool(window._search_popup.rows))
    old_page = window.settingInterface
    old_entries = window.searchIndex._entries
    old_box = window.taskInterface.pages["reward"].checks.boxes["reward_mail_enable"]
    changed = not old_box.isChecked()
    cfg.save_config()
    path = Path(cfg.config_path)
    with path.open(encoding="utf-8") as f:
        data = cfg.yaml.load(f)
    data.update(reward_mail_enable=changed, notification_added_channels=["telegram"],
                notify_telegram_enable=False, update_download_proxy="http://example.invalid:8080")
    with path.open("w", encoding="utf-8") as f:
        cfg.yaml.dump(data, f)
    window._on_config_file_changed()
    assert window.settingInterface is not old_page
    assert window.settingInterface.currentCategory() == "notify"
    assert window.taskInterface.currentTask() == "reward"
    assert window.taskInterface.pages["reward"].checks.boxes["reward_mail_enable"].isChecked() == changed
    assert "telegram" in window.settingInterface.pages["notify"].channels.rows
    assert window.searchIndex._entries is not old_entries
    assert any(r.link == "setting:update_download_proxy" and r.value == data["update_download_proxy"]
               for r in window._search_popup.results)


@pytest.mark.parametrize("window", [{"test_tray": True}], indirect=True)
def test_tray_opens_current_settings_and_twin_disables_new_pages(window, monkeypatch):
    monkeypatch.setattr(window.runController, "setDesktopTwinHosting", Mock())
    monkeypatch.setattr(window.toolsInterface, "setDesktopTwinHosting", Mock())
    monkeypatch.setattr(cfg, "is_config_changed", lambda: False)
    monkeypatch.setattr(cfg, "writes_suspended", False)
    window.stackedWidget.setAnimationEnabled(False)
    window.switchTo(window.taskInterface)
    action = next(a for a in window.tray_icon.contextMenu().actions() if a.text() == localization.tr("设置"))
    window.setDesktopTwinHosting(True)
    try:
        assert all(not w.isEnabled() for w in (window.settingInterface, window.taskInterface,
                                                window.accountsInterface, window.warpInterface))
        assert not window.warpInterface.transferButton.isEnabled()
        assert not action.isEnabled() and window._desktop_twin_notice.isVisible()
    finally:
        window.setDesktopTwinHosting(False)
    action.trigger()
    assert window.stackedWidget.currentWidget() is window.settingInterface
    assert all(w.isEnabled() for w in (window.taskInterface, window.accountsInterface, window.warpInterface))


@pytest.mark.parametrize("window", [{"evernight_unlocked": True, "ui_theme": "light"}], indirect=True)
def test_pages_keep_theme_language_and_task_state(window, editable, qtbot):
    window = editable
    window.stackedWidget.setAnimationEnabled(False)
    window.openSearch()
    window._search_popup.close()
    window.taskInterface.showTask("assets")
    window.taskInterface.pages["assets"].views["relics"].setExpanded(True)
    window._evernight.animation_played = True
    for theme in ("light", "dark", "evernight"):
        assert window.set_ui_theme(theme)
        assert len(window.settingInterface.pages) == len(window.taskInterface.pages) == 10
        window.openSearch()
        assert window._search_popup.isVisible() and window.accountsInterface.detail is not None
        window._search_popup.close()
    assert qconfig.get(qconfig.themeColor).name() == EVERNIGHT_RED
    assert window.taskInterface.pages["power"].header.tile._evernight
    assert window.settingInterface.hint.actionButton._evernight
    assert window.settingInterface.themeCard.comboBox.findData("evernight") >= 0
    previous_accounts = window.accountsInterface.detail
    old_task = window.taskInterface.pages["assets"]
    window.openSearch()
    window._search_popup.input.setText("proxy")
    switch_language(qtbot, window, "en_US")
    assert window.accountsInterface.detail is previous_accounts
    assert window.taskInterface.pages["assets"] is not old_task
    assert window.taskInterface.currentTask() == "assets"
    assert window.taskInterface.pages["assets"].views["relics"].isExpanded()
    assert window._search_popup.input.text() == "proxy"
    assert window._search_popup.input.placeholderText() == localization.tr("搜索设置、任务、帮助和工具")
    assert window.accountsInterface.titleLabel.text() == localization.tr("账号")
    for group, label in (("tool", "Tools"), ("page", "Pages")):
        assert window._search_popup.pills[group]._text.startswith(label)


def test_task_switch_reward_strategy_and_default_control(editable, qtbot):
    from app.content.settings_state import defaults_for
    from module.settings_registry import find_setting
    from tasks.weekly.currency_wars_strategy import HIGH_ANAXA
    window = editable
    tasks = window.taskInterface
    window.stackedWidget.setAnimationEnabled(False)
    assert window.navigate("task:reward")
    row = tasks.listPanel.rows["reward"]
    before = row.switch.isChecked()
    row.switch.setChecked(not before)
    qtbot.waitUntil(lambda: tasks.pages["reward"].header.joinSwitch.isChecked() != before)
    assert window.taskModel.enabled("reward") != before
    box = tasks.pages["reward"].checks.boxes["reward_mail_enable"]
    value = not box.isChecked()
    box.setChecked(value)
    assert cfg.reward_mail_enable == value
    cfg.set_value("currencywars_strategy", "retired")
    assert window.navigate("task:currencywars")
    notice = tasks.pages["currencywars"].notice
    qtbot.waitUntil(notice.isVisible)
    qtbot.mouseClick(notice.actionButton, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(notice.isHidden)
    assert cfg.currencywars_strategy == HIGH_ANAXA
    item = find_setting("use_fuel")
    original = defaults_for(item)[item.id]
    assert window.navigate("setting:use_fuel")
    badge = tasks.pages["power"].decorations.badges[item.id]
    cfg.set_value(item.id, not original)
    qtbot.waitUntil(lambda: badge.pill.isVisible())
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QEnterEvent
    center = QPointF(badge.target.rect().center())
    QApplication.sendEvent(badge.target, QEnterEvent(center, center, center))
    qtbot.waitUntil(badge.resetButton.isVisible)
    qtbot.mouseClick(badge.resetButton, Qt.MouseButton.LeftButton)
    assert cfg.use_fuel == original and badge.pill.isHidden()


def test_channel_dialog_validation_test_send_save_and_qq_binding(editable, qtbot, monkeypatch):
    from app.content import notify_model
    from app.pages.notify import ChannelDialog
    from module.notification import channels, results
    from module.notification.qqbot import QqBotOpenIdBinder
    w = editable
    monkeypatch.setattr(notify_model, "init_notifiers", Mock())
    test_send = Mock(return_value=results.Delivery("", True))
    monkeypatch.setattr(channels, "send_test", test_send)
    dialog = ChannelDialog(w.notifyModel, "telegram", w)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.yesButton.click()
    assert dialog.errors["notify_telegram_token"].isVisible() and dialog.isVisible()
    dialog.editors["notify_telegram_token"][1].setText("test-token")
    dialog.editors["notify_telegram_userid"][1].setText("12345")
    with qtbot.waitSignal(w.notifyModel.testFinished):
        dialog.testButton.click()
    assert test_send.call_args.args[2]["notify_telegram_userid"] == "12345"
    assert dialog.testButton.isEnabled() and dialog.testResult.text()
    assert not cfg.notify_telegram_token
    dialog.yesButton.click()
    qtbot.waitUntil(dialog.isHidden)
    assert cfg.notify_telegram_token == "test-token"
    assert "telegram" in w.settingInterface.pages["notify"].channels.rows
    qq = ChannelDialog(w.notifyModel, "qqbot", w)
    qtbot.addWidget(qq)
    qq.show()
    qq.editors["notify_qqbot_appid"][1].setText("appid")
    qq.editors["notify_qqbot_client_secret"][1].setText("test-secret")
    monkeypatch.setattr(notify_model.MessageBox, "exec", lambda _: True)
    monkeypatch.setattr(QqBotOpenIdBinder, "capture", lambda self, mode, code: "demo-recipient")
    bind = next(b for b in qq.findChildren(PushButton) if b.text() == localization.tr("自动绑定单聊用户"))
    with qtbot.waitSignal(w.notifyModel.bound):
        bind.click()
        assert w.notifyModel.binding_pending and not w._can_replace_settings()
    assert qq.editors["notify_qqbot_openid"][1].text() == "demo-recipient"
    assert not cfg.notify_qqbot_openid
    qq.cancelButton.click()



def test_channel_can_be_removed_from_the_list(editable, qtbot, monkeypatch):
    from app.content import notify_model
    from app.pages import notify
    w = editable
    monkeypatch.setattr(notify_model, "init_notifiers", Mock())
    panel = w.settingInterface.pages["notify"].channels
    assert not w.notifyModel.save("telegram", {"notify_telegram_token": "test-token", "notify_telegram_userid": "12345"})
    qtbot.waitUntil(lambda: "telegram" in panel.rows)
    asked = []
    answers = iter([False, True])
    monkeypatch.setattr(notify.MessageBox, "exec", lambda box: asked.append(box.contentLabel.text()) or next(answers))
    qtbot.mouseClick(panel.rows["telegram"].removeButton, Qt.MouseButton.LeftButton)
    assert "telegram" in panel.rows and cfg.notify_telegram_token == "test-token"
    qtbot.mouseClick(panel.rows["telegram"].removeButton, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "telegram" not in panel.rows)
    assert not cfg.notify_telegram_token and not cfg.notify_telegram_enable
    assert not panel.tiles["telegram"]._added and len(asked) == 2 and "填写的内容会一起清除" in asked[0]
    monkeypatch.setattr(w.notifyModel, "remove", lambda _: {"": "配置写入已暂停"})
    failed = Mock()
    monkeypatch.setattr(notify.InfoBar, "error", failed)
    answers = iter([True])
    panel._remove("winotify" if sys.platform == "win32" else "telegram")
    assert failed.call_args.args[1] == "配置写入已暂停"


def test_power_order_follows_the_settings(editable, qtbot):
    page = editable.taskInterface.pages["power"]
    host, steps = page.host, page.order.steps
    assert [step.cards for step in steps.values()] == [
        [host.powerPlanCard], [host.buildTargetEnableCard], [host.instanceTypeCard, host.instanceNameCard]]
    base = {"control_backend": "local", "ui_profile": "pc_1080", "power_plan": [], "build_target_enable": False,
            "instance_type": "侵蚀隧洞", "instance_names": {**cfg.instance_names, "侵蚀隧洞": "睿治之径"}}

    def shows(*texts):
        qtbot.waitUntil(lambda: tuple(step.pill.text() for step in steps.values()) == texts)

    cfg.set_values(base)
    shows("暂无计划，跳过", "未启用，跳过", "直接刷这里")
    assert [step._number for step in steps.values()] == [1, 2, 3]
    cfg.set_values({"power_plan": [["凝滞虚影", "空海之形", 2]], "build_target_enable": True})
    shows("先刷 1 项", "计划刷完再刷", "培养目标用不上时才刷")
    cfg.set_value("power_plan_continue", False)
    shows("先刷 1 项", "计划刷完就停，不会刷", "计划刷完就停，不会刷")
    cfg.set_values({**base, "control_backend": "adb", "ui_profile": "touch_720"})
    qtbot.waitUntil(steps["target"].isHidden)
    assert (steps["plan"]._number, steps["default"]._number, steps["default"]._last) == (1, 2, True)
    editable.stackedWidget.setAnimationEnabled(False)
    assert editable.navigate("task:power#power_plan")
    assert editable.taskInterface.currentTask() == "power"


def test_sidebar_search_text_is_never_cut(window):
    box = window.searchBox
    assert box.text() == "搜索功能、设置、帮助"
    if sys.platform == "win32":
        assert box.shownText() == box.text()
    metrics = QFontMetricsF(getFont(13))
    controls_width = box.width() - box._rects()[2].width()
    box.setFixedWidth(ceil(controls_width + metrics.horizontalAdvance(box.text())))
    assert box.shownText() == box.text()
    box.setFixedWidth(ceil(controls_width + metrics.horizontalAdvance("搜索")))
    assert box.shownText() == "搜索"


def test_default_window_size_matches_config():
    from ruamel.yaml import YAML
    from app.main_window import DEFAULT_WINDOW_HEIGHT, MIN_WINDOW_WIDTH
    example = YAML(typ="safe").load(Path(cfg.example_path))
    assert (example["window_width"], example["window_height"]) == (MIN_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)


@pytest.mark.parametrize("component", ["task", "accounts"])
def test_language_rollback_on_new_page_failure(editable, qtbot, monkeypatch, component):
    from app import task_interface
    from app import accounts_interface as accounts
    w = editable
    w.stackedWidget.setAnimationEnabled(False)
    assert w.navigate("task:reward")
    before = w.settingInterface
    previous = cfg.ui_language
    owner, name = (task_interface, "TaskPage") if component == "task" else (accounts.AccountsInterface, "_setTexts")
    factory = getattr(owner, name)

    def fail_in_english(*args, **kwargs):
        if localization.get_current_language() == "en_US":
            raise RuntimeError("page construction failed")
        return factory(*args, **kwargs)

    monkeypatch.setattr(owner, name, fail_in_english)
    warning = Mock()
    monkeypatch.setattr("app.main_window.InfoBar.warning", warning)
    w._on_ui_language_changed("en_US")
    qtbot.waitUntil(lambda: warning.called, timeout=15000)
    assert localization.get_current_language() == "zh_CN" and cfg.ui_language == previous
    assert w.settingInterface is before
    assert w.taskInterface.currentTask() == "reward"
    assert w.stackedWidget.currentWidget() is w.taskInterface
    assert w.accountsInterface.titleLabel.text() == "账号"


@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows 本地账号绑定")
def test_live_account_binding_preserves_run_page_and_scopes_plan(window, qtbot, tmp_path, monkeypatch):
    from module.accounts.store import AccountStore
    from module.accounts.files import write_yaml
    from qfluentwidgets import Theme, setTheme
    model, page, controller = window.accountModel, window.logInterface, window.runController
    store = AccountStore(tmp_path / "accounts", role="ui")
    monkeypatch.setattr(model, "store", store)
    monkeypatch.setattr(cfg, "_account_layer", None)
    monkeypatch.setattr("utils.registry.gameaccount.gamereg_uid", lambda *args: 100000789)
    write_yaml(store.index_path, {"enabled": True, "current": "100000789", "accounts": [
        {"uid": "100000789", "name": "虚构甲"}, {"uid": "100000456", "name": "虚构乙", "plan": "independent"}]})
    store.modify("100000456", "plan.yaml", lambda plan: plan.update(instance_type="侵蚀隧洞"))
    try:
        model.refresh()
        assert cfg.bound_account == "100000789" and not window.taskModel.overridden("power")
        controller.appendLog("样例任务已开始\n")
        window.stackedWidget.setAnimationEnabled(False)
        assert window.navigate("page:accounts")
        assert model.set_current("100000456").ok
        assert window.taskModel.overridden("power") and cfg.instance_type == "侵蚀隧洞"
        result = window.searchIndex.query("定时计划", settings_only=True)[0]
        assert result.link == "run:schedule"
        window.settingInterface._openResult(result)
        assert window.stackedWidget.currentWidget() is page and page.page() == "schedule"
        for segment in ("current", "schedule", "history"):
            assert window.navigate("run:" + segment) and page.page() == segment
        setTheme(Theme.DARK)
        switch_language(qtbot, window, "en_US")
        assert window.logInterface is page and window.runController is controller
        assert model.card()[1] == "虚构乙" and controller.log_entries()[-1].text == "样例任务已开始"
    finally:
        cfg.bind_account(None)
