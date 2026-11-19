"""在分身窗口管理当前 Windows 用户的分身专用凭据。"""

from PySide6.QtCore import QPoint, QPropertyAnimation
from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QMessageBox, QVBoxLayout
from qfluentwidgets import BodyLabel, LineEdit, PasswordLineEdit, PrimaryPushButton, PushButton

from app.tools import desktop_twin_credentials as credentials
from module.localization import tr


class TwinPasswordDialog(QDialog):
    FORGOTTEN = 2

    def __init__(self, saved_account, parent):
        super().__init__(parent)
        self.setWindowTitle(tr("管理分身密码"))
        self.setMinimumWidth(350)
        self.account = LineEdit(self)
        self.account.setText(saved_account or credentials.current_account())
        self.account.setPlaceholderText(tr("MicrosoftAccount\\邮箱 或 计算机名\\用户名"))
        self.account.setToolTip(self.account.placeholderText())
        self.password = PasswordLineEdit(self)
        self.password.setPlaceholderText(tr("请输入 Windows 账户密码"))
        self._password_shake = QPropertyAnimation(self.password, b"pos", self)
        self._password_shake.setDuration(260)
        form = QFormLayout()
        form.addRow(tr("Windows 账户"), self.account)
        form.addRow(tr("账户密码"), self.password)
        self._password_form = form
        self._password_shake.finished.connect(form.invalidate)
        hint = BodyLabel(tr("密码保存在本机的Windows凭据管理器中，March7th小助手不会以任何方式上传你的Windows密码。如果保存的密码错误，启动分身时仍会要求输入密码。"), self)
        hint.setWordWrap(True)
        self.error = BodyLabel(self)
        self.error.setWordWrap(True)
        self.error.hide()
        self.forget = PushButton(tr("删除已保存的密码"), self)
        self.forget.setVisible(saved_account is not None)
        self.forget.clicked.connect(self._forget)
        self.save = PrimaryPushButton(tr("更新密码") if saved_account is not None else tr("保存密码"), self)
        self.save.clicked.connect(self._save)
        self.save.setDefault(True)
        cancel = PushButton(tr("取消"), self)
        cancel.clicked.connect(self.reject)
        self.forget.setAutoDefault(False)
        cancel.setAutoDefault(False)
        actions = QHBoxLayout()
        actions.addWidget(self.forget)
        actions.addStretch()
        actions.addWidget(cancel)
        actions.addWidget(self.save)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(self.error)
        layout.addLayout(actions)
        (self.password if self.account.text() else self.account).setFocus()

    def _save(self):
        password = self.password.text()
        if not password:
            self.error.hide()
            self.password.setFocus()
            self._password_shake.stop()
            # 让表单先恢复输入框的位置，连续点击时从同一位置开始。
            self._password_form.invalidate()
            self.layout().activate()
            origin = self.password.pos()
            self._password_shake.setKeyValues([
                (t, origin + QPoint(dx, 0))
                for t, dx in ((0, 0), (0.15, -6), (0.35, 6), (0.55, -4), (0.75, 3), (1, 0))
            ])
            self._password_shake.start()
            return
        try:
            credentials.save_credential(self.account.text(), password)
        except (ValueError, RuntimeError) as exc:
            self.error.setText(str(exc))
            self.error.show()
            return
        self.accept()

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
        super().done(result)
