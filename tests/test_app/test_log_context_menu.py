# coding:utf-8
"""任务日志区右键菜单测试：清空日志/打开日志文件夹入口。"""
import inspect
import sys

import pytest

@pytest.fixture(scope="session")
def qapp():
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        return app
    except ImportError:
        pytest.skip("PySide6 未安装")


class TestClearButtonRemoved:
    def test_clear_button_no_longer_created(self, qapp):
        from app.run.log_view import LogPanel
        assert not hasattr(LogPanel(), "clearButton")

    def test_clear_log_method_still_available(self):
        from app.content.run_controller import RunController
        assert hasattr(RunController, "clear_log")


class TestLogContextMenu:
    def _make_iface(self, qapp):
        from app.run.log_view import LogPanel
        iface = LogPanel()
        iface.view.setPlainText("line1\nline2")
        iface.clear_calls = []
        iface.clearRequested.connect(lambda: iface.clear_calls.append(1))
        return iface

    def _popup(self, iface, monkeypatch):
        from PySide6.QtCore import QPoint
        from qfluentwidgets import RoundMenu
        captured = {}

        def fake_exec(menu_self, pos, ani=True, aniType=None):
            captured['menu'] = menu_self

        monkeypatch.setattr(RoundMenu, 'exec', fake_exec)
        iface._menu(QPoint(0, 0))
        assert 'menu' in captured
        return captured['menu']

    def test_menu_has_expected_actions(self, qapp, monkeypatch):
        from PySide6.QtCore import Qt
        from module.localization import tr
        iface = self._make_iface(qapp)
        menu = self._popup(iface, monkeypatch)
        actions = menu.actions()
        texts = [action.text() for action in actions if not action.isSeparator()]
        assert texts == [tr('复制'), tr('全选'), tr('清空日志'), tr('打开日志文件夹')]
        # RoundMenu 的分隔符是列表项（DecorationRole 为 "seperator"），不在 actions() 里
        separator_count = sum(
            1 for row in range(menu.view.count())
            if menu.view.item(row).data(Qt.ItemDataRole.DecorationRole) == 'seperator'
        )
        assert separator_count == 1

    def test_copy_disabled_without_selection(self, qapp, monkeypatch):
        iface = self._make_iface(qapp)
        menu = self._popup(iface, monkeypatch)
        assert menu.actions()[0].isEnabled() is False

        iface.view.selectAll()
        menu = self._popup(iface, monkeypatch)
        assert menu.actions()[0].isEnabled() is True

    def test_clear_action_triggers_clear_log(self, qapp, monkeypatch):
        iface = self._make_iface(qapp)
        menu = self._popup(iface, monkeypatch)
        menu.actions()[2].trigger()  # 复制/全选/清空日志/打开日志文件夹
        assert iface.clear_calls == [1]

    def test_folder_action_opens_log_folder(self, qapp, monkeypatch):
        iface = self._make_iface(qapp)
        calls = []
        iface.folderRequested.connect(lambda: calls.append(1))
        menu = self._popup(iface, monkeypatch)
        menu.actions()[3].trigger()  # 打开日志文件夹
        assert calls == [1]

    def test_select_all_action_selects_text(self, qapp, monkeypatch):
        iface = self._make_iface(qapp)
        menu = self._popup(iface, monkeypatch)
        menu.actions()[1].trigger()  # 全选
        assert iface.view.textCursor().selectedText() != ''


class TestLogFolderCardUsesSharedHelper:
    def test_card_button_opens_log_folder(self):
        from app.card.comboboxsettingcard2 import ComboBoxSettingCardLog
        source = inspect.getsource(ComboBoxSettingCardLog._onClicked)
        assert 'open_log_folder' in source
