"""Data and backup controls for the existing desktop settings page."""
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog
from qfluentwidgets import (FluentIcon as FIF, InfoBar, InfoBarPosition, MessageBox, PushButton,
                            PushSettingCard)

from app.common.mascot import Mascot
from app.components.mascot_dialog import add_mascot
from module.localization import tr
from utils import data_backup, data_migration, paths


def open_data(parent):
    folder = Path(paths.data_dir())
    try:
        folder.mkdir(parents=True, exist_ok=True)
        if QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder))):
            return
        reason = str(folder)
    except OSError as exc:
        reason = str(exc)
    InfoBar.error(tr("无法打开数据文件夹"), reason, parent=parent)


def show_migration(window, result):
    status = result["status"]
    options = dict(parent=window, position=InfoBarPosition.TOP, duration=-1, orient=Qt.Vertical)
    if status == "success":
        bar = InfoBar.success(tr("数据已移到 userdata 文件夹"),
                              tr("设置、账号、流程编排和记录现在都保存在这个文件夹里，迁移前的副本在 userdata\\backup。"), **options)
        button = PushButton(tr("打开文件夹"), bar)
        button.clicked.connect(lambda: open_data(window))
        bar.addWidget(button)
        bar.adjustSize()
    elif status == "pending":
        labels = {paths.LOGS: tr("日志"), paths.SCREENSHOTS: tr("截图"), "browser": tr("云游戏浏览器数据")}
        bar = InfoBar.warning(tr("部分数据还在原来的位置"),
                              tr("{items}暂时沿用原位置，下次启动会再试。").format(
                                  items="、".join(labels.get(s, s) for s in result["pending"])), **options)
    elif status == "recovery_pending":
        bar = InfoBar.error(tr(data_migration.recovery_instruction()),
                            result["reason"] + "\n" + result["backup_dir"], **options)
    elif status == "attention":
        bar = InfoBar.warning(tr("数据操作没有完成"), paths.data_dir() + "\n" + result["reason"], **options)
    elif status in ("failed", "deferred"):
        reason = result["reason"]
        if reason in data_migration.REASONS.values():
            reason = tr(reason)
        bar = InfoBar.warning(tr("数据迁移没有完成"),
                              tr("这次继续使用原来的位置，下次启动会再试。原因：{reason}").format(
                                  reason=reason), **options)
    else:
        return
    data_migration.acknowledge()
    return bar


def build_data_cards(owner, parent):
    owner.folderCard = PushSettingCard(tr("打开文件夹"), FIF.FOLDER, tr("数据文件夹"), paths.data_dir())
    owner.backupCard = PushSettingCard(tr("备份到文件"), FIF.SAVE, tr("备份数据"),
        tr("把设置、账号、流程编排和各种记录打包成一个 zip 文件，不含日志和云游戏浏览器数据"))
    owner.restoreCard = PushSettingCard(tr("选择备份文件"), FIF.HISTORY, tr("从备份恢复"),
        tr("恢复前会自动备份当前数据，恢复后需要重启小助手"))
    owner.importCard = PushSettingCard(tr("选择文件夹"), FIF.FOLDER_ADD, tr("从旧版文件夹导入"),
        tr("选择以前的小助手文件夹，把其中的设置、账号、流程编排和记录复制过来，导入前会自动备份当前数据"))
    owner.diagnosticCard = PushSettingCard(tr("导出"), FIF.DOCUMENT, tr("导出排查包"),
        tr("隐藏 Token、密码、Cookie 和推送密钥后，导出设置和最近一次运行的日志，可以直接发到群里或 Issue"))
    for card in (owner.folderCard, owner.backupCard, owner.restoreCard, owner.importCard, owner.diagnosticCard):
        card.hBoxLayout.setStretch(2, 1)
        card.hBoxLayout.setStretch(4, 0)
        card.vBoxLayout.setAlignment(card.contentLabel, Qt.AlignmentFlag(0))
        card.contentLabel.setWordWrap(True)
        card.setParent(parent)
    owner.folderCard.contentLabel.setToolTip(paths.data_dir())
    owner.folderCard.clicked.connect(lambda: open_data(parent.window()))
    owner.backupCard.clicked.connect(lambda: save_data(parent, False))
    owner.diagnosticCard.clicked.connect(lambda: save_data(parent, True))
    owner.restoreCard.clicked.connect(lambda: restore_data(parent, False))
    owner.importCard.clicked.connect(lambda: restore_data(parent, True))


def save_data(parent, diagnostics):
    title = tr("导出排查包") if diagnostics else tr("备份数据")
    filename = "March7th-diagnostics.zip" if diagnostics else "March7th-backup.zip"
    path, _ = QFileDialog.getSaveFileName(parent, title, filename, "ZIP (*.zip)")
    if path:
        try:
            (data_backup.diagnostics if diagnostics else data_backup.backup)(path)
        except Exception as exc:
            InfoBar.error(tr("文件保存失败"), str(exc), parent=parent.window())
        else:
            InfoBar.success(tr("文件已保存"), path, parent=parent.window())

def restore_data(parent, importing):
    window = parent.window()
    running = getattr(window, "runController", None)
    if running and running.isTaskRunning():
        InfoBar.warning(tr("请先停止正在运行的任务"), "", parent=window)
        return
    if importing:
        path = QFileDialog.getExistingDirectory(parent, tr("从旧版文件夹导入"))
    else:
        path, _ = QFileDialog.getOpenFileName(parent, tr("选择备份文件"), "", "ZIP (*.zip)")
    if not path:
        return
    try:
        (data_backup.import_folder if importing else data_backup.restore)(path)
    except data_backup.RecoveryPendingError as exc:
        from module.config import cfg
        cfg.writes_suspended = True
        InfoBar.error(tr(data_migration.recovery_instruction()), str(exc), duration=-1, parent=window)
    except data_backup.TaskRunningError:
        InfoBar.warning(tr("请先停止正在运行的任务"), "", parent=window)
    except Exception as exc:
        InfoBar.error(tr("数据操作没有完成"), str(exc), duration=-1, parent=window)
    else:
        from module.config import cfg
        # Prevent the old in-memory settings/window geometry from overwriting restored bytes on exit.
        cfg.writes_suspended = True
        message = MessageBox(tr("数据已导入") if importing else tr("数据已恢复"),
                             tr("请重新启动小助手以使用这份数据。"), window)
        message.yesButton.setText(tr("关闭小助手"))
        message.cancelButton.hide()
        add_mascot(message, Mascot.STAMP)
        message.exec()
        window.quitApp()
