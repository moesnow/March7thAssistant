from datetime import date
from threading import get_ident
import time
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget
from qfluentwidgets import ComboBox, MessageBox, PlainTextEdit
from app.common.mascot import Mascot
from tests.test_app.mascot_assertions import assert_pose

from app.content import gacha_dialogs as dialogs, gacha_update as worker
from app.content.gacha_model import Column, GachaFilterProxy, GachaTableModel, Role
from module.gacha.stats import all_stats, pool_stats
from module.gacha.store import GachaStore
from module.gacha.update import UpdateResult
from tests.test_app.test_warp_import import data, put
from tests.test_module.test_gacha_stats import draw
from tests.test_module.test_gacha_transfer import uigf
from utils import paths


@pytest.fixture
def ui(qtbot, tmp_path):
    window = QWidget()
    qtbot.addWidget(window)
    window.resize(800, 700)
    window.show()
    return window, GachaStore(paths.select(tmp_path))


def test_model_columns_roles_order_and_filter(ui):
    window, _ = ui
    stats = all_stats([draw(1, 5, name="March"), draw(2, 3, "21", day=2), draw(10, 4, name="MARCH", day=3)])
    model = GachaTableModel((r for s in stats.values() for r in s.details), window)
    proxy = GachaFilterProxy(model, window)
    assert proxy.rowCount() == 3 and proxy.columnCount() == 6
    assert model.headerData(Column.PITY, Qt.Orientation.Horizontal) == "第几抽（保底内）"
    cell = proxy.index(0, 0)
    assert [cell.data(role) for role in (Role.ID, Role.TIME, Role.STARS, Role.PITY, Role.NUMBER, Role.POOL)] == [
        "10", "2026-11-03 08:00:00", 4, 1, 2, "11"]
    assert [proxy.index(0, col).data() for col in Column] == [
        "2026-11-03 08:00:00", "MARCH", "角色", 4, "角色活动跃迁", 1]
    assert proxy.set_filters(stars=[4, 5], keyword="arch", start=date(2026, 11, 3), end="2026-11-03") == 2
    proxy.sort(Column.STARS, Qt.SortOrder.DescendingOrder)
    assert proxy.index(0, 0).data(Role.ID) == "1"
    model.set_rows(stats["21"].details)
    assert proxy.rowCount() == 0
    assert proxy.set_filters() == 1 and proxy.index(0, Column.POOL).data() == "Fate[UBW]角色联动跃迁"


def test_proxy_ten_thousand(qtbot, capsys):
    rows = pool_stats("11", [draw(i, 5 if i % 5 == 0 else 3, name="March") for i in range(10000)]).details
    model = GachaTableModel(rows)
    proxy = GachaFilterProxy(model)
    assert proxy.rowCount() == 10000
    elapsed = []
    for stars, count in (([5], 2000), ([3], 8000), ([3, 5], 10000)):
        start = time.perf_counter()
        assert proxy.set_filters(stars=stars, keyword="MA", end="2026-11-03") == count
        elapsed.append((time.perf_counter() - start) * 1000)
    with capsys.disabled():
        print(f"\n10,000 detail rows · slowest filter {max(elapsed):.2f} ms")
    assert max(elapsed) < 200


def answer(monkeypatch, actions, mode=0, *, expected_poses=None):
    observations = []
    execute = MessageBox.exec
    actions = iter(actions)
    def respond(dialog):
        combo = dialog.findChild(ComboBox)
        if combo is not None:
            assert combo.currentIndex() == 0
            combo.setCurrentIndex(mode)
        summary = dialog.findChild(PlainTextEdit)
        content = dialog.contentLabel.text() + (summary.toPlainText() if summary is not None else "")
        cancel_focused = dialog.cancelButton.isDefault() and dialog.focusWidget() is dialog.cancelButton
        if expected_poses is not None:
            expected = expected_poses[len(observations)]
            mascot = getattr(dialog, "mascotLabel", None)
            if expected is None:
                assert mascot is None
            else:
                assert_pose(mascot.pixmap(), expected)
                assert summary is None or dialog.textLayout.indexOf(summary) >= 0
        observations.append((dialog.titleLabel.text(), content, cancel_focused))
        button = dialog.yesButton if next(actions) else dialog.cancelButton
        QTimer.singleShot(0, button.click)
        return execute(dialog)
    monkeypatch.setattr(MessageBox, "exec", respond)
    return observations


@pytest.mark.parametrize("mode,actions,expected", [(0, [True, True], "success"), (1, [True, True], "success"),
                                                 (0, [False], "cancelled"), (1, [True, False], "cancelled")])
