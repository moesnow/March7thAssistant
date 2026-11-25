"""File selection and confirmations. The owner displays the returned outcome."""
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog
from qfluentwidgets import ComboBox, MessageBox, PlainTextEdit

from app.common.mascot import Mascot
from app.components.mascot_dialog import add_mascot
from module.gacha.store import GachaStore
from module.gacha.transfer import export_records, prepare_import, save_import
from module.localization import tr


@dataclass(frozen=True, slots=True)
class Outcome:
    status: str
    uids: tuple[str, ...] = ()
    reason: str = ""
    path: Path | None = None


def _choose_mode(parent):
    box = MessageBox(tr("选择导入方式"),
                     tr("默认合并会保留现有记录。只有希望用文件内容覆盖现有记录时，才选择强制替换。"), parent)
    choice = ComboBox(box.widget)
    choice.addItems([tr("安全合并（推荐）"), tr("强制替换现有记录")])
    box.textLayout.addWidget(choice)
    box.widget.setFixedHeight(box.widget.height() + choice.sizeHint().height() + 12)
    box.yesButton.setText(tr("下一步"))
    box.cancelButton.setText(tr("取消"))
    return ("merge", "replace")[choice.currentIndex()] if box.exec() else None


def _counts(plan):
    return tr("账号 UID：{uid}\n现有记录：{existing} 条\n文件记录：{incoming} 条\n新增记录：{added} 条\n重复记录：{duplicates} 条\n导入后：{total} 条").format(
        uid=plan.data["info"]["uid"], existing=tr("无法统计") if plan.existing_unreadable else plan.existing_count,
        incoming=plan.incoming_count, added=tr("无法统计") if plan.existing_unreadable else plan.added_count,
        duplicates=tr("无法统计") if plan.existing_unreadable else plan.duplicate_count, total=len(plan.data["list"]))


def _confirm_import(parent, plans, mode):
    replace = mode == "replace"
    intro = (tr("此操作会用导入文件中的记录替换目前保存的全部记录。原有记录不会保留在当前列表中。")
             if replace else tr("导入方式：保留已有记录，补充新记录，自动跳过重复内容。"))
    counts = "\n\n".join(_counts(plan) for plan in plans)
    box = MessageBox(tr("警告：替换现有抽卡记录") if replace else tr("确认导入抽卡记录"),
                     intro if len(plans) > 1 else intro + "\n\n" + counts, parent)
    if replace:
        add_mascot(box, Mascot.BOX)
    if len(plans) > 1:
        summary = PlainTextEdit(box.widget)
        summary.setReadOnly(True)
        summary.setPlainText(counts)
        summary.setFixedHeight(min(260, max(100, parent.height() // 3)))
        box.textLayout.addWidget(summary)
        box.widget.setFixedHeight(box.widget.height() + summary.height() + 12)
    box.yesButton.setText(tr("确认替换") if replace else tr("确认合并"))
    box.cancelButton.setText(tr("取消"))
    if replace:
        box.yesButton.setAutoDefault(False)
        box.cancelButton.setDefault(True)
        box.cancelButton.setFocus()
    return box.exec()


def import_dialog(parent, *, store=None):
    store = store or GachaStore()
    try:
        path, _ = QFileDialog.getOpenFileName(parent, tr("导入抽卡记录"), "", tr("UIGF / SRGF 格式 (*.json)"))
        if not path:
            return Outcome("cancelled")
        plans = prepare_import(path, "replace", store=store)
        if any(p.existing_count or p.existing_unreadable for p in plans):
            mode = _choose_mode(parent.window())
            if mode is None:
                return Outcome("cancelled")
            if mode == "merge":
                plans = prepare_import(path, mode, store=store)
            if not _confirm_import(parent.window(), plans, mode):
                return Outcome("cancelled")
        return Outcome("success", save_import(plans, store=store))
    except Exception as exc:
        return Outcome("failed", reason=str(exc))


def export_dialog(parent, format, uid=None, *, store=None):
    try:
        if format == "excel":
            title, name, pattern = tr("导出为 Excel 文件"), f"{tr('抽卡记录')}_{uid}.xlsx", tr("Excel 文件 (*.xlsx)")
        elif format == "srgf":
            title, name, pattern = tr("导出抽卡记录"), f"SRGF_{uid}.json", tr("SRGF 格式 (*.json)")
        else:
            title = tr("导出抽卡记录")
            name, pattern = f"UIGF_{uid or 'all'}.json", tr("UIGF 格式 (*.json)")
        path, _ = QFileDialog.getSaveFileName(parent, title, name, pattern)
        if not path:
            return Outcome("cancelled")
        dest = export_records(path, format, uid, store=store)
        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(dest.parent)))
        return Outcome("success", path=dest, reason="" if opened else tr("文件已导出，无法打开所在文件夹。"))
    except Exception as exc:
        return Outcome("failed", reason=str(exc))


def clear_dialog(parent, uid, *, store=None):
    store = store or GachaStore()
    try:
        with store.reading():
            original = store.path(uid).read_bytes()
        box = MessageBox(tr("清空抽卡记录"), tr("账号 UID：{uid}").format(uid=uid) + "\n" +
                         tr("确定要清空抽卡记录吗？此操作不可撤销。"), parent.window())
        box.yesButton.setText(tr("确认"))
        box.cancelButton.setText(tr("取消"))
        add_mascot(box, Mascot.BOX)
        if not box.exec():
            return Outcome("cancelled")
        backup = store.clear(uid, expected=original)
        return Outcome("success", (str(uid),), path=backup)
    except Exception as exc:
        return Outcome("failed", reason=str(exc))
