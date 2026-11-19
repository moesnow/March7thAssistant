"""在分身窗口管理当前 Windows 用户的分身专用凭据。"""

from PySide6.QtCore import QPoint, QPropertyAnimation
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QMessageBox, QVBoxLayout
from qfluentwidgets import (BodyLabel, CaptionLabel, LineEdit, MessageBoxBase, PasswordLineEdit,
                            PushButton, SubtitleLabel, setCustomStyleSheet)

from app.tools import desktop_twin_credentials as credentials
from module.localization import tr


class TwinPasswordDialog(MessageBoxBase):
    FORGOTTEN = 2

    def __init__(self, saved_account, parent):
        super().__init__(parent)
        title = tr("自动登录")
        self.setWindowTitle(title)
        self.viewLayout.addWidget(SubtitleLabel(title, self.widget))
        self.widget.setMinimumWidth(400)

        self.account = LineEdit(self.widget)
        self.account.setText(saved_account or credentials.current_account())
        self.account.setPlaceholderText(tr("MicrosoftAccount\\邮箱 或 计算机名\\用户名"))
        self.account.setToolTip(self.account.placeholderText())
        self.password = PasswordLineEdit(self.widget)
        self.password.setPlaceholderText(tr("请输入 Windows 账户密码"))
        self._password_shake = QPropertyAnimation(self.password, b"pos", self)
        self._password_shake.setDuration(260)
        form = QVBoxLayout()
        form.setSpacing(4)
        for text, field in ((tr("Windows 账户"), self.account), (tr("账户密码"), self.password)):
            label = BodyLabel(text, self.widget)
            label.setBuddy(field)
            form.addWidget(label)
            form.addWidget(field)
            if field is self.account:
                form.addSpacing(8)
        self.viewLayout.addLayout(form)
        self._password_form = form
        self._password_shake.finished.connect(form.invalidate)

        hint = CaptionLabel(tr("若保存的密码有误，启动时仍会要求输入"), self.widget)
        hint.setTextColor(QColor(96, 96, 96), QColor(206, 206, 206))
        hint.setWordWrap(True)
        self.viewLayout.addWidget(hint)
        self.error = BodyLabel(self.widget)
        self.error.setWordWrap(True)
        self.error.hide()
        self.viewLayout.addWidget(self.error)

        self.forget = PushButton(tr("删除已保存的密码"), self.buttonGroup)
        outline = "PushButton:enabled { border: 1px solid --ThemeColorPrimary; }"
        setCustomStyleSheet(self.forget, outline, outline)
        self.forget.setVisible(saved_account is not None)
        self.forget.clicked.connect(self._forget)
        self.buttonLayout.insertWidget(0, self.forget)
        self.forget.setAutoDefault(False)
        self.yesButton.setText(tr("更新密码") if saved_account is not None else tr("保存密码"))
        self.yesButton.setDefault(True)
        self.cancelButton.setText(tr("取消"))
        self.cancelButton.setAutoDefault(False)
        (self.password if self.account.text() else self.account).setFocus()

    def validate(self) -> bool:
        password = self.password.text()
        if not password:
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
            credentials.save_credential(self.account.text(), password)
        except (ValueError, RuntimeError) as exc:
            self.error.setText(str(exc))
            self.error.show()
            return False
        return True

    def _forget(self):
        if QMessageBox.question(self, tr("删除已保存的密码"), tr("删除本机保存的分身密码？"),
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            credentials.forget_credential()
        except RuntimeError as exc:
            self.error.setText(str(exc))
            self.error.show()
            return
        self.done(self.FORGOTTEN)

    def done(self, result):
        self.password.clear()
        self.widget.setEnabled(False)
        super().done(result)
