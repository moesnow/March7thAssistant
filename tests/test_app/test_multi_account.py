"""多账号配置隔离、按当前账号起跑，以及最小 GUI。"""
import copy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    from module.config import cfg
    from module.config.config import Config
    from module.config import accounts

    monkeypatch.setattr(Config, "_readonly", False)
    monkeypatch.setattr(cfg, "writes_suspended", False)
    monkeypatch.setattr(cfg, "config", copy.deepcopy(cfg._load_default_config("assets/config/config.example.yaml")))
    monkeypatch.setattr(cfg, "config_path", str(tmp_path / "config.yaml"))
    monkeypatch.setattr(accounts, "PROFILE_ROOT", tmp_path / "profiles")
    cfg.save_config()
    return cfg


def test_profiles_keep_settings_and_progress_separate(isolated_config):
    from module.config.accounts import add_account, account_config, profile_path
    cfg = isolated_config
    cfg.set_values({"last_run_timestamp": 123, "weekly_relic_cleanup_timestamp": 456,
                    "divergent_universe_daily_completed_count": 5, "power_plan": [{"count": 3}]})
    one, two = add_account(cfg), add_account(cfg)
    original_path = cfg.config_path
    original_bytes = Path(original_path).read_bytes()
    with account_config(cfg, one):
        assert cfg.last_run_timestamp == 0
        assert cfg.weekly_relic_cleanup_timestamp == 0
        assert cfg.divergent_universe_daily_completed_count == 0
        assert cfg.power_plan == [{"count": 3}]
        cfg.set_values({"last_run_timestamp": 999, "power_enable": False, "power_plan": []})
    with account_config(cfg, two):
        assert cfg.last_run_timestamp == 0
        assert cfg.power_enable is True
        assert cfg.power_plan == [{"count": 3}]
    with account_config(cfg, one):
        assert cfg.last_run_timestamp == 999
        assert cfg.power_enable is False
        assert cfg.power_plan == []
    assert cfg.config_path == original_path
    assert Path(original_path).read_bytes() == original_bytes
    assert profile_path(one) != profile_path(two)


def test_shared_settings_follow_default_and_context_restores_on_error(isolated_config):
    from module.config.accounts import add_account, account_config
    cfg = isolated_config
    account = add_account(cfg)
    cfg.set_values({"game_path": "new-game.exe", "after_finish": "Shutdown"})
    original_path = cfg.config_path
    with pytest.raises(RuntimeError, match="task failed"):
        with account_config(cfg, account):
            assert cfg.game_path == "new-game.exe"
            assert cfg.after_finish == "Shutdown"
            cfg.set_value("power_enable", False)
            raise RuntimeError("task failed")
    assert cfg.config_path == original_path
    assert cfg.power_enable is True


@pytest.fixture
def runner(isolated_config, monkeypatch):
    from tasks.game import multi_account as module
    from module.config.accounts import add_account

    cfg = isolated_config
    one, two = add_account(cfg), add_account(cfg)
    one.update(name="one", login_name="111******11", uid="1")
    two.update(name="two", login_name="222******22", uid="2")
    cfg.set_value("multi_accounts", [one, two])
    monkeypatch.setattr(module, "cfg", cfg)
    original_switch = module.switch_account
    switch = Mock(side_effect=lambda account: account["uid"])
    monkeypatch.setattr(module, "switch_account", switch)
    monkeypatch.setattr(module, "current_uid", lambda: "2")
    return SimpleNamespace(module=module, cfg=cfg, one=one, two=two, switch=switch,
                           original_switch=original_switch)


def test_current_account_first_and_new_batch_has_no_stale_completion(runner):
    from module.config.accounts import profile_path
    ran = []
    def run():
        ran.append(runner.cfg.config_path)
        runner.cfg.set_value("last_run_timestamp", len(ran))
    runner.module.run_accounts(run)
    assert ran == [str(profile_path(runner.two)), str(profile_path(runner.one))]
    assert [call.args[0]["id"] for call in runner.switch.call_args_list] == [runner.one["id"]]
    runner.module.run_accounts(run)
    assert ran[2:] == ran[:2]


