"""任务页右上角：正在编辑哪个账号的方案。没开多账号时不显示。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import FluentIcon, PushButton

from app.overview.widgets import ElidedLabel
from app.pages.common import secondary
from module.localization import tr
from .avatar import Avatar


class EditingAccount(QWidget):
    def __init__(self, model, window, parent=None):
        super().__init__(parent)
        self.model, self.window_ = model, window
        self.avatar = Avatar(24, self)
        self.label = secondary(ElidedLabel(self, size=13))
        self.button = PushButton(FluentIcon.PEOPLE, "", self)
        self.button.clicked.connect(lambda: self.window_.openAccountSwitcher(self.button))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.avatar)
        layout.addWidget(self.label)
        layout.addSpacing(4)
        layout.addWidget(self.button)
        self.setMaximumWidth(420)
        model.changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        info = self.model.editing()
        self.setVisible(info is not None)
        if info is None:
            return
        self.avatar.setAccount(info.color, info.name)
        text = tr("正在编辑「{name}」的独立方案") if info.plan == "independent" else tr("「{name}」使用共享方案")
        self.label.setFullText(text.format(name=info.name))
        self.button.setText(tr("切换账号"))
