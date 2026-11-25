"""Exercise the redesigned warp page through the controls a user operates."""
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject, Qt, Signal
from PySide6.QtGui import QAction
from qfluentwidgets import InfoBar, Theme, qconfig, setTheme, setThemeColor

from app import warp_interface
from app.common.design_tokens import EVERNIGHT_RED, MARCH7TH_PINK
from app.common.mascot import Mascot
from app.content.gacha_dialogs import Outcome
from app.content.gacha_model import Column, Role
from app.gacha import detail, style
from module import localization
from module.gacha import samples
from module.gacha.update import UpdateResult
from tests.test_app.test_gacha_adapters import answer
from utils import paths


@pytest.fixture
def make_page(qtbot, tmp_path, monkeypatch):
    def create(case="accounts", *, show=True):
        root = tmp_path / "empty" if case == "empty" else samples.write_samples(tmp_path / "cases")[case]
        monkeypatch.setattr(paths, "_layout", paths.select(tmp_path, root))
        page = warp_interface.WarpInterface()
        qtbot.addWidget(page)
        page.resize(1080, 600)
        if show:
            page.show()
        return page
    return create


def action(menu, text):
    return next(a for a in menu.actions() if a.text() == text)


def messages(page):
    return [(bar.title, bar.content) for bar in page.findChildren(InfoBar)]


def test_legacy_records_split_on_first_show(make_page):
    page = make_page("legacy", show=False)
    old = page.store.legacy_file
    assert page.summary is None and old.is_file()
    original = old.read_bytes()
    page.show()
    assert page.stack.currentWidget() is page.dashboard and page.summary.selected.uid == samples.UID_A
    assert not old.exists() and next(page.store.directory.glob("*.bak")).read_bytes() == original


def test_empty_page(make_page):
    page = make_page("empty")
    assert page.stack.currentWidget() is page.emptyState
    assert page.statusLabel.fullText() == "还没有数据"
    assert page.emptyState.titleLabel.text() == "还没有抽卡记录"
    assert page.emptyState.importButton.isEnabled() and not page.notice.isVisible()
    assert not any(w.isVisible() for w in (page.uidButton, page.poolBar, page.moreButton))
    assert not action(page.transferMenu, "导出 UIGF").isEnabled()
    assert not page.copyAction.isEnabled()


def test_non_windows_explains_which_action_is_available(make_page, monkeypatch):
    monkeypatch.setattr("module.gacha.update.sys", SimpleNamespace(platform="linux"))
    page = make_page("empty")
    reason = "从游戏更新抽卡记录仅支持 Windows。"
    assert page.updateButton.toolTip() == page.emptyState.subtitleLabel.text() == reason
    assert not page.updateButton.isEnabled()
    assert not page.emptyState.updateButton.isVisible() and page.emptyState.importButton.isVisible()
    assert all(not row.isVisible() for row, label in page.emptyState.steps)


def test_broken_file_opens_its_containing_folder(make_page, monkeypatch):
    opened = Mock()
    monkeypatch.setattr(warp_interface, "open_path", opened)
    page = make_page("broken")
    assert page.stack.currentWidget() is page.emptyState and page.notice.isVisible()
    assert str(page.store.legacy_file) in page.notice.textLabel.text()
    assert page.summary.issues[0].reason in page.notice.textLabel.text()
    assert page.notice.actionButton.text() == "打开所在文件夹"
    page.notice.actionButton.click()
    opened.assert_called_once_with(str(page.store.legacy_file.parent))
    assert page.store.legacy_file.read_bytes() == b"{broken"


def test_figures_pity_distribution_and_recent_rows(make_page, qtbot):
    page = make_page()
    dashboard = page.dashboard
    cards = (dashboard.totalCard, dashboard.fiveCountCard, dashboard.averageCard, dashboard.fourCard)
    assert [c.titleLabel.text() for c in cards] == ["总抽数", "五星", "平均出金", "四星"]
    assert [c.value.parts() for c in cards] == [("1,257", ""), ("20", "出率 1.59%"), ("60.5", "抽"), ("146", "出率 11.6%")]
    assert dashboard.totalCard.noteLabel.fullText() == "2024-04-26 至 2026-11-22"
    assert dashboard.averageCard.noteLabel.fullText() == "最快 12 抽 · 最慢 90 抽"
    pity = dashboard.pityCard
    assert pity.value.parts() == ("47", "抽未出五星") and pity.fourLabel.plainText() == "四星 3 / 10"
    assert pity.distanceLabel.plainText() == "距离保底 43 抽（约 6,880 星琼）"
    assert pity.bar.toolTip() == "第 74 抽起五星概率提升，第 90 抽必定获得五星"
    chart = dashboard.distributionCard.chart
    assert [bucket.count for bucket in chart._buckets] == [0, 1, 0, 2, 3, 2, 5, 5, 2]
    assert "81～90 抽：2 个五星" in chart.accessibleDescription()
    five = dashboard.fiveCard
    assert five.list._rows[0].name == "昔涟"
    for height, shown in ((160, 3), (360, 8)):
        five.list.setFixedHeight(height)
        qtbot.waitUntil(lambda: five.list.shown() == shown)
        assert five.footLabel.fullText() == f"共 20 个五星，这里显示最近 {shown} 个"
    page.poolBar.chips["12"].click()
    assert five.list.shown() == 1 and five.footLabel.fullText() == "共 1 个五星 · 表格中可按星级、名称筛选"


