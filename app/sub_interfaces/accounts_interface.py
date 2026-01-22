
from typing import Union
from qfluentwidgets import SettingCard, SettingCardGroup, ListWidget, FluentIconBase, CardWidget, FluentStyleSheet
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton, QListWidgetItem, QVBoxLayout, QMessageBox, QInputDialog, QLineEdit, QLabel
from PySide6.QtWidgets import QGridLayout, QFrame
from qfluentwidgets import FluentIcon as FIF
from module.config import cfg
from app.tools.account_manager import accounts, reload_all_account_from_files, dump_current_account, delete_account, \
    save_account_name, import_account, save_acc_and_pwd, clear_reg
from module.logger import log
from module.localization import tr


class AccountsCard(QFrame):

    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, content=None, texts=None, parent=None):
        super().__init__(parent=parent)
        FluentStyleSheet.SETTING_CARD.apply(self)
        self.setFixedHeight(400)
        #
        self.widget = ListWidget()
        self.wLayout = QGridLayout()
        self.wLayout.addWidget(self.widget)
        # self.widget.setStyleSheet("QListWidget{border: 1px solid #d9d9d9;} QListWidget::item{height: 30px;} QListWidget::item:selected{background-color: #f0f0f0;} QListWidget::item:hover{background-color: #f0f0f0;}")
        #
        self.buttons = QVBoxLayout()
        self.buttons.setContentsMargins(10, 3, 10, 3)
        self.tipsText = QLabel(tr("重要：请完全进入游戏（看到角色）后再进行导出，否则会读取前一个账号的UID，导致文件和账号不对应"))
        self.tipsText.setWordWrap(True)
        self.tipsText.setStyleSheet('color: #f94e9b')
        self.tipsText2 = QLabel(tr("该功能不支持云·星穹铁道"))
        self.tipsText2.setWordWrap(True)
        self.tipsText2.setStyleSheet('color: #f94e9b')
        self.buttons.addWidget(self.tipsText)
        self.buttons.addWidget(self.tipsText2)
        self.tipsText.setFixedHeight(50)
        self.tipsText2.setFixedHeight(50)
        self.addAccountButton = QPushButton(tr("导出当前游戏账户"), self)
        self.importAccountButton = QPushButton(tr("导入选中的账户"), self)
        self.deleteAccountButton = QPushButton(tr("删除账户"), self)
        self.renameAccountButton = QPushButton(tr("账户更名"), self)
        self.autologinAccountButton = QPushButton(tr("自动登录"), self)
        self.refreshAccountButton = QPushButton(tr("刷新"), self)
        self.clearRegButton = QPushButton(tr("清除注册表"), self)
        self.buttons.addWidget(self.addAccountButton)
        self.buttons.addWidget(self.importAccountButton)
        self.buttons.addWidget(self.deleteAccountButton)
        self.buttons.addWidget(self.renameAccountButton)
        self.buttons.addWidget(self.autologinAccountButton)
        self.buttons.addWidget(self.refreshAccountButton)
        self.buttons.addWidget(self.clearRegButton)
        _self = self

        def load_accounts():
            _self.widget.clear()
            for account in accounts:
                item = QListWidgetItem(account.account_name)
                item.setData(Qt.ItemDataRole.UserRole, account.account_id)
                _self.widget.addItem(item)
            _self.widget.clearSelection()
        try:
            load_accounts()
        except Exception as e:
            log.error(f"load_accounts: {e}")

        def refreshAccountButtonAction(self):
            reload_all_account_from_files()
            load_accounts()
            QMessageBox.information(None, tr("刷新"), tr("账户列表刷新成功"))

        def addAccountButtonAction(self):
            dump_current_account()
            load_accounts()
            QMessageBox.information(None, tr("导出"), tr("账户导出成功"))

        def deleteAccountButtonAction(self):
            items = _self.widget.selectedItems()
            if len(items) == 0:
                QMessageBox.warning(None, tr("删除账户"), tr("请选择要删除的账户"))
                return
            if QMessageBox.question(None, tr("删除账户"), tr("确定要删除选中的账户吗？"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.No:
                return
            for item in items:
                account_id = item.data(Qt.ItemDataRole.UserRole)
                delete_account(account_id)
            load_accounts()

        def renameAccountButtonAction(self):
            items = _self.widget.selectedItems()
            if len(items) == 0:
                QMessageBox.warning(None, tr("账户更名"), tr("请选择要更名的账户"))
                return
            if len(items) > 1:
                QMessageBox.warning(None, tr("账户更名"), tr("只能选择一个账户"))
                return
            for item in items:
                account_id = item.data(Qt.ItemDataRole.UserRole)
                account_name, ok = QInputDialog.getText(None, tr("账户更名"), tr("请输入新的账户名"))
                if ok:
                    account_name = account_name.strip()
                    if len(account_name) == 0:
                        QMessageBox.warning(None, tr("账户更名"), tr("账户名不能为空"))
                        return
                    save_account_name(account_id, account_name)
                    load_accounts()

        def autologinAccountButtonAction(self):
            items = _self.widget.selectedItems()
            if len(items) == 0:
                QMessageBox.warning(None, tr("自动登录"), tr("请选择要使用的账户"))
                return
            if len(items) > 1:
                QMessageBox.warning(None, tr("自动登录"), tr("只能选择一个账户"))
                return
            for item in items:
                account_id = item.data(Qt.ItemDataRole.UserRole)

                disclaimer_result = QMessageBox.question(
                    None,
                    tr("自动登录"),
                    tr("当登录过期时尝试自动重新填写账号密码\n *此功能存在一定风险，请谨慎使用*"),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if disclaimer_result != QMessageBox.StandardButton.Yes:
                    return

                account_name, ok = QInputDialog.getText(None, tr("自动登录"), tr("请输入用户名"))
                if not ok:
                    return
                if not account_name.strip():
                    QMessageBox.warning(None, tr("自动登录"), tr("用户名不能为空"))
                    return

                account_pass, ok2 = QInputDialog.getText(None, tr("自动登录"), tr("请输入密码"), QLineEdit.EchoMode.Password)
                if not ok2:
                    return
                if not account_pass.strip():
                    QMessageBox.warning(None, tr("自动登录"), tr("密码不能为空"))
                    return

                save_acc_and_pwd(account_id, account_name, account_pass)

        def importAccountButtonAction(self):
            items = _self.widget.selectedItems()
            if len(items) == 0:
                QMessageBox.warning(None, tr("导入"), tr("请选择要使用的账户"))
                return
            if len(items) > 1:
                QMessageBox.warning(None, tr("导入"), tr("只能选择一个账户"))
                return
            for item in items:
                account_id = item.data(Qt.ItemDataRole.UserRole)
                import_account(account_id)
                QMessageBox.information(None, tr("导入"), tr("账户导入成功"))

        def clearRegButtonAction(self):
            if QMessageBox.question(None, tr("清除注册表"), tr("确定要清除注册表中的账户信息吗？"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.No:
                return
            clear_reg()
            QMessageBox.information(None, tr("清除注册表"), tr("注册表中的账户信息已清除"))

        self.addAccountButton.clicked.connect(addAccountButtonAction)
        self.importAccountButton.clicked.connect(importAccountButtonAction)
        self.refreshAccountButton.clicked.connect(refreshAccountButtonAction)
        self.renameAccountButton.clicked.connect(renameAccountButtonAction)
        self.autologinAccountButton.clicked.connect(autologinAccountButtonAction)
        self.deleteAccountButton.clicked.connect(deleteAccountButtonAction)
        self.clearRegButton.clicked.connect(clearRegButtonAction)
        #
        self.mLayout = QGridLayout()
        self.mLayout.addLayout(self.wLayout, 0, 0, 1, 1)
        self.mLayout.addLayout(self.buttons, 0, 1, 1, 1)
        self.mLayout.setColumnStretch(0, 1)  # 第一列的拉伸因子为1，即均分空间
        self.mLayout.setColumnStretch(1, 1)  # 第二列的拉伸因子为1，即均分空间
        #
        self.setLayout(self.mLayout)


def accounts_interface(tr, scrollWidget) -> SettingCardGroup:
    accountsInterface = SettingCardGroup(tr("账户设置"), scrollWidget)
    accountsInterface.addSettingCard(AccountsCard(
        FIF.ALBUM, title=tr(""),
    ))
    return accountsInterface
