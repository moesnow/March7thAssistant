"""总览的真实 Qt 渲染与交互。所有任务入口由记录调用的模型代替。"""
from dataclasses import replace
from unittest.mock import Mock, call

import pytest
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtWidgets import QApplication, QBoxLayout, QWidget
from qfluentwidgets import Theme, qconfig, setTheme
from shiboken6 import isValid

from app import overview_interface as ui
from app.overview import greeting
from module.localization import tr
from module.overview.samples import sample_snapshot
from module.overview.types import Button
from module.config import cfg
from utils.tasks import supported_tasks


@pytest.fixture
def page(qtbot):
    host = QWidget()
    qtbot.addWidget(host)
    host.navigate = Mock()
    host.resize(1060, 740)
    widget = ui.OverviewInterface(host)
    widget.resize(host.size())
    widget.model = Mock()
    host.show()
    yield widget
    host.hide()


@pytest.mark.parametrize("theme", ["light", "dark", "evernight"])
@pytest.mark.parametrize("state", ["ready", "running", "completed", "failed", "setup", "stopped"])
def test_sample_renders(page, state, theme):
    previous = qconfig.get(qconfig.themeMode)
    try:
        setTheme(Theme.LIGHT if theme == "light" else Theme.DARK, save=False)
        page.setEvernightMode(theme == "evernight")
        snapshot = sample_snapshot(state)
        page.render(snapshot)
        QApplication.processEvents()
        assert page.greeting._mode() == theme and page.greeting.pill.text() == snapshot.greeting.badge
        assert page.greeting.titleLabel.fullText() == snapshot.greeting.title
        assert page.greeting.phaseBox.isVisible() == (state == "running")
        assert page.greeting.mascot.pose().value == snapshot.greeting.mascot
        art = page.greeting.mascot.imageRect()  # 压到底和弹起时都不会被裁掉
        assert art.width() * (1 + greeting.SQUASH_WIDTH) <= page.greeting.mascot.width()
        assert art.height() * (1 + greeting.SQUASH_HEIGHT * greeting.STRETCH) < page.greeting.height() - 1
        image = page.view.grab()
        assert image.width() >= 900 and image.height() >= page.greeting.height() and not image.isNull()
    finally:
        setTheme(previous, save=False)


@pytest.mark.parametrize("state", ["ready", "running", "completed", "failed", "setup", "stopped"])
def test_greeting_buttons_dispatch(page, state):
    snapshot = sample_snapshot(state)
    page.render(snapshot)
    methods = {"start_full": "start_full", "continue": "start_full", "stop": "stop",
               "toggle_pause": "toggle_pause", "retry_step": "retry_step", "start_task": "start_task"}
    for action in snapshot.greeting.buttons:
        widget = next(b for b in page.greeting._buttons if b.text().removesuffix(" ›") == action.text)
        if action.id == "choose_task":
            continue
        page.model.reset_mock()
        page.window().navigate.reset_mock()
        widget.click()
        if action.id in methods:
            args = (action.target,) if action.id in ("start_task", "retry_step") else ()
            assert page.model.method_calls == [getattr(call, methods[action.id])(*args), call.request_refresh()]
        else:
            page.window().navigate.assert_called_once_with(action.link)
            assert not page.model.method_calls


def test_run_one_task_menu_matches_backend(page, monkeypatch):
    monkeypatch.setattr(cfg, "config", dict(cfg.config, control_backend="adb", ui_profile="touch_720"))
    actions = supported_tasks(cfg)
    captured = []

    def open_menu(menu, *args, **kwargs):
        captured.extend(menu.actions())
        for action in captured:
            action.trigger()
    monkeypatch.setattr(ui.RoundMenu, "exec", open_menu)
    snapshot = sample_snapshot("ready")
    page.render(snapshot)
    choose = next(b for b in snapshot.greeting.buttons if b.id == "choose_task")
    next(w for w in page.greeting._buttons if w.text() == choose.text).click()
    assert [a.text() for a in captured] == [tr(name) for name in actions.values()]
    assert page.model.start_task.call_args_list == [call(key) for key in actions]


