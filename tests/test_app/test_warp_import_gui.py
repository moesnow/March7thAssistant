"""Click through the page and its real confirmation dialogs using isolated files."""
from unittest.mock import Mock

import pytest
from qfluentwidgets import InfoBar, MessageBox

from app.content import gacha_dialogs as dialogs
from app.warp_interface import WarpInterface
from tests.test_app.test_gacha_adapters import answer
from tests.test_app.test_warp_import import data, put
from tests.test_module.test_gacha_transfer import uigf
from utils import paths


@pytest.fixture
def page(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_layout", paths.select(tmp_path, tmp_path / "profile"))
    page = WarpInterface()
    qtbot.addWidget(page)
    page.resize(1100, 720)
    page.show()
    return page


def choose_file(monkeypatch, path):
    monkeypatch.setattr(dialogs.QFileDialog, "getOpenFileName", lambda *args: (str(path), ""))


def click_import(page):
    if page.emptyState.isVisible():
        page.emptyState.importButton.click()
    else:
        next(action for action in page.transferMenu.actions() if action.text().startswith("导入 ")).trigger()


@pytest.mark.parametrize("empty_file", [False, True])
def test_first_import_without_confirmation(page, tmp_path, monkeypatch, empty_file):
    uid = "100000001"
    if empty_file:
        page.store.write(uid, data(()))
        page.reload()
    choose_file(monkeypatch, put(tmp_path / "input.json", data()))
    monkeypatch.setattr(MessageBox, "exec", lambda *_: pytest.fail("unexpected confirmation"))
    click_import(page)
    assert page.summary.selected.uid == uid and page.summary.selected.count == 2
    assert page.stack.currentWidget() is page.dashboard
    assert page.store.read(uid)["list"] == data()["list"]


def test_file_dialog_cancel(page, monkeypatch):
    choose_file(monkeypatch, "")
    click_import(page)
    assert page.stack.currentWidget() is page.emptyState
    assert not page.findChildren(InfoBar)
    assert not page.store.path("100000001").exists()


@pytest.mark.parametrize("mode,clicks", [(0, [False]), (0, [True, False]), (0, [True, True]),
                                         (1, [True, False]), (1, [True, True])])
def test_merge_or_replace_after_preview(page, tmp_path, monkeypatch, mode, clicks):
    uid = "100000001"
    page.store.write(uid, data())
    page.reload()
    target = page.store.path(uid)
    before = target.read_bytes()
    choose_file(monkeypatch, put(tmp_path / "in.json", data((2, 3))))
    seen = answer(monkeypatch, clicks, mode)
    click_import(page)
    assert len(seen) == len(clicks) and seen[0][0] == "选择导入方式"
    if len(clicks) == 2:
        title, counts, cancel_default = seen[1]
        assert ("替换" in title) == bool(mode)
        assert all(s in counts for s in ("UID：100000001", "现有记录：2", "文件记录：2", "新增记录：1", "重复记录：1"))
        assert f"导入后：{2 if mode else 3} 条" in counts
        if mode:
            assert cancel_default and "原有记录不会保留在当前列表中" in counts
    if all(clicks):
        expected = ["2", "3"] if mode else ["1", "2", "3"]
        assert [r["id"] for r in page.store.read(uid)["list"]] == expected
        assert page.summary.selected.count == len(expected)
        assert next(target.parent.glob("*.bak")).read_bytes() == before
    else:
        assert target.read_bytes() == before and not list(target.parent.glob("*.bak"))
        assert not page.findChildren(InfoBar)


def test_repeat_import_marks_only_duplicates(page, tmp_path, monkeypatch):
    uid = "100000001"
    page.store.write(uid, data())
    page.reload()
    choose_file(monkeypatch, put(tmp_path / "in.json", data()))
    seen = answer(monkeypatch, [True, False])
    click_import(page)
    assert "新增记录：0 条" in seen[1][1] and "重复记录：2 条" in seen[1][1]


def test_two_accounts_in_one_file(page, tmp_path, monkeypatch):
    first, second = "100000001", "100000002"
    page.store.write(first, data())
    page.reload()
    choose_file(monkeypatch, put(tmp_path / "in.json", uigf(data((2, 3)), data((9,), second))))
    seen = answer(monkeypatch, [True, True])
    click_import(page)
    assert all(f"UID：{uid}" in seen[1][1] for uid in (first, second))
    assert {a.uid: a.count for a in page.summary.accounts} == {first: 3, second: 1}
    assert page.summary.selected.uid == first


def test_other_uid_does_not_replace_current_account(page, tmp_path, monkeypatch):
    first, second = "100000001", "100000002"
    page.store.write(first, data())
    page.reload()
    before = page.store.path(first).read_bytes()
    choose_file(monkeypatch, put(tmp_path / "in.json", data((3,), second)))
    monkeypatch.setattr(MessageBox, "exec", lambda *_: pytest.fail("unexpected confirmation"))
    click_import(page)
    assert page.summary.selected.uid == second and page.store.read(second)["list"][0]["id"] == "3"
    assert page.store.path(first).read_bytes() == before


def test_replace_unreadable_file_from_gui(page, tmp_path, monkeypatch):
    uid = "100000001"
    target = page.store.path(uid)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"{broken")
    page.reload()
    assert page.notice.isVisible()
    choose_file(monkeypatch, put(tmp_path / "in.json", data()))
    seen = answer(monkeypatch, [True, True], mode=1)
    click_import(page)
    assert "无法统计" in seen[1][1] and seen[1][2]
    assert not page.notice.isVisible() and page.summary.selected.count == 2
    assert next(target.parent.glob("*.bak")).read_bytes() == b"{broken"


def test_export_then_clear_through_page(page, tmp_path, monkeypatch):
    uid = "100000001"
    page.store.write(uid, data())
    page.reload()
    original = page.store.path(uid).read_bytes()
    destination = tmp_path / "records.json"
    monkeypatch.setattr(dialogs.QFileDialog, "getSaveFileName", lambda *args: (str(destination), ""))
    opened = Mock(return_value=True)
    monkeypatch.setattr(dialogs.QDesktopServices, "openUrl", opened)
    next(a for a in page.transferMenu.actions() if a.text() == "导出 SRGF").trigger()
    assert destination.is_file() and opened.call_args.args[0].toLocalFile() == tmp_path.as_posix()
    seen = answer(monkeypatch, [False, True])
    for accepted in (False, True):
        next(a for a in page.moreMenu.actions() if a.text().startswith("清空")).trigger()
        assert page.store.path(uid).exists() != accepted
    assert [s[0] for s in seen] == ["清空抽卡记录"] * 2 and uid in seen[0][1]
    assert page.stack.currentWidget() is page.emptyState
    assert next(page.store.directory.glob("*.bak")).read_bytes() == original