def test_uid_is_bound_after_selecting_unknown_account(runner):
    one = {**runner.one, "uid": ""}
    runner.cfg.set_value("multi_accounts", [one])
    runner.switch.side_effect = lambda account: "10001"
    seen = []
    runner.module.run_accounts(lambda: seen.append(runner.cfg.last_run_timestamp))
    assert runner.cfg.multi_accounts[0]["uid"] == "10001"
    assert seen == [0]
    runner.switch.assert_called_once()


def test_disabled_account_is_skipped_and_failure_does_not_continue(runner):
    runner.cfg.set_value("multi_accounts", [runner.one, {**runner.two, "enabled": False}])
    run = Mock(side_effect=RuntimeError("task failed"))
    original_path = runner.cfg.config_path
    with pytest.raises(RuntimeError, match="task failed"):
        runner.module.run_accounts(run)
    run.assert_called_once()
    assert runner.cfg.config_path == original_path
    assert runner.switch.call_args.args[0]["id"] == runner.one["id"]


def test_return_to_title_uses_phone_menu_and_confirms(runner, monkeypatch):
    from unittest.mock import call

    module = runner.module
    steps = Mock()
    monkeypatch.setattr(module, "screen", steps.screen)
    monkeypatch.setattr(module, "auto", steps.auto)
    monkeypatch.setattr(module, "wait_for_text", steps.wait_for_text)

    module.return_to_title()

    assert steps.mock_calls == [
        call.screen.change_to("menu"),
        call.auto.click_element((1845 / 1920, 952 / 1080, 48 / 1920, 54 / 1080), "crop"),
        call.wait_for_text("是否返回登录页面", crop=(0.35, 0.42, 0.3, 0.12), include=True),
        call.auto.click_element("确认", "text", crop=(0.51, 0.58, 0.20, 0.10)),
        call.wait_for_text("登出", crop=(0.92, 0.20, 0.08, 0.22)),
    ]


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_account_table_add_inline_edit_delete_and_default_off(isolated_config, qapp):
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QStyleOptionViewItem
    from app.sub_interfaces.multi_account_card import MultiAccountCard
    from module.config.accounts import profile_path
    card = MultiAccountCard()
    assert not card.switchButton.isChecked()
    assert not card.isExpand
    assert not card.removeButton.isEnabled()
    card.switchButton.setChecked(True)
    assert isolated_config.multi_account_enable is True
    assert not card.isExpand
    card.card.expandButton.click()
    card.expandAni.setCurrentTime(card.expandAni.duration())
    assert card.isExpand
    assert card.height() > card.card.height()
    card.addButton.click()
    assert card.table.rowCount() == 1
    assert card.table.cellWidget(0, 1).placeholderText() == "三月七"
    assert card.table.horizontalHeaderItem(2).text() == "账号ID"
    assert card.table.cellWidget(0, 2).placeholderText() == "账号ID(必填)"
    assert card.table.cellWidget(0, 3).placeholderText() == "UID"
    for column in (1, 2, 3):
        assert card.table.cellWidget(0, column) is not None
    for column, value in ((1, "主号"), (2, "147******79")):
        editor = card.table.cellWidget(0, column)
        editor.setText(value)
        editor.editingFinished.emit()
    assert isolated_config.multi_accounts[0]["name"] == "主号"
    assert isolated_config.multi_accounts[0]["login_name"] == "147******79"
    assert isolated_config.multi_accounts[0]["uid"] == ""
    for column in (1, 2, 3):
        option = QStyleOptionViewItem()
        card.table.delegate.initStyleOption(option, card.table.model().index(0, column))
        assert option.palette.color(QPalette.ColorRole.Text).alpha() == 0
        assert option.palette.color(QPalette.ColorRole.HighlightedText).alpha() == 0
    assert card.configureButton.isEnabled()
    saved_profile = profile_path(card.accounts[0])
    assert saved_profile.is_file()
    card.removeButton.click()
    assert isolated_config.multi_accounts == []
    assert card.table.rowCount() == 0
    assert not saved_profile.exists()
    card.card.expandButton.click()
    card.expandAni.setCurrentTime(card.expandAni.duration())
    assert not card.isExpand
    assert isolated_config.multi_account_enable is True
    assert card.height() == card.card.height()
    card.deleteLater()