def test_pool_chips_shrink_to_stay_on_one_line(make_page, qapp):
    bar = make_page().poolBar
    chips = list(bar.chips.values())
    gaps = bar.flow.horizontalSpacing() * (len(chips) - 1)
    normal, narrow = (sum(chip.widthFor(compact) for chip in chips) + gaps for compact in (False, True))
    assert narrow < normal and bar.chips["2"].accessibleName() == "新手跃迁 50 · 已结束"
    bar.setParent(None)
    bar.show()
    for width, compact, rows in ((normal + 1, False, 1), (normal, True, 1), (narrow + 1, True, 1), (narrow, False, 2)):
        bar.resize(width, 80)
        for _ in range(3):
            qapp.processEvents()
        assert {chip._compact for chip in chips} == {compact} and len({chip.y() for chip in chips}) == rows, width
        assert bar.heightForWidth(width) == rows * 32 + (rows - 1) * 8
    bar.deleteLater()


def test_departure_warp_finished_and_early_five(make_page):
    page = make_page()
    page.poolBar.chips["2"].click()
    pity = page.dashboard.pityCard
    assert pity.value.parts() == ("50", "抽 · 已结束") and not pity.fourLabel.isVisible()
    assert pity.bar.toolTip() == pity.distanceLabel.plainText() == "新手跃迁最多 50 抽，已经抽完"
    early = samples.sample_account(samples.UID_B)
    for row in early["list"]:
        row["gacha_type"] = "2"
    early["list"][0]["rank_type"] = "5"
    page.store.write(samples.UID_B, early)
    page.selectAccount(samples.UID_B)
    assert pity.value.parts() == ("32", "抽 · 已获得五星") and pity.fourLabel.isVisible()
    assert pity.bar.toolTip() == pity.distanceLabel.plainText() == "还能再抽 18 抽"


def test_switch_pool_uid_details_and_back(make_page):
    page = make_page()
    page.poolBar.chips["12"].click()
    assert page.currentPool() == "12" and page.dashboard.totalCard.value.parts()[0] == "35"
    page.dashboard.fiveCard.detailsButton.click()
    assert page.stack.currentWidget() is page.detail and page.detail.proxy.rowCount() == 35
    page.detail.backButton.click()
    assert page.stack.currentWidget() is page.dashboard
    action(page.uidMenu, f"UID {samples.UID_B} · 32 抽").trigger()
    assert page.uidButton.text() == f"UID {samples.UID_B}"
    selected = action(page.uidMenu, f"UID {samples.UID_B} · 32 抽")
    selected.trigger()
    assert selected.isChecked() and sum(a.isChecked() for a in page.uidMenu.actions()) == 1
    assert page.dashboard.totalCard.value.parts()[0] == "0"
    assert page.dashboard.fiveCard.footLabel.fullText() == "这个卡池还没有记录"
    page.poolBar.chips["11"].click()
    assert page.dashboard.fiveCard.footLabel.fullText() == "还没有五星，表格中可按星级、名称筛选"


def test_menu_rows_and_action_ownership_stay_bounded(make_page):
    page = make_page()
    menus = (page.transferMenu, page.moreMenu, page.uidMenu, page.updateMenu)
    def sizes():
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        return [(m.view.count(), len(m.findChildren(QAction))) for m in menus]
    initial = sizes()
    assert [rows for rows, owned in initial] == [8, 3, 2, 2]
    for uid in (samples.UID_B, samples.UID_A):
        page.selectAccount(uid)
        page.poolBar.chips["12"].click()
        page.setMode("details")
        page.setMode("stats")
        page.retranslateUi()
        assert sizes() == initial