def test_default_shortcuts_launch_the_selected_task(page):
    page.render(sample_snapshot("ready"))
    routine, power, currency_wars, divergent = page.shortcutsCard._buttons
    routine.click()
    power.click()
    for button, name in ((currency_wars, "货币战争"), (divergent, "差分宇宙")):
        assert button.text() == tr(name)
        actions = button.menu().actions()
        assert [action.text() for action in actions] == [tr("运行一次"), tr("循环运行"), tr("中途接管")]
        for action in actions:
            action.trigger()
    assert page.model.launch_shortcut.call_args_list == [
        call("routine"), call("power"),
        call("currencywars"), call("currencywarsloop"), call("currencywarstemp"),
        call("divergent"), call("divergentloop"), call("divergenttemp"),
    ]


def test_shortcut_rows_keep_their_spacing_on_first_show(page, qtbot):
    page.render(sample_snapshot("ready"))
    card = page.shortcutsCard
    qtbot.waitUntil(lambda: card._columns == 2 and card._buttons[0].isVisible())
    QApplication.processEvents()

    for column in range(2):
        upper, lower = card._buttons[column], card._buttons[column + 2]
        assert lower.y() - upper.geometry().bottom() - 1 >= card.grid.verticalSpacing()


def test_empty_shortcuts_card_tells_why(page):
    snapshot = sample_snapshot("ready")
    card = page.shortcutsCard
    for values, text in (
        ({"shortcuts_hidden": True}, "当前连接方式没有可用的快捷启动"),
        ({}, "还没有快捷启动，点「编辑」添加常用操作"),
        ({"unavailable": ("shortcuts",)}, "暂时读不到快捷启动"),
    ):
        page.render(replace(snapshot, shortcuts=(), **values))
        assert card.emptyLabel.isVisible() and card.emptyLabel.text() == tr(text) and not card._buttons
        assert card.editLink.isVisible() == ("unavailable" not in values)
    page.render(snapshot)
    assert not card.emptyLabel.isVisible() and len(card._buttons) == 4


def test_retry_without_step_starts_original_task(page):
    snapshot = sample_snapshot("failed")
    retry = Button("start_task", tr("重新运行"), target="power")
    page.render(replace(snapshot, greeting=replace(snapshot.greeting, buttons=(retry,))))
    page.greeting._buttons[0].click()
    page.model.start_task.assert_called_once_with("power")


def test_fold_and_breakpoint(page, qtbot):
    snapshot = sample_snapshot("ready")
    page.render(snapshot)
    card = page.planCard
    active = [item for item in snapshot.plan if item.status not in ("disabled", "unsupported")]
    assert 0 < len(active) < len(snapshot.plan)
    assert [row.item for row in card.rows] == active
    card.foldLink.click()
    assert [row.item for row in card.rows] == list(snapshot.plan)
    card.foldLink.click()
    assert [row.item for row in card.rows] == active
    for width, wide in ((ui.WIDE_LAYOUT - 1, False), (ui.WIDE_LAYOUT, True), (ui.WIDE_LAYOUT + 1, True)):
        page.resize(width + page.width() - page.viewport().width(), page.height())
        qtbot.waitUntil(lambda: page.viewport().width() == width)
        assert page.statsGrid.itemAtPosition(0 if wide else 1, 2 if wide else 0).widget() is page.weeklyCard
        expected = QBoxLayout.Direction.LeftToRight if wide else QBoxLayout.Direction.BottomToTop
        assert page.bottomLayout.direction() == expected
        if wide:
            qtbot.waitUntil(lambda: card.geometry().right() < page.sideWidget.geometry().left())
        else:
            qtbot.waitUntil(lambda: page.sideWidget.geometry().bottom() < card.geometry().top())


def test_power_card_counts_up_between_readings(page):
    snapshot = sample_snapshot("ready")  # 17 分钟前为 186
    card = page.powerCard
    card._elapsed = Mock(elapsed=Mock(return_value=0))
    page.render(snapshot)
    assert (card.valueLabel.text(), card.unitLabel.text(), card.badge.text()) == ("188", "/ 300", "+1 · 1:00")
    assert card.meter._fraction == 188 / 300 and "186" in card.noteLabel.fullText()
    for elapsed, value, countdown in ((59_000, "188", "0:01"), (60_000, "189", "6:00"), (421_000, "190", "5:59")):
        card._elapsed.elapsed.return_value = elapsed
        card._refresh()
        assert (card.valueLabel.text(), card.badge.text()) == (value, f"+1 · {countdown}")
        assert card._timer.isActive()
    card.hide()
    assert not card._timer.isActive()
    card.show()
    assert card._timer.isActive()
    page.render(replace(snapshot, power=replace(snapshot.power, value=300)))
    assert (card.valueLabel.text(), card.badge.text()) == ("300", tr("已回满")) and not card._timer.isActive()
    page.render(replace(snapshot, power=replace(snapshot.power, value=None)))
    assert card.valueLabel.text() == "—" and card.badge.isHidden() and not card._timer.isActive()
    page.render(replace(snapshot, power=None, unavailable=("power",)))
    assert card.valueLabel.text() == "—" and card.noteLabel.fullText() == tr("暂时读不到开拓力")


