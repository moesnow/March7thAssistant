# coding:utf-8
"""本地操作模式切换到后台前的确认：先确认再写配置，取消时恢复原选项。"""
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32" or not hasattr(sys, 'getwindowsversion'),
    reason="GUI 测试仅在 Windows 平台运行"
)


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


@pytest.fixture
def card(qapp):
    from qfluentwidgets import FluentIcon
    from app.card.expandable_switch_setting_card import ExpandableComboBoxSettingCard
    config = MagicMock()
    config.get_value.return_value = 'foreground'
    answers = []
    confirm = MagicMock(side_effect=lambda _value: answers.pop(0))
    with patch('module.config.cfg', config):
        widget = ExpandableComboBoxSettingCard(
            'local_control_mode', FluentIcon.GAME, '本地操作模式',
            texts={'前台': 'foreground', '后台': 'background'}, confirm=confirm)
    emitted = []
    widget.currentIndexChanged.connect(emitted.append)
    yield SimpleNamespace(widget=widget, config=config, confirm=confirm, answers=answers, emitted=emitted)
    widget.deleteLater()


def test_cancel_keeps_previous_option_and_never_writes_config(card):
    card.answers.append(False)
    card.widget.comboBox.setCurrentIndex(1)  # 用户选择“后台”
    card.confirm.assert_called_once_with('background')
    assert card.widget.comboBox.currentIndex() == 0
    assert card.widget.comboBox.currentText() == '前台'
    card.config.set_value.assert_not_called()
    assert card.emitted == []


def test_confirm_writes_config_and_notifies(card):
    card.answers.append(True)
    card.widget.comboBox.setCurrentIndex(1)
    card.config.set_value.assert_called_once_with('local_control_mode', 'background')
    assert card.emitted == [1]
    # 取消后再次选择同一项仍会询问，确认后才生效
    card.answers.append(True)
    card.widget.comboBox.setCurrentIndex(0)
    assert card.config.set_value.call_args.args == ('local_control_mode', 'foreground')


def test_cancel_then_retry_asks_again(card):
    card.answers.extend([False, True])
    card.widget.comboBox.setCurrentIndex(1)
    card.widget.comboBox.setCurrentIndex(1)
    assert card.confirm.call_count == 2
    card.config.set_value.assert_called_once_with('local_control_mode', 'background')


def test_card_without_confirm_saves_immediately(qapp):
    from qfluentwidgets import FluentIcon
    from app.card.expandable_switch_setting_card import ExpandableComboBoxSettingCard
    config = MagicMock()
    config.get_value.return_value = 'a'
    with patch('module.config.cfg', config):
        widget = ExpandableComboBoxSettingCard('x', FluentIcon.GAME, 'x', texts={'A': 'a', 'B': 'b'})
    widget.comboBox.setCurrentIndex(1)
    config.set_value.assert_called_once_with('x', 'b')
    widget.deleteLater()


@pytest.fixture
def confirm_mode(qapp, monkeypatch):
    """调用设置页的确认逻辑，MessageBox 换成替身；answer 为对话框 exec() 的返回值。"""
    import app.setting_interface as module
    state = SimpleNamespace(boxes=[], answer=1)

    def make_box(title, content, parent):
        box = MagicMock()
        box.title, box.content, box.parent = title, content, parent
        box.exec.return_value = state.answer
        state.boxes.append(box)
        return box

    monkeypatch.setattr(module, 'MessageBox', make_box)
    host = SimpleNamespace(window=lambda: 'main-window')
    confirm = module.SettingInterface._SettingInterface__confirmLocalControlMode
    state.call = lambda value: confirm(host, value)
    return state


def test_switching_to_foreground_needs_no_dialog(confirm_mode):
    assert confirm_mode.call('foreground') is True
    assert confirm_mode.boxes == []


@pytest.mark.parametrize('answer', [1, 0])
def test_switching_to_background_explains_limits_and_follows_choice(confirm_mode, answer):
    confirm_mode.answer = answer
    assert confirm_mode.call('background') is bool(answer)
    box = confirm_mode.boxes[0]
    assert box.parent == 'main-window'
    for limit in ('借用鼠标', '不能最小化', '保持系统解锁', '临时把游戏切到前台', '独立程序'):
        assert limit in box.content
    box.yesButton.setText.assert_called_once()
    box.cancelButton.setText.assert_called_once()