def test_editing_a_row_selects_it_and_saves_changes(isolated_config, qapp):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QFocusEvent
    from PySide6.QtTest import QTest
    from app.sub_interfaces.multi_account_card import MultiAccountCard

    card = MultiAccountCard()
    card.switchButton.setChecked(True)
    card.setExpand(True)
    card.expandAni.setCurrentTime(card.expandAni.duration())
    card.show()
    card.addButton.click()
    card.addButton.click()
    assert card.table.cellWidget(1, 1).placeholderText() == "长夜月"
    editor = card.table.cellWidget(0, 2)
    QTest.mouseClick(editor, Qt.MouseButton.LeftButton)
    assert card.table.currentRow() == 0
    QTest.keyClicks(editor, "147******79")
    qapp.sendEvent(editor, QFocusEvent(QEvent.Type.FocusOut))
    QTest.mouseClick(card.table.cellWidget(1, 1), Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert isolated_config.multi_accounts[0]["login_name"] == "147******79"
    assert card.table.currentRow() == 1
    assert card.configureButton.isEnabled()
    card.close()


def test_hover_keeps_selected_account_and_path_opens_its_folder(isolated_config, qapp, monkeypatch):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QFocusEvent
    from PySide6.QtTest import QTest
    from app.sub_interfaces import multi_account_card as module
    from module.config.accounts import profile_path

    card = module.MultiAccountCard()
    card.switchButton.setChecked(True)
    card.setExpand(True)
    card.expandAni.setCurrentTime(card.expandAni.duration())
    card.resize(900, card.height())
    card.show()
    card.addButton.click()
    card.addButton.click()
    card.addButton.click()
    card.addButton.click()
    assert card.table.cellWidget(2, 1).placeholderText() == "账号3"
    assert card.table.cellWidget(3, 1).placeholderText() == "账号4"
    QTest.mouseClick(card.table.cellWidget(0, 1), Qt.MouseButton.LeftButton)
    selected_path = card.pathLabel.text()
    QTest.mouseMove(card.table.cellWidget(1, 1))
    qapp.sendEvent(card.table.cellWidget(1, 1), QFocusEvent(QEvent.Type.FocusIn))
    qapp.processEvents()
    assert card.table.currentRow() == 0
    assert card.pathLabel.text() == selected_path
    assert card.table.delegate.hoverRow == -1
    opened = Mock()
    monkeypatch.setattr(module, 'open_path', opened)
    card.pathLabel.linkActivated.emit('profile')
    opened.assert_called_once_with(profile_path(card.accounts[0]).resolve().parent)
    QTest.mouseClick(card.table.cellWidget(1, 1), Qt.MouseButton.LeftButton)
    assert card.table.currentRow() == 1
    assert card.accounts[1]['id'] in card.pathLabel.text()
    card.close()


def test_configure_button_emits_selected_account(isolated_config, qapp):
    from app.sub_interfaces.multi_account_card import MultiAccountCard

    card = MultiAccountCard()
    card.setExpand(True)
    card.expandAni.setCurrentTime(card.expandAni.duration())
    card.addButton.click()
    selected = []
    card.configureRequested.connect(selected.append)
    card.configureButton.click()
    assert selected[0]['id'] == isolated_config.multi_accounts[0]['id']
    assert selected[0]['display_name'] == '三月七'
    assert selected[0]["id"] in card.pathLabel.text()
    card.deleteLater()


def test_accounts_scroll_above_fixed_file_path_and_link_to_help(isolated_config, qapp):
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QLabel
    from app.sub_interfaces.multi_account_card import MultiAccountCard

    card = MultiAccountCard()
    card.resize(1000, card.height())
    card.switchButton.setChecked(True)
    card.setExpand(True)
    card.expandAni.setCurrentTime(card.expandAni.duration())
    card.show()
    card.addButton.click()
    qapp.processEvents()
    first_height = card.table.height()
    first_link_y = card.helpLink.y()
    scroll_height = card.accountScrollArea.height()
    card.addButton.click()
    qapp.processEvents()
    assert card.table.height() > first_height
    assert card.helpLink.y() > first_link_y
    assert card.accountScrollArea.height() > scroll_height
    assert card.pathLabel.y() > card.accountScrollArea.geometry().bottom()
    for _ in range(4):
        card.addButton.click()
    qapp.processEvents()
    expanded_height = card.table.height()
    card.addButton.click()
    card.addButton.click()
    qapp.processEvents()
    assert card.table.height() > expanded_height
    assert card.accountScrollArea.height() == 320
    file_y = card.pathLabel.y()
    assert card.table.verticalScrollBar().maximum() == 0
    scrollbar = card.accountScrollArea.verticalScrollBar()
    assert scrollbar.maximum() > 0
    scrollbar.setValue(0)
    link_y = card.helpLink.mapTo(card, QPoint()).y()
    scrollbar.setValue(scrollbar.maximum())
    qapp.processEvents()
    assert scrollbar.value() > 0
    assert card.helpLink.mapTo(card, QPoint()).y() < link_y
    assert card.pathLabel.y() == file_y
    assert not any(label.text().startswith('从当前登录账号') for label in card.findChildren(QLabel))
    requested = []
    card.accountHelpRequested.connect(lambda: requested.append(True))
    card.helpLink.linkActivated.emit('account-help')
    assert requested == [True]
    assert '查看账号管理教程' in card.helpLink.text()
    assert not hasattr(card, 'tutorialImage')
    card.close()


def test_account_page_expands_and_renders(isolated_config, qapp, tmp_path):
    from PySide6.QtTest import QTest
    from app.setting_interface import SettingInterface
    from module.config.accounts import add_account

    one, two = add_account(isolated_config), add_account(isolated_config)
    one.update(name="主号", login_name="147******79")
    two.update(name="小号", login_name="*.", uid="100000002")
    isolated_config.set_value("multi_accounts", [one, two])
    page = SettingInterface()
    page.resize(1120, 1080)
    group = next(page.stackedWidget.widget(i) for i in range(page.stackedWidget.count())
                 if page.stackedWidget.widget(i).objectName() == "AccountsInterface")
    page.stackedWidget.setCurrentWidget(group)
    page.show()
    QTest.qWait(10)
    collapsed = page.stackedWidget.height()
    group.multiAccountCard.switchButton.setChecked(True)
    assert not group.multiAccountCard.isExpand
    group.multiAccountCard.card.expandButton.click()
    group.multiAccountCard.expandAni.setCurrentTime(group.multiAccountCard.expandAni.duration())
    QTest.qWait(10)
    assert page.stackedWidget.height() > collapsed
    assert group.multiAccountCard.table.width() > 600
    assert group.multiAccountCard.configureButton.isVisible()
    import os
    preview = os.environ.get("MULTI_ACCOUNT_PREVIEW")
    if preview:
        page.grab().save(preview)
    page.close()


@pytest.mark.parametrize('login_name', ['222******22', '*.'])
def test_title_switch_clicks_keep_record_circle_and_observes_welcome(runner, monkeypatch, login_name):
    from tasks.game import multi_account as module
    from unittest.mock import call

    # 模拟切号流程中的游戏画面。
    auto = Mock()
    auto.find_element.return_value = True
    monkeypatch.setattr(module, "auto", auto)
    monkeypatch.setattr(module, "cfg", runner.cfg)
    monkeypatch.setattr(module, "screen", Mock())
    monkeypatch.setattr(module, "current_uid", lambda: "2")
    monkeypatch.setattr(module, "return_to_title", Mock())
    runner.two['login_name'] = login_name
    assert runner.original_switch(runner.two) == "2"
    module.return_to_title.assert_not_called()
    clicks = auto.click_element.call_args_list
    assert clicks[1] == call((690 / 1920, 560 / 1080, 22 / 1920, 22 / 1080), "crop")
    assert clicks[2].args[0] == "退出"
    if login_name == '*.':
        assert clicks[4].args == ('./assets/images/screen/login_account_star_dot.png', 'image', 0.9)
    else:
        assert clicks[4].args[0] == login_name
        assert clicks[4].kwargs["include"] is False
    assert clicks[5].args[0] == "进入游戏"
    assert any(c.args[0] == "欢迎进入游戏" for c in auto.find_element.call_args_list)