def test_detail_filters_combine_and_reset(make_page, monkeypatch):
    class Today(date):
        @classmethod
        def today(cls):
            return date(2026, 11, 15)

    monkeypatch.setattr(detail, "date", Today)
    page = make_page()
    page.dashboard.fiveCard.detailsButton.click()
    view = page.detail
    proxy = view.proxy
    assert view.table.isColumnHidden(Column.POOL) and view.countLabel.fullText() == "共 1,257 条"
    dates = [proxy.index(i, Column.TIME).data() for i in range(proxy.rowCount())]
    assert dates == sorted(dates, reverse=True)
    view.starChips[3].click()
    view.starChips[4].click()
    assert proxy.rowCount() == 20
    view.allPools.click()
    assert not view.table.isColumnHidden(Column.POOL) and proxy.rowCount() == 23
    assert view.countLabel.fullText() == "筛选出 23 条，共 1,391 条"
    view.searchBox.setText("白露")
    assert proxy.rowCount() == 2
    assert {proxy.index(i, 0).data(Role.POOL) for i in range(2)} == {"11", "2"}
    view.searchBox.setText("没有这样的名称")
    assert proxy.rowCount() == 0 and view.emptyLabel.isVisible() and view.emptyLabel.text() == "没有符合条件的记录"
    view.searchBox.clear()
    view.starChips[3].click()
    view.starChips[4].click()
    records = samples.sample_account(samples.UID_A)["list"]
    for index, days in enumerate((30, 90, 365), 1):
        view.periodBox.setCurrentIndex(index)
        first = (Today.today() - timedelta(days=days - 1)).isoformat()
        ids = {r["id"] for r in records if first <= r["time"][:10] <= Today.today().isoformat()}
        assert ids and len(ids) < len(records)
        assert {proxy.index(i, 0).data(Role.ID) for i in range(proxy.rowCount())} == ids
    view.periodBox.setCurrentIndex(0)
    assert view.countLabel.fullText() == "共 1,391 条" and not view.emptyLabel.isVisible()


class FakeUpdater(QObject):
    progress = Signal(str, object)
    finished = Signal(object)
    available = True
    unavailable_reason = ""
    last_link = None
    running = False

    def start(self, mode):
        self.mode = mode
        self.running = True
        return True

    def finish(self, result):
        self.running = False
        if result.success:
            self.last_link = result.link
        self.finished.emit(result)


def test_update_actions_follow_signals_and_returned_uid(make_page, monkeypatch):
    updater = FakeUpdater()
    monkeypatch.setattr(warp_interface, "GachaUpdater", lambda *args, **kwargs: updater)
    page = make_page()
    assert page.summary.selected.uid == samples.UID_A and not page.copyAction.isEnabled()
    page.updateButton.button.click()
    assert updater.mode == "normal" and not page.updateButton.isEnabled() and page.spinner.isVisible()
    assert page.updateButton.text() == "正在更新…" and not page.emptyState.updateButton.isEnabled()
    updater.progress.emit("第 3 页", "角色活动跃迁")
    assert page.statusLabel.fullText() == "角色活动跃迁：第 3 页"
    updater.progress.emit("正在整理", None)
    assert page.statusLabel.fullText() == "正在整理"
    updater.finish(UpdateResult(True, samples.UID_B, {"11": 2, "12": 3}, link="fixture-link"))
    assert page.summary.selected.uid == samples.UID_B and page.copyAction.isEnabled()
    assert page.updateButton.isEnabled() and not page.spinner.isVisible()
    assert page.statusLabel.fullText() == page.summary.updated_label
    assert ("抽卡记录已更新", f"UID {samples.UID_B} 新增 5 条记录") in messages(page)
    action(page.updateMenu, "重新获取全部记录").trigger()
    assert updater.mode == "full"
    updater.finish(UpdateResult(False, None, {}, "本次连接超时"))
    assert page.summary.selected.uid == samples.UID_B and page.copyAction.isEnabled()
    assert page.updateButton.isEnabled() and not page.spinner.isVisible()
    assert ("更新失败", "本次连接超时") in messages(page)
    action(page.updateMenu, "只获取新记录").trigger()
    assert updater.mode == "normal"
    updater.finish(UpdateResult(True, samples.UID_B, {}, link="fixture-link"))
    assert ("抽卡记录已更新", f"UID {samples.UID_B} 没有新记录") in messages(page)