def test_context_menu_changes_background_and_mascot(page, monkeypatch, tmp_path):
    chosen = str(tmp_path / "custom.webp")
    write = Mock()
    monkeypatch.setattr(cfg, "set_value", write)
    monkeypatch.setattr(ui.QFileDialog, "getOpenFileName", lambda *_: (chosen, ""))
    snapshot = sample_snapshot("ready")
    for label, background, shown, expected in (
        ("更换问候区背景", "", True, ("banner_path", chosen)),
        ("恢复默认背景", chosen, True, ("banner_path", "")),
        ("隐藏 Q 版小人", "", True, ("overview_show_mascot", False)),
        ("显示 Q 版小人", "", False, ("overview_show_mascot", True)),
    ):
        def open_menu(menu, *args):
            next(action for action in menu.actions() if action.text() == tr(label)).trigger()
        monkeypatch.setattr(ui.RoundMenu, "exec", open_menu)
        page.render(replace(snapshot, background=background, show_mascot=shown))
        page.greeting.customContextMenuRequested.emit(QPoint(12, 12))
        write.assert_called_once_with(*expected)
        page.model.refresh.assert_called_once_with()
        write.reset_mock()
        page.model.reset_mock()


def test_theme_signal_disconnects_on_destruction(qapp):
    previous = qconfig.get(qconfig.themeMode)
    widget = ui.OverviewInterface()
    widget.render(sample_snapshot("ready"))
    widget.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not isValid(widget)
    try:
        setTheme(Theme.DARK, save=False)
        setTheme(Theme.LIGHT, save=False)
        QApplication.processEvents()
    finally:
        setTheme(previous, save=False)


def test_reduced_motion_suppresses_mascot_bounce(page, monkeypatch, qtbot):
    page.render(sample_snapshot("ready"))
    mascot = page.greeting.mascot
    for enabled in (False, True):
        monkeypatch.setattr(greeting, "animations_enabled", lambda: enabled)
        qtbot.mouseClick(mascot, Qt.MouseButton.LeftButton)
        assert (mascot.animation.state() == mascot.animation.State.Running) == enabled


def test_mascot_squash_follows_android(page, monkeypatch, qtbot):
    monkeypatch.setattr(greeting, "animations_enabled", lambda: True)
    page.render(sample_snapshot("ready"))
    mascot = page.greeting.mascot
    animation = mascot.animation
    qtbot.mousePress(mascot, Qt.MouseButton.LeftButton)
    assert animation.state() == animation.State.Stopped  # 松手才算点击
    qtbot.mouseRelease(mascot, Qt.MouseButton.LeftButton)
    animation.pause()
    for elapsed, scale in ((0, (1, 1)), (70, (1.14, 0.78)), (194, (0.9479, 1.0819)), (319, (1.0194, 0.9695))):
        animation.setCurrentTime(elapsed)
        assert mascot._scale() == pytest.approx(scale, abs=0.001)
    animation.setCurrentTime(194)
    stretched = mascot._squash
    mascot.bounce()  # 连点：从当前的形变继续
    animation.pause()
    animation.setCurrentTime(0)
    assert mascot._squash == stretched
    animation.setCurrentTime(70)
    assert mascot._scale() == pytest.approx((1.14, 0.78))
    animation.setCurrentTime(greeting.BOUNCE_MS)
    assert mascot._scale() == (1, 1)


@pytest.mark.parametrize("accepted", [True, False])
def test_edit_link_refreshes_only_after_save(page, monkeypatch, accepted):
    from app.overview import shortcut_dialog
    dialog = Mock()
    dialog.return_value.exec.return_value = accepted
    monkeypatch.setattr(shortcut_dialog, "ShortcutEditDialog", dialog)
    page.render(sample_snapshot("ready"))
    assert page.shortcutsCard.editLink.isVisible()
    page.shortcutsCard.editLink.click()
    dialog.assert_called_once_with(page.window())
    assert page.model.request_refresh.call_count == int(accepted)
