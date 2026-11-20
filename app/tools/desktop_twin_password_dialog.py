"""在分身窗口管理当前 Windows 用户的分身专用凭据。"""

from PySide6.QtCore import QPoint, QPropertyAnimation
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QVBoxLayout
from qfluentwidgets import BodyLabel, CaptionLabel, LineEdit, MessageBoxBase, PasswordLineEdit, SubtitleLabel

from app.tools import desktop_twin_credentials as credentials
from module.localization import tr


class TwinPasswordDialog(MessageBoxBase):
    def __init__(self, saved_account, parent):
        super().__init__(parent)
        title = tr("自动登录")
        self.setWindowTitle(title)
        self.viewLayout.addWidget(SubtitleLabel(title, self.widget))
        self.widget.setMinimumWidth(400)

        self.account = LineEdit(self.widget)
        has_saved_password = saved_account is not None
        self.account.setReadOnly(has_saved_password)
        self.account.setText(saved_account if has_saved_password else credentials.current_account())
        form = QVBoxLayout()
        form.setSpacing(4)
        account_label = BodyLabel(tr("Windows 账户"), self.widget)
        account_label.setBuddy(self.account)
        form.addWidget(account_label)
        form.addWidget(self.account)
        self.password = None
        if not has_saved_password:
            self.account.setPlaceholderText(tr("MicrosoftAccount\\邮箱 或 计算机名\\用户名"))
            self.account.setToolTip(self.account.placeholderText())
            self.password = PasswordLineEdit(self.widget)
            self.password.setPlaceholderText(tr("请输入 Windows 账户密码"))
            password_label = BodyLabel(tr("账户密码"), self.widget)
            password_label.setBuddy(self.password)
            form.addSpacing(8)
            form.addWidget(password_label)
            form.addWidget(self.password)
            self._password_shake = QPropertyAnimation(self.password, b"pos", self)
            self._password_shake.setDuration(260)
            self._password_shake.finished.connect(form.invalidate)
        self.viewLayout.addLayout(form)
        self._password_form = form

        hint = CaptionLabel(tr("若保存的密码有误，启动分身时仍会要求输入"), self.widget)
        hint.setTextColor(QColor(96, 96, 96), QColor(206, 206, 206))
        hint.setWordWrap(True)
        self.viewLayout.addWidget(hint)
        self.error = BodyLabel(self.widget)
        self.error.setWordWrap(True)
        self.error.hide()
        self.viewLayout.addWidget(self.error)

        self.yesButton.setText(tr("删除密码") if has_saved_password else tr("保存密码"))
        self.yesButton.setDefault(not has_saved_password)
        self.cancelButton.setText(tr("取消"))
        self.cancelButton.setDefault(has_saved_password)
        if has_saved_password:
            self.cancelButton.setFocus()
        else:
            (self.password if self.account.text() else self.account).setFocus()

    def validate(self) -> bool:
        if self.password is not None and not self.password.text():
            self.error.hide()
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
            return False
        try:
            if self.password is None:
                credentials.forget_credential()
            else:
                credentials.save_credential(self.account.text(), self.password.text())
        except (ValueError, RuntimeError) as exc:
            self.error.setText(str(exc))
            self.error.show()
            return False
        return True

    def done(self, result):
        if self.password is not None:
            self.password.clear()
        self.widget.setEnabled(False)
        super().done(result)