@pytest.mark.parametrize("operation", ["import", "export", "clear"])
@pytest.mark.parametrize("status", ["success", "failed", "cancelled"])
def test_transfer_menu_outcomes(make_page, monkeypatch, operation, status):
    page = make_page()
    uid = samples.UID_A
    original = page.summary
    reason = "测试文件被占用"
    if operation == "clear" and status == "success":
        page.store.clear(uid)
    affected = (samples.UID_B,) if operation == "import" else (uid,) if operation == "clear" else ()
    outcome = Outcome(status, affected, reason if status == "failed" else "", page.store.path(uid))
    dialog = Mock(return_value=outcome)
    monkeypatch.setattr(warp_interface, operation + "_dialog", dialog)
    seen = (answer(monkeypatch, [True], expected_poses=(Mascot.STARTLED,))
            if status == "failed" and operation in ("import", "export") else [])
    if operation == "import":
        action(page.transferMenu, "导入 UIGF / SRGF 文件…").trigger()
        dialog.assert_called_once_with(page.window(), store=page.store)
    elif operation == "export":
        action(page.transferMenu, "导出全部 2 个 UID（UIGF）").trigger()
        dialog.assert_called_once_with(page.window(), "uigf", None, store=page.store)
    else:
        action(page.moreMenu, "清空这个 UID 的记录…").trigger()
        dialog.assert_called_once_with(page.window(), uid, store=page.store)

    if status != "success":
        assert page.summary is original
        if status == "failed" and operation in ("import", "export"):
            title = "导入失败" if operation == "import" else "导出失败"
            assert [entry[:2] for entry in seen] == [(title, reason)]
        assert messages(page) == ([("清空失败", reason)] if (operation, status) == ("clear", "failed") else [])
    elif operation == "export":
        assert page.summary is original and ("导出成功", str(outcome.path)) in messages(page)
    else:
        assert page.summary.selected.uid == samples.UID_B
        expected = (("导入成功", f"UID {samples.UID_B}") if operation == "import" else
                    ("已清空", f"UID {uid} 的记录已清空，原文件的备份留在数据文件夹里"))
        assert expected in messages(page)


@pytest.mark.parametrize("fmt, label", [("uigf", "导出 UIGF"), ("srgf", "导出 SRGF"), ("excel", "导出 Excel")])
def test_single_uid_export_menu(make_page, monkeypatch, fmt, label):
    page = make_page()
    action(page.uidMenu, f"UID {samples.UID_B} · 32 抽").trigger()
    export = Mock(return_value=Outcome("cancelled"))
    monkeypatch.setattr(warp_interface, "export_dialog", export)
    action(page.transferMenu, label).trigger()
    export.assert_called_once_with(page.window(), fmt, samples.UID_B, store=page.store)


def test_live_language_and_three_themes(make_page):
    page = make_page()
    previous = localization.get_current_language()
    theme, color = qconfig.theme, qconfig.get(qconfig.themeColor)
    try:
        localization.load_language("en_US")
        page.retranslateUi()
        tr = localization.tr
        pairs = [(page.titleLabel.text(), "抽卡记录"), (page.transferButton.text(), "导入 / 导出"),
                 (page.updateMenu.actions()[0].text(), "只获取新记录"), (page.poolBar.chips["11"].text(), "角色活动跃迁"),
                 (page.dashboard.totalCard.titleLabel.text(), "总抽数"), (page.dashboard.pityCard.titleLabel.text(), "当前保底"),
                 (page.dashboard.distributionCard.titleLabel.text(), "五星出货分布")]
        page.dashboard.fiveCard.detailsButton.click()
        pairs.append((page.detail.backButton.text(), "返回统计"))
        headers = ("时间", "名称", "类型", "星级", "卡池", "第几抽（保底内）")
        pairs.extend((page.detail.proxy.headerData(c, Qt.Orientation.Horizontal), name) for c, name in zip(Column, headers))
        for actual, source in pairs:
            assert actual == tr(source) and actual != source
        for current, accent in ((Theme.LIGHT, MARCH7TH_PINK), (Theme.DARK, MARCH7TH_PINK), (Theme.DARK, EVERNIGHT_RED)):
            setTheme(current, save=False)
            setThemeColor(accent, save=False)
            assert style.evernight() == (accent == EVERNIGHT_RED)
            for mode in ("stats", "details"):
                page.setMode(mode)
                assert not page.grab().isNull()
            assert page.detail.proxy.rowCount() == 1257
    finally:
        localization.load_language(previous)
        setTheme(theme, save=False)
        setThemeColor(color, save=False)