def test_import_two_uids_confirmations(ui, tmp_path, monkeypatch, mode, actions, expected):
    window, store = ui
    store.write("111", data((1, 2), "111"))
    incoming = data((2, 3), "111")
    if mode == 1:
        incoming["info"]["lang"] = "en-us"
        incoming["list"][0]["name"] = "March 7th"
    source = put(tmp_path / "import.json", uigf(incoming, data((9,), "222")))
    monkeypatch.setattr(dialogs.QFileDialog, "getOpenFileName", lambda *args: (str(source), ""))
    seen = answer(monkeypatch, actions, mode, expected_poses=(None, Mascot.BOX if mode == 1 else None))
    result = dialogs.import_dialog(window, store=store)
    assert result.status == expected and seen[0][0] == "选择导入方式"
    if len(actions) == 2:
        title, counts, default_cancel = seen[1]
        assert all(token in counts for token in ("UID：111", "UID：222", "文件记录：2", "重复记录：1", "新增记录：1"))
        if mode == 1:
            assert "警告" in title and default_cancel
    if expected == "success":
        assert result.uids == ("111", "222")
        assert len(store.read("111")["list"]) == (2 if mode else 3)
    else:
        assert not store.path("222").exists() and not list(store.directory.glob("*.bak"))


def test_dialog_empty_first_import_invalid_and_export_cancel(ui, tmp_path, monkeypatch):
    window, store = ui
    chosen = Mock(return_value=("", ""))
    monkeypatch.setattr(dialogs.QFileDialog, "getOpenFileName", chosen)
    monkeypatch.setattr(dialogs.QFileDialog, "getSaveFileName", lambda *a: ("", ""))
    monkeypatch.setattr(MessageBox, "exec", lambda *a: pytest.fail("unexpected confirmation"))
    assert dialogs.import_dialog(window, store=store).status == "cancelled"
    assert dialogs.export_dialog(window, "excel", "111", store=store).status == "cancelled"
    source = tmp_path / "input.json"
    chosen.return_value = (str(source), "")
    assert dialogs.import_dialog(window, store=store).status == "failed"
    put(source, data(uid="111"))
    assert dialogs.import_dialog(window, store=store).uids == ("111",)


@pytest.mark.parametrize("format,uid,name", [("srgf", "111", "SRGF_111.json"), ("uigf", None, "UIGF_all.json"),
                                             ("excel", "111", "抽卡记录_111.xlsx")])
def test_export_opens_folder(ui, tmp_path, monkeypatch, format, uid, name):
    window, store = ui
    store.write("111", data(uid="111"))
    dest = tmp_path / ("out.xlsx" if format == "excel" else "out.json")
    chosen = Mock(return_value=(str(dest), ""))
    monkeypatch.setattr(dialogs.QFileDialog, "getSaveFileName", chosen)
    opened = Mock(return_value=True)
    monkeypatch.setattr(dialogs.QDesktopServices, "openUrl", opened)
    outcome = dialogs.export_dialog(window, format, uid, store=store)
    assert chosen.call_args.args[2] == name and chosen.call_args.args[3].endswith(f"(*{dest.suffix})")
    assert outcome.status == "success" and outcome.path == dest and dest.is_file()
    assert opened.call_args.args[0].toLocalFile().replace("\\", "/") == dest.parent.as_posix()


@pytest.mark.parametrize("ok", [True, False])
def test_clear_dialog_only_selected(ui, monkeypatch, ok):
    window, store = ui
    for uid in ("111", "222"):
        store.write(uid, data(uid=uid))
    original = store.path("111").read_bytes()
    seen = answer(monkeypatch, [ok], expected_poses=(Mascot.BOX,))
    outcome = dialogs.clear_dialog(window, "111", store=store)
    assert "111" in seen[0][1] and store.path("222").is_file()
    if ok:
        assert outcome.uids == ("111",) and outcome.path.read_bytes() == original and not store.path("111").exists()
    else:
        assert outcome.status == "cancelled" and store.path("111").read_bytes() == original


def test_worker_signals_last_success_and_platform(ui, qtbot, monkeypatch):
    window, store = ui
    monkeypatch.setattr(worker.GachaUpdater, "_last_successful_link", None)
    updater = worker.GachaUpdater(window, store=store)
    results = iter([UpdateResult(True, "111", {"11": 2}, link="local-fixture"),
                    UpdateResult(False, None, {}, "fixture failure")])
    jobs = []
    main_thread = get_ident()
    def run(store, mode, report):
        jobs.append((mode, get_ident()))
        report("progress", "title")
        return next(results)
    monkeypatch.setattr(worker, "update_records", run)
    monkeypatch.setattr(worker, "unavailable_reason", lambda: "")
    assert updater.last_link is None
    progress = []
    updater.progress.connect(lambda msg, title: progress.append((msg, title)))
    for mode in ("normal", "full"):
        with qtbot.waitSignal(updater.finished, timeout=5000) as done:
            assert updater.start(mode) and updater.running and not updater.start()
        assert done.args[0].success == (mode == "normal") and not updater.running
    assert progress == [("progress", "title")] * 2
    assert [mode for mode, thread in jobs if thread != main_thread] == ["normal", "full"]
    copied = Mock()
    monkeypatch.setattr("utils.clipboard.copy", copied)
    assert worker.GachaUpdater(store=store).last_link == updater.last_link
    updater.copy_link()
    copied.assert_called_once_with("local-fixture")
    monkeypatch.setattr(worker, "unavailable_reason", lambda: "仅支持 Windows")
    assert not updater.available and updater.unavailable_reason and not updater.start()
