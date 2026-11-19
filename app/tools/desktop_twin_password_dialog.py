"""在分身窗口管理当前 Windows 用户的分身专用凭据。"""

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
        self.password.setPlaceholderText(tr("请输入 Windows 账户密码。"))
        form = QFormLayout()
        form.addRow(tr("Windows 账户"), self.account)
        form.addRow(tr("账户密码"), self.password)
        hint = BodyLabel(tr("密码保存在本机的 Windows 凭据管理器中。以你的 Windows 用户身份运行的其他程序也可能读取它。"), self)
        hint.setWordWrap(True)
        self.error = BodyLabel(self)
        self.error.setWordWrap(True)
        self.error.hide()
        self.forget = PushButton(tr("忘记密码"), self)
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
        try:
            credentials.save_credential(self.account.text(), self.password.text())
        except (ValueError, RuntimeError) as exc:
            self.error.setText(str(exc))
            self.error.show()
            return
        self.accept()

    def _forget(self):
        if QMessageBox.question(self, tr("忘记密码"), tr("删除本机保存的分身密码？"),
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
