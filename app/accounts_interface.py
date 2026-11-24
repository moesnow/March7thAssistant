"""账号：登录快照、多账号轮流、每个账号的任务方案。数据和操作来自 app.content.account_model.AccountModel。"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import (Action, BodyLabel, DropDownPushButton, FluentIcon, InfoBar, PrimaryPushButton, RoundMenu,
                            TitleLabel, qconfig)

from app.content.account_model import AccountModel
from module.localization import tr
from module.logger import log
from .accounts.detail import AccountDetail
from .accounts.dialogs import (AddAccountDialog, ClearLoginDialog, CredentialsDialog, DeleteDialog, EnableDialog,
                               RenameDialog)
from .accounts.empty import EmptyAccounts
from .accounts.panel import AccountPanel
from .pages.common import NoticeStrip, is_evernight, refresh_on_restore, secondary, shared, style_primary

PANEL_WIDTH = 356


class AccountsInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("accountsInterface")
        self.window_ = parent
        self.model = shared(parent, "accountModel", lambda: AccountModel(parent))
        self._selected = None
        self.titleLabel = TitleLabel(self)
        self.subtitleLabel = secondary(BodyLabel(self))
        self.addButton = DropDownPushButton(FluentIcon.ADD, "", self)
        self.addMenu = RoundMenu(parent=self)
        self.addActions = [Action(FluentIcon.GAME, "", triggered=lambda: self.addAccount()),
                           Action(FluentIcon.FOLDER, "", triggered=lambda: self.addFromClient()),
                           Action(FluentIcon.DELETE, "", triggered=lambda: self.clearGameLogin())]
        self.addMenu.addAction(self.addActions[0])
        self.addMenu.addAction(self.addActions[1])
        self.addMenu.addSeparator()
        self.addMenu.addAction(self.addActions[2])
        self.addButton.setMenu(self.addMenu)
        self.runAllButton = PrimaryPushButton(FluentIcon.PLAY, "", self)
        self.runAllButton.clicked.connect(self.runAll)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 12, 0)
        head.setSpacing(12)
        head.addWidget(self.titleLabel)
        head.addWidget(self.subtitleLabel, 1, Qt.AlignmentFlag.AlignBottom)
        head.addWidget(self.addButton)
        head.addWidget(self.runAllButton)
        self.empty = EmptyAccounts(self)
        self.empty.addClicked.connect(self.addAccount)
        self.panel = AccountPanel(self)
        self.panel.setFixedWidth(PANEL_WIDTH)
        self.panel.toggled.connect(self.setEnabledState)
        self.panel.list.setStatusSource(self._rowStatus)
        self.panel.list.accountSelected.connect(self.showAccount)
        self.panel.list.orderChanged.connect(lambda order: self._run(tr("调整顺序"), self.model.reorder, order))
        self.detail = AccountDetail(self)
        self._connectDetail()
        self.body = QWidget(self)
        columns = QHBoxLayout(self.body)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(16)
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 24)
        left.addWidget(self.panel)
        columns.addLayout(left)
        columns.addWidget(self.detail, 1)
        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.body)
        self.stack.addWidget(self.empty)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 12, 0)
        layout.setSpacing(14)
        layout.addLayout(head)
        self.notice = NoticeStrip(self, kind="warning")
        self.notice.actionClicked.connect(lambda: self.model.open_folder(None))
        self.notice.hide()
        noticeRow = QHBoxLayout()
        noticeRow.setContentsMargins(0, 0, 12, 0)
        noticeRow.addWidget(self.notice)
        layout.addLayout(noticeRow)
        layout.addWidget(self.stack, 1)
        self.model.changed.connect(self._modelChanged)
        self.model.operationFinished.connect(self._operationFinished)
        qconfig.themeChanged.connect(self._restyle)
        qconfig.themeColorChanged.connect(self._restyle)
        self._setTexts()
        self._restyle()
        refresh_on_restore(self, parent, self.refresh)

    # ---------- 界面 ----------

    def _connectDetail(self):
        header, login, plan = self.detail.header, self.detail.login, self.detail.plan
        header.renameClicked.connect(self.rename)
        header.switchClicked.connect(self.switchAccount)
        header.runClicked.connect(self.runAccount)
        header.rotateToggled.connect(lambda on: self._run(tr("参与轮流"), self.model.set_rotate, self._selected, on))
        header.folderClicked.connect(lambda: self.model.open_folder(self._selected))
        header.deleteClicked.connect(self.deleteAccount)
        login.saveClicked.connect(self.saveLogin)
        login.credentialsClicked.connect(self.editCredentials)
        login.clearCredentialsClicked.connect(
            lambda: self._run(tr("账号密码"), self.model.clear_credentials, self._selected))
        login.autoLoginToggled.connect(lambda on: self._run(tr("自动填写"), self.model.set_auto_login, self._selected, on))
        login.pathClicked.connect(self.choosePath)
        login.pathCleared.connect(lambda: self._run(tr("游戏客户端"), self.model.set_game_path, self._selected, ""))
        login.hourChanged.connect(lambda hour: self._run(tr("刷新时间"), self.model.set_refresh_hour, self._selected, hour))
        plan.planChanged.connect(lambda mode: self._run(tr("任务方案"), self.model.set_plan, self._selected, mode))
        plan.restoreClicked.connect(lambda diff: self._run(tr("恢复共享"), self.model.restore_shared, self._selected, diff))
        plan.editClicked.connect(self.editPlan)
        self.detail.week.strip.dayClicked.connect(lambda run_id: self.window_.navigate(f"run:{run_id}"))

    def _setTexts(self):
        self.titleLabel.setText(tr("账号"))
        self.subtitleLabel.setText(tr("每个账号有自己的登录和任务方案，可以按顺序轮流运行"))
        self.addButton.setText(tr("添加账号"))
        self.runAllButton.setText(tr("轮流运行全部"))
        for action, text in zip(self.addActions, (tr("从当前游戏登录导入"), tr("从另一个游戏客户端导入…"),
                                                  tr("清除游戏登录信息…"))):
            action.setText(text)

    def retranslateUi(self):
        self._setTexts()
        self.empty.retranslateUi()
        self.panel.retranslateUi()
        self.refresh()

    def _restyle(self, *_):
        style_primary(self.runAllButton, is_evernight())
        if self.isVisible():
            self.refresh()
        self.update()

    def _modelChanged(self):
        if self.isVisible() and not self.window().isMinimized():
            self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self.model.refresh()
        self.refresh()

    def _rowStatus(self, info):
        if self.model.active():
            return info.status.kind, info.status.text
        if info.logged_in:
            return "login", tr("当前登录")
        return ("no_login", tr("没有登录快照")) if info.login == "missing" else ("idle", "")

    def refresh(self):
        infos = self.model.accounts()
        active, reason = self.model.active(), self.model.unsupported_reason()
        problems = self.model.problems()
        self.notice.setKind("warning", is_evernight())
        self.notice.setText("\n".join(problems))
        self.notice.setAction(tr("打开账号文件夹"))
        self.notice.setVisible(bool(problems))
        self.panel.setState(enabled=self.model.enabled(), reason=reason)
        self.empty.textLabel.setText(reason or self.empty.introduction())
        for step in self.empty.steps:
            step.setVisible(not reason)
        readonly = self.model.readonly()
        self.addButton.setDisabled(readonly)
        self.empty.addButton.setDisabled(readonly)
        for group in (self.detail.header, self.detail.login, self.detail.plan):
            group.setDisabled(readonly)
        if readonly or self.model.busy():
            self.panel.switch.setEnabled(False)
        self.runAllButton.setVisible(active)
        self.runAllButton.setEnabled(not self.model.busy() and any(info.rotate for info in infos))
        self.stack.setCurrentWidget(self.body if infos else self.empty)
        if not infos:
            self._selected = None
            return
        uids = [info.uid for info in infos]
        if self._selected not in uids:
            self._selected = self.model.current() if self.model.current() in uids else uids[0]
        self.panel.list.setAccounts(infos, self._selected)
        self.showAccount(self._selected)

    def selected(self):
        return self._selected

    def showAccount(self, uid):
        info = next((item for item in self.model.accounts() if item.uid == uid), None)
        if info is None:
            return False
        self._selected = uid
        self.panel.list.select(uid)
        active = self.model.active()
        self.detail.setAccount(info, active=active, current=uid == self.model.current(), busy=self.model.busy(),
                               diffs=self.model.diffs(uid) if active else (), default_hour=self.model.default_hour())
        return True

    def info(self):
        return next((item for item in self.model.accounts() if item.uid == self._selected), None)

    # ---------- 操作 ----------

    def _run(self, title, function, *args, success=""):
        try:
            outcome = function(*args)
        except Exception as exc:
            log.error(f"账号操作失败：{getattr(function, '__name__', title)} {type(exc).__name__}: {exc}")
            InfoBar.error(title, tr("操作没有完成，详情见日志"), duration=5000, parent=self.window_)
            QTimer.singleShot(0, self, self.refresh)
            return False
        if outcome is not None and not outcome.ok:
            if outcome.text:
                InfoBar.error(title, outcome.text, duration=6000, parent=self.window_)
            QTimer.singleShot(0, self, self.refresh)
            return False
        if self.model.working():
            # 在后台读写登录，完成后由 operationFinished 给出结果。
            InfoBar.info(title, outcome.text, duration=2000, parent=self.window_)
            return True
        text = (outcome.text if outcome is not None else "") or success
        if text:
            InfoBar.success(title, text, duration=3000, parent=self.window_)
        return True

    def _operationFinished(self, result):
        if result.text:
            show = InfoBar.success if result.ok else InfoBar.error
            show(tr("账号"), result.text, duration=4000, parent=self.window_)

    def setEnabledState(self, on):
        if on and not self.model.accounts():
            self.refresh()
            InfoBar.warning(tr("还没有保存账号"), tr("先添加至少一个账号，再打开多账号轮流"), duration=4000, parent=self.window_)
            return
        if on and not EnableDialog(self.model.inherit_name(), self.window_).exec():
            self.refresh()
            return
        self._run(tr("多账号轮流运行"), self.model.set_enabled, on)

    def addAccount(self):
        dialog = AddAccountDialog(lambda: self.model.login(), self.window_)
        if dialog.exec() and dialog.login is not None and \
                self._run(tr("添加账号"), self.model.add_current, dialog.name(), "", dialog.login.uid, success=tr("登录已保存")):
            self.showAccount(dialog.login.uid)

    def addFromClient(self):
        path, _ = QFileDialog.getOpenFileName(self.window_, tr("选择游戏客户端"), "", "StarRail.exe (StarRail.exe)")
        if not path:
            return
        dialog = AddAccountDialog(lambda: self.model.login(path), self.window_)
        if dialog.exec() and dialog.login is not None and \
                self._run(tr("添加账号"), self.model.add_current, dialog.name(), path, dialog.login.uid, success=tr("登录已保存")):
            self.showAccount(dialog.login.uid)

    def clearGameLogin(self):
        if ClearLoginDialog(self.window_).exec():
            self._run(tr("清除游戏登录信息"), self.model.clear_game_login, success=tr("游戏登录信息和设置已清除"))

    def rename(self):
        info = self.info()
        if info is None:
            return
        dialog = RenameDialog(info.name, self.window_)
        if dialog.exec() and dialog.name():
            self._run(tr("修改备注名"), self.model.rename, info.uid, dialog.name())

    def switchAccount(self):
        info = self.info()
        if info is not None:
            self._run(tr("切换账号"), self.model.switch_to, info.uid)

    def runAccount(self):
        info = self.info()
        if info is not None:
            self._run(tr("只运行此账号"), self.model.run, info.uid)

    def runAll(self):
        self._run(tr("轮流运行全部"), self.model.run_all)

    def saveLogin(self):
        info = self.info()
        if info is not None:
            self._run(tr("游戏登录快照"), self.model.save_login, info.uid, success=tr("登录已保存"))

    def editCredentials(self):
        info = self.info()
        if info is None:
            return
        dialog = CredentialsDialog(info.name, self.window_)
        if dialog.exec():
            account, password = dialog.values()
            self._run(tr("账号密码"), self.model.save_credentials, info.uid, account, password, success=tr("已加密保存"))

    def choosePath(self):
        info = self.info()
        if info is None:
            return
        path, _ = QFileDialog.getOpenFileName(self.window_, tr("选择游戏客户端"), info.game_path, "StarRail.exe (StarRail.exe)")
        if path:
            self._run(tr("游戏客户端"), self.model.set_game_path, info.uid, path)

    def deleteAccount(self):
        info = self.info()
        if info is not None and DeleteDialog(info.name, self.window_).exec():
            self._run(tr("删除账号"), self.model.delete, info.uid, success=tr("账号已删除"))

    def editPlan(self):
        info = self.info()
        if info is not None and self._run(tr("切换账号"), self.model.set_current, info.uid):
            self.window_.switchTo(self.window_.taskInterface)
