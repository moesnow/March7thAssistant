"""账号页左侧：多账号总开关、账号列表和说明。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout
from qfluentwidgets import BodyLabel, CaptionLabel, FluentIcon, IconWidget, SimpleCardWidget, StrongBodyLabel

from app.pages.common import Divider, NoticeStrip, bare_switch, is_evernight, secondary
from module.localization import tr
from .account_list import AccountList


class AccountPanel(SimpleCardWidget):
    toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBorderRadius(8)
        self.iconWidget = IconWidget(FluentIcon.PEOPLE, self)
        self.iconWidget.setFixedSize(18, 18)
        self.titleLabel = StrongBodyLabel(self)
        self.descriptionLabel = secondary(CaptionLabel(self))
        self.descriptionLabel.setWordWrap(True)
        self.switch = bare_switch(self)
        self.switch.checkedChanged.connect(self.toggled)
        head = QHBoxLayout()
        head.setContentsMargins(16, 14, 16, 12)
        head.setSpacing(12)
        column = QVBoxLayout()
        column.setSpacing(2)
        column.addWidget(self.titleLabel)
        column.addWidget(self.descriptionLabel)
        head.addWidget(self.iconWidget, 0, Qt.AlignmentFlag.AlignTop)
        head.addLayout(column, 1)
        head.addWidget(self.switch, 0, Qt.AlignmentFlag.AlignVCenter)
        self.notice = NoticeStrip(self, kind="info")
        self.notice.hide()
        self.list = AccountList(self)
        self.footLabel = secondary(CaptionLabel(self))
        self.footLabel.setWordWrap(True)
        self.footLabel.setContentsMargins(16, 10, 16, 12)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(head)
        noticeRow = QHBoxLayout()
        noticeRow.setContentsMargins(12, 0, 12, 12)
        noticeRow.addWidget(self.notice)
        self.noticeRow = noticeRow
        layout.addLayout(noticeRow)
        layout.addWidget(Divider(self))
        layout.addWidget(self.list, 1)
        layout.addWidget(Divider(self))
        layout.addWidget(self.footLabel)
        self.retranslateUi()

    def retranslateUi(self):
        self.titleLabel.setText(tr("多账号轮流运行"))
        self.descriptionLabel.setText(tr("每个账号使用自己的任务方案和完成状态，定时运行按下面的顺序依次切换"))
        self.switch.setAccessibleName(tr("多账号轮流运行"))

    def setState(self, *, enabled, reason):
        """enabled：总开关；reason：不能用多账号的原因，空串表示可以用。"""
        self.switch.blockSignals(True)
        self.switch.setChecked(enabled)
        self.switch.blockSignals(False)
        self.switch.setEnabled(not reason or enabled)
        self.notice.setKind("info", is_evernight())
        self.notice.setText(reason)
        self.notice.setVisible(bool(reason))
        self.noticeRow.setContentsMargins(12, 0, 12, 12 if reason else 0)
        active = enabled and not reason
        self.list.setMovable(active)
        self.footLabel.setText(
            tr("拖动调整顺序。一个账号失败后会记录原因并继续下一个账号，全部结束后合并发送一条通知。多账号只支持本地客户端。")
            if active else tr("这里保存的是本地客户端的登录快照，换号时不用重新登录。打开上面的开关后，可以按顺序轮流运行。"))
