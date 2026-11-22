"""在分身窗口管理当前 Windows 用户的分身专用凭据。"""

from PySide6.QtCore import QPoint, QPropertyAnimation, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QVBoxLayout
from qfluentwidgets import (BodyLabel, CaptionLabel, InfoBarIcon, LineEdit, MessageBoxBase,
                            PasswordLineEdit, SubtitleLabel, setCustomStyleSheet)

from app.components.notice_bar import NoticeBar
from app.tools import desktop_twin_credentials as credentials
from module.localization import tr


class TwinPasswordDialog(MessageBoxBase):
    def __init__(self, saved_account, parent):
        super().__init__(parent)
        title = tr("自动登录")
        self.setWindowTitle(title)
        self.viewLayout.addWidget(SubtitleLabel(title, self.widget))
        self.widget.setMinimumWidth(400)

        self.viewLayout.setSpacing(8)
        form = QVBoxLayout()
        form.setSpacing(4)
        account_label = BodyLabel(tr("Windows 账户"), self.widget)
        form.addWidget(account_label)
        self.account = LineEdit(self.widget)
        setCustomStyleSheet(
            self.account,
            "LineEdit:read-only { background-color: #eeeeee; color: #606060; }",
            "LineEdit:read-only { background-color: #323232; color: #bdbdbd; }",
        )
        account_label.setBuddy(self.account)
        self.account.setAccessibleName(account_label.text())
        self.account.setPlaceholderText(tr("MicrosoftAccount\\邮箱 或 计算机名\\用户名"))
        self.account.setToolTip(self.account.placeholderText())
        form.addWidget(self.account)
        self.password = PasswordLineEdit(self.widget)
        self.password.setPlaceholderText(tr("请输入 Windows 账户密码"))
        self.password_label = BodyLabel(tr("账户密码"), self.widget)
        self.password_label.setContentsMargins(0, 4, 0, 0)
        self.password_label.setBuddy(self.password)
        form.addWidget(self.password_label)
        form.addWidget(self.password)
        self._password_shake = QPropertyAnimation(self.password, b"pos", self)
        self._password_shake.setDuration(260)
        self._password_shake.finished.connect(form.invalidate)
        self.viewLayout.addLayout(form)
        self._password_form = form

        self.hint = CaptionLabel(tr("若保存的密码有误，启动分身时仍会要求输入"), self.widget)
        self.hint.setTextColor(QColor(96, 96, 96), QColor(206, 206, 206))
        self.hint.setWordWrap(True)
        self.feedback = NoticeBar(parent=self.widget)
        self.viewLayout.addWidget(self.feedback)
        self.viewLayout.addWidget(self.hint)

        self.cancelButton.setText(tr("关闭"))
        self._set_mode(saved_account)

    def _set_mode(self, saved_account, fallback_account=""):
        self._saved_account = saved_account
        saved = saved_account is not None
        name = saved_account if saved else fallback_account or credentials.current_account()
        self.account.setText(name)
        self.account.setReadOnly(saved)
        # setText 同时清空撤销历史，删除密码后无法从输入框恢复旧值。
        self.password.setText("")
        self.password.setPasswordVisible(False)
        self.password.setVisible(not saved)
        self.password_label.setVisible(not saved)
        self.yesButton.setText(tr("删除密码") if saved else tr("保存密码"))
        self.yesButton.setDefault(not saved)
        self.cancelButton.setDefault(saved)
        if saved:
            self._show_feedback(InfoBarIcon.SUCCESS, tr("已保存分身密码"))
            self.cancelButton.setFocus()
        else:
            self.feedback.hide()
            self.hint.show()
            (self.password if name else self.account).setFocus()

    def _show_feedback(self, icon, message):
        self.hint.setVisible(icon == InfoBarIcon.SUCCESS)
        self.feedback.setIcon(icon)
        self.feedback.setContent(message)
        self.feedback.show()

    def accept(self):
        """主按钮在当前窗口应用操作，关闭由次要按钮处理。"""
        if self._saved_account is None and not self.password.text():
            self.feedback.hide()
            self.hint.show()
            self.password.setFocus()
            self._password_shake.stop()
            # 让表单先恢复输入框的位置，连续点击时从同一位置开始。
            self._password_form.invalidate()
            self.widget.layout().activate()
            origin = self.password.pos()
            self._password_shake.setKeyValues([
                (t, origin + QPoint(dx, 0))
                for t, dx in ((0, 0), (0.15, -6), (0.35, 6), (0.55, -4), (0.75, 3), (1, 0))
            ])
            self._password_shake.start()
            return
        name = self.account.text().strip()
        try:
            saved_account, applied = credentials.change_credential(self._saved_account, name, self.password.text())
        except (ValueError, RuntimeError) as exc:
            self._show_feedback(InfoBarIcon.ERROR, str(exc))
            return
        self._set_mode(saved_account, name)
        if not applied:
            self._show_feedback(InfoBarIcon.WARNING, tr("分身凭据已在其他位置更改，请核对后再操作。"))
        if saved_account is not None:
            # 刚保存或刷新出了其他账户，双击的第二下都不应删除这条凭据。
            self.yesButton.setEnabled(False)
            QTimer.singleShot(QApplication.doubleClickInterval(), self.yesButton, lambda: self.yesButton.setEnabled(True))

    def done(self, result):
        self.password.setText("")
        self.widget.setEnabled(False)
        super().done(result)
