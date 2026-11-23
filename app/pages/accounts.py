"""账号：管理本地客户端的登录账号。内容沿用原设置页「账号」标签。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, ScrollArea, TitleLabel

from app.sub_interfaces.accounts_interface import accounts_interface
from module.localization import tr
from .common import secondary


class AccountsInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("accountsInterface")
        self.setWidgetResizable(True)
        self.enableTransparentBackground()
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._build()

    def _build(self):
        view = QWidget()
        view.setObjectName("view")
        view.setStyleSheet("#view{background: transparent}")
        layout = QVBoxLayout(view)
        layout.setContentsMargins(36, 14, 36, 28)
        layout.setSpacing(10)
        try:
            title = TitleLabel(tr("账号"), view)
            description = secondary(BodyLabel(
                tr("保存本地客户端的登录状态，换号时直接导入，不用每次重新登录。只支持本地客户端。"), view))
            description.setWordWrap(True)
            content = accounts_interface(tr, view)
            content.titleLabel.hide()
            layout.addWidget(title)
            layout.addWidget(description)
            layout.addSpacing(6)
            layout.addWidget(content)
            layout.addStretch(1)
        except Exception:
            view.deleteLater()
            raise
        self.setWidget(view)
        self.view, self.titleLabel, self.descriptionLabel, self.content = view, title, description, content

    def retranslateUi(self):
        position = self.verticalScrollBar().value()
        self._build()
        self.verticalScrollBar().setValue(position)
