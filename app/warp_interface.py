# coding:utf-8
"""抽卡记录：按 UID 和卡池查看统计、保底、出货分布和明细，从游戏更新或导入导出记录。"""
from PySide6.QtCore import QPoint
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import (Action, DropDownPushButton, FluentIcon as FIF, IndeterminateProgressRing, InfoBar,
                            InfoBarPosition, MenuAnimationType, MessageBox, PrimarySplitPushButton, RoundMenu,
                            TitleLabel, ToolButton, qconfig)

from app.common.design_tokens import PAGE_MARGIN
from app.common.icon import UiIcon
from app.common.mascot import Mascot
from app.components.mascot_dialog import add_mascot
from app.content.gacha_dialogs import clear_dialog, export_dialog, import_dialog
from app.content.gacha_update import GachaUpdater
from app.gacha import style
from app.gacha.cards import Dashboard
from app.gacha.chips import PoolBar
from app.gacha.detail import DetailView
from app.gacha.empty import EmptyState
from app.overview.widgets import ElidedLabel
from app.pages.common import NoticeStrip, is_evernight, secondary, shared, style_primary
from module.gacha.store import GachaStore
from module.gacha.summary import load_summary
from module.localization import tr
from utils.desktop import open_path


class WarpInterface(QWidget):
    """页头固定；下面是空状态、统计和明细三种视图之一。数据在第一次显示时才读取。"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("warpInterface")
        self.store = shared(parent, "gachaStore", GachaStore)
        self.updater = shared(parent, "gachaUpdater", lambda: GachaUpdater(parent, store=self.store))
        self.summary = None
        self.pool = None
        self.mode = "stats"
        self._dirty = True
        self._issueFolder = None
        self._build()
        self.updater.progress.connect(self._onProgress)
        self.updater.finished.connect(self._onFinished)
        qconfig.themeChanged.connect(self._restyle)
        qconfig.themeColorChanged.connect(self._restyle)
        self.retranslateUi()
        self._setRunning(self.updater.running)
        self._restyle()

    def _build(self):
        self.titleLabel = TitleLabel(self)
        self.uidButton = DropDownPushButton(FIF.PEOPLE, "", self)
        self.uidMenu = RoundMenu(parent=self)
        self.uidGroup = QActionGroup(self.uidMenu)
        self.uidButton.setMenu(self.uidMenu)
        self.spinner = IndeterminateProgressRing(self)
        self.spinner.setFixedSize(16, 16)
        self.spinner.setStrokeWidth(2)
        self.spinner.hide()
        self.statusLabel = secondary(ElidedLabel(self, size=13))
        self.updateButton = PrimarySplitPushButton(FIF.SYNC, "", self)
        self.updateButton.clicked.connect(self.startUpdate)
        self.updateMenu = RoundMenu(parent=self)
        self.updateButton.setFlyout(self.updateMenu)
        self.transferButton = DropDownPushButton(UiIcon.IMPORT, "", self)
        self.transferMenu = RoundMenu(parent=self)
        self.transferButton.setMenu(self.transferMenu)
        self.moreButton = ToolButton(FIF.MORE, self)
        self.moreMenu = RoundMenu(parent=self)
        self.moreButton.clicked.connect(self._showMoreMenu)
        self.poolBar = PoolBar(self)
        self.poolBar.poolChanged.connect(self.selectPool)
        self.notice = NoticeStrip(self, kind="warning")
        self.notice.actionClicked.connect(self._openIssueFolder)
        self.notice.hide()
        self.emptyState = EmptyState(self)
        self.emptyState.updateRequested.connect(self.startUpdate)
        self.emptyState.importRequested.connect(self.importRecords)
        self.dashboard = Dashboard(self)
        self.dashboard.openDetails.connect(lambda: self.setMode("details"))
        self.detail = DetailView(self)
        self.detail.back.connect(lambda: self.setMode("stats"))
        self.stack = QStackedWidget(self)
        for widget in (self.emptyState, self.dashboard, self.detail):
            self.stack.addWidget(widget)

        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(self.titleLabel)
        top.addSpacing(12)
        top.addWidget(self.uidButton)
        top.addSpacing(6)
        top.addWidget(self.spinner)
        top.addWidget(self.statusLabel, 1)
        top.addSpacing(8)
        top.addWidget(self.updateButton)
        top.addWidget(self.transferButton)
        top.addWidget(self.moreButton)
        header = QVBoxLayout()
        header.setContentsMargins(PAGE_MARGIN, 18, PAGE_MARGIN, 14)
        header.setSpacing(14)
        header.addLayout(top)
        header.addWidget(self.poolBar)
        header.addWidget(self.notice)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(header)
        layout.addWidget(self.stack, 1)

    # ---- 文字与样式 ----

    def retranslateUi(self):
        self.titleLabel.setText(tr("抽卡记录"))
        self.transferButton.setText(tr("导入 / 导出"))
        self.moreButton.setToolTip(tr("更多操作"))
        self.emptyState.retranslateUi(self.updater.available, self.updater.unavailable_reason)
        self.detail.retranslateUi()
        self._setRunning(self.updater.running)
        self._dirty = True
        if self.isVisible():
            self.reload()
        else:
            self._buildMenus()

    def _restyle(self, *args):
        evernight = is_evernight()
        style_primary(self.updateButton, evernight)
        self.notice.setKind("warning", evernight)
        self.emptyState.restyle()
        self.dashboard.refresh()
        self.detail.restyle()
        for chip in self.poolBar.chips.values():
            chip.update()

    # ---- 数据 ----

    def showEvent(self, event):
        super().showEvent(event)
        if self._dirty:
            self.reload()

    def reload(self, uid=None):
        if uid is None and self.summary is not None and self.summary.selected is not None:
            uid = self.summary.selected.uid
        self.summary = load_summary(uid, store=self.store)
        self._dirty = False
        self._buildMenus()
        self._render()

    def selectAccount(self, uid):
        if self.summary is not None and self.summary.selected is not None and self.summary.selected.uid == uid:
            return
        self.reload(uid)

    def selectPool(self, pool_id):
        self.pool = pool_id
        self._render()

    def setMode(self, mode):
        self.mode = mode
        self._render()

    def currentPool(self):
        pools = self.summary.pools
        if self.pool in pools:
            return self.pool
        return next((key for key, stats in pools.items() if stats.total), next(iter(pools)))

    def _render(self):
        summary = self.summary
        if summary is None:
            return
        selected = summary.selected
        for widget in (self.uidButton, self.moreButton, self.poolBar):
            widget.setVisible(selected is not None)
        if selected is not None:
            self.uidButton.setText(tr("UID {uid}").format(uid=selected.uid))
        if not self.updater.running:
            self.statusLabel.setFullText(summary.updated_label if selected is not None else tr("还没有数据"))
        self._renderIssues(summary.issues)
        if selected is None:
            self.mode = "stats"
            self.stack.setCurrentWidget(self.emptyState)
            return
        key = self.currentPool()
        self.poolBar.setPools(summary.pools, key)
        if self.mode == "details":
            self.detail.setData(summary.pools, key)
            self.stack.setCurrentWidget(self.detail)
        else:
            self.dashboard.setStats(summary.pools[key])
            self.stack.setCurrentWidget(self.dashboard)

    def _renderIssues(self, issues):
        self.notice.setVisible(bool(issues))
        if not issues:
            self._issueFolder = None
            return
        lines = [tr("有 {count} 个抽卡记录文件没能读取，记录暂时不会显示：").format(count=len(issues))]
        for issue in issues[:3]:
            # 原因一行、路径一行：路径很长时也不会和原因挤在一起。
            lines += [issue.reason, str(issue.path)]
        if len(issues) > 3:
            lines.append(tr("还有 {count} 个").format(count=len(issues) - 3))
        self.notice.setText("\n".join(lines))
        self.notice.setAction(tr("打开所在文件夹"))
        path = issues[0].path
        self._issueFolder = path if path.is_dir() else path.parent

    # ---- 菜单 ----

    def _buildMenus(self):
        summary = self.summary
        accounts = summary.accounts if summary is not None else ()
        selected = summary.selected if summary is not None else None

        # RoundMenu.clear() leaves separator rows and menu-owned actions behind.
        for menu in (self.updateMenu, self.transferMenu, self.moreMenu, self.uidMenu):
            for action in menu.actions():
                if menu is self.uidMenu:
                    self.uidGroup.removeAction(action)
                action.deleteLater()
            menu.clear()
            menu.view.clear()

        self.updateMenu.addActions([
            Action(FIF.SYNC, tr("只获取新记录"), self.updateMenu, triggered=lambda: self.startUpdate("normal")),
            Action(FIF.HISTORY, tr("重新获取全部记录"), self.updateMenu, triggered=lambda: self.startUpdate("full")),
        ])

        self.transferMenu.addAction(Action(UiIcon.IMPORT, tr("导入 UIGF / SRGF 文件…"), self.transferMenu,
                                           triggered=self.importRecords))
        self.transferMenu.addSeparator()
        exports = [("uigf", tr("导出 UIGF"), False)]
        if len(accounts) > 1:
            exports.append(("uigf", tr("导出全部 {count} 个 UID（UIGF）").format(count=len(accounts)), True))
        exports += [("srgf", tr("导出 SRGF"), False), ("excel", tr("导出 Excel"), False)]
        for fmt, text, every in exports:
            action = Action(UiIcon.EXPORT, text, self.transferMenu,
                            triggered=lambda checked=False, fmt=fmt, every=every: self.exportRecords(fmt, every))
            action.setEnabled(selected is not None)
            self.transferMenu.addAction(action)
        self.transferMenu.addSeparator()
        self.copyAction = Action(UiIcon.LINK, tr("复制抽卡链接"), self.transferMenu, triggered=self.copyLink)
        self.copyAction.setEnabled(bool(self.updater.last_link))
        if not self.updater.last_link:
            self.copyAction.setToolTip(tr("更新一次记录后可以复制"))
        self.transferMenu.addAction(self.copyAction)

        self.moreMenu.addAction(Action(FIF.FOLDER, tr("打开数据文件夹"), self.moreMenu, triggered=self.openFolder))
        self.moreMenu.addSeparator()
        clear = Action(FIF.DELETE, tr("清空这个 UID 的记录…"), self.moreMenu, triggered=self.clearRecords)
        clear.setEnabled(selected is not None)
        self.moreMenu.addAction(clear)

        for account in accounts:
            action = Action(tr("UID {uid} · {count} 抽").format(uid=account.uid, count=style.number(account.count)),
                            self.uidMenu, triggered=lambda checked=False, uid=account.uid: self.selectAccount(uid))
            action.setCheckable(True)
            self.uidGroup.addAction(action)
            action.setChecked(selected is not None and account.uid == selected.uid)
            self.uidMenu.addAction(action)

    def _showMoreMenu(self):
        menu = self.moreMenu
        menu.adjustSize()
        x = self.moreButton.width() - menu.sizeHint().width() + menu.layout().contentsMargins().right()
        menu.exec(self.moreButton.mapToGlobal(QPoint(x, self.moreButton.height())), aniType=MenuAnimationType.DROP_DOWN)

    # ---- 更新 ----

    def startUpdate(self, mode="normal"):
        if mode not in ("normal", "full"):
            mode = "normal"
        if self.updater.running:
            return
        if not self.updater.available:
            self._info("warning", tr("不能从游戏更新"), self.updater.unavailable_reason)
            return
        if self.updater.start(mode):
            self._setRunning(True)

    def _setRunning(self, running):
        available = self.updater.available
        self.updateButton.setEnabled(available and not running)
        self.updateButton.setText(tr("正在更新…") if running else tr("更新记录"))
        self.updateButton.setToolTip("" if available else self.updater.unavailable_reason)
        self.emptyState.setUpdateEnabled(available and not running)
        self.spinner.setVisible(running)
        if running:
            self.statusLabel.setFullText(tr("正在获取跃迁记录…"))
        elif self.summary is not None:
            self.statusLabel.setFullText(self.summary.updated_label if self.summary.selected is not None
                                         else tr("还没有数据"))

    def _onProgress(self, text, title=None):
        self.statusLabel.setFullText(tr("{title}：{text}").format(title=title, text=text) if title else text)

    def _onFinished(self, result):
        self._setRunning(False)
        if result.success:
            self.reload(result.uid)
            added = sum(result.added.values())
            text = (tr("UID {uid} 新增 {count} 条记录").format(uid=result.uid, count=style.number(added)) if added
                    else tr("UID {uid} 没有新记录").format(uid=result.uid))
            self._info("success", tr("抽卡记录已更新"), text)
        else:
            self.reload()
            self._info("error", tr("更新失败"), result.reason)

    # ---- 导入、导出、清空 ----

    def importRecords(self, *args):
        outcome = import_dialog(self.window(), store=self.store)
        if outcome.status == "success":
            self.reload(outcome.uids[0] if outcome.uids else None)
            self._info("success", tr("导入成功"), tr("UID {uids}").format(uids=", ".join(outcome.uids)))
        elif outcome.status == "failed":
            self._transferFailed(tr("导入失败"), outcome.reason)

    def exportRecords(self, fmt, every=False):
        selected = self.summary.selected if self.summary is not None else None
        if selected is None:
            return
        outcome = export_dialog(self.window(), fmt, None if every else selected.uid, store=self.store)
        if outcome.status == "success":
            self._info("success", tr("导出成功"), outcome.reason or str(outcome.path or ""))
        elif outcome.status == "failed":
            self._transferFailed(tr("导出失败"), outcome.reason)

    def _transferFailed(self, title, reason):
        box = MessageBox(title, reason, self.window())
        box.cancelButton.hide()
        box.yesButton.setText(tr("确定"))
        add_mascot(box, Mascot.STARTLED)
        box.exec()

    def clearRecords(self, *args):
        selected = self.summary.selected if self.summary is not None else None
        if selected is None:
            return
        outcome = clear_dialog(self.window(), selected.uid, store=self.store)
        if outcome.status == "success":
            self.summary = None
            self.reload()
            self._info("success", tr("已清空"), tr("UID {uid} 的记录已清空，原文件的备份留在数据文件夹里").format(uid=selected.uid))
        elif outcome.status == "failed":
            self._info("error", tr("清空失败"), outcome.reason)

    def copyLink(self, *args):
        try:
            self.updater.copy_link()
        except Exception as exc:
            self._info("warning", tr("复制失败"), str(exc))
            return
        self._info("success", tr("已复制抽卡链接"), tr("链接里有临时登录凭据，只发给你信任的工具"))

    def openFolder(self, *args):
        folder = self.store.directory
        open_path(str(folder if folder.exists() else folder.parent))

    def _openIssueFolder(self):
        if self._issueFolder is not None:
            open_path(str(self._issueFolder))

    def _info(self, kind, title, content):
        duration = 8000 if kind == "error" else 4000
        getattr(InfoBar, kind)(title, content or "", duration=duration, position=InfoBarPosition.TOP, parent=self)
