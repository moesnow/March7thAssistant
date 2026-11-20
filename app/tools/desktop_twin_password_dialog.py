"""在分身窗口管理当前 Windows 用户的分身专用凭据。"""

from PySide6.QtCore import QPoint, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout
from qfluentwidgets import (BodyLabel, CaptionLabel, FluentIcon, InfoBarIcon, LineEdit, MessageBoxBase,
                            PasswordLineEdit, SubtitleLabel, TransparentPushButton)

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
        self.edit_account = TransparentPushButton(FluentIcon.EDIT, tr("修改账户名"), self.widget)
        self.edit_account.setAutoDefault(False)
        self.edit_account.clicked.connect(self._edit_account)
        header = QHBoxLayout()
        header.addWidget(account_label)
        header.addStretch()
        header.addWidget(self.edit_account)
        form.addLayout(header)
        self.account_display = BodyLabel(self.widget)
        self.account_display.setTextFormat(Qt.TextFormat.PlainText)
        self.account_display.setWordWrap(True)
        self.account_display.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse |
                                                    Qt.TextInteractionFlag.TextSelectableByKeyboard)
        form.addWidget(self.account_display)
        self.account = LineEdit(self.widget)
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
        self.viewLayout.addWidget(self.hint)
        self.feedback = NoticeBar(parent=self.widget)
        self.viewLayout.addWidget(self.feedback)
        self.feedback.hide()

        self.cancelButton.setText(tr("关闭"))
        saved = saved_account is not None
        self._set_mode(saved_account if saved else credentials.current_account(), saved=saved)

    def _set_mode(self, name, *, saved):
        self._has_saved_password = saved
        self.account.setText(name)
        self.account_display.setText(name or "—")
        editing = not saved and not name
        self.account.setVisible(editing)
        self.account_display.setVisible(not editing)
        self.edit_account.setVisible(not saved and not editing)
        self.password.clear()
        self.password.setPasswordVisible(False)
        self.password.setVisible(not saved)
        self.password_label.setVisible(not saved)
        self.yesButton.setText(tr("删除密码") if saved else tr("保存密码"))
        self.yesButton.setDefault(not saved)
        self.cancelButton.setDefault(saved)
        if saved:
            self.cancelButton.setFocus()
        else:
            (self.account if editing else self.password).setFocus()

    def _edit_account(self):
        self.edit_account.hide()
        self.account_display.hide()
        self.account.show()
        self.account.setFocus()
        self.account.selectAll()

    def _show_feedback(self, icon, message):
        self.hint.hide()
        self.feedback.setIcon(icon)
        self.feedback.setContent(message)
        self.feedback.show()

    def accept(self):
        """主按钮在当前窗口应用操作，关闭由次要按钮处理。"""
        if not self._has_saved_password and not self.password.text():
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
            if self._has_saved_password:
                credentials.forget_credential()
                message = tr("已删除保存的分身密码")
            else:
                credentials.save_credential(name, self.password.text())
                message = tr("已保存分身密码")
        except (ValueError, RuntimeError) as exc:
            self._show_feedback(InfoBarIcon.ERROR, str(exc))
            return
        self._set_mode(name or credentials.current_account(), saved=not self._has_saved_password)
        self._show_feedback(InfoBarIcon.SUCCESS, message)
        # 新动作在同一位置，避免双击保存时第二下误删密码。
        self.yesButton.setEnabled(False)
        QTimer.singleShot(QApplication.doubleClickInterval(), self.yesButton, lambda: self.yesButton.setEnabled(True))

    def done(self, result):
        self.password.clear()
        self.widget.setEnabled(False)
        super().done(result)
