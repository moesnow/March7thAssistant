"""账号切换浮层：切换正在查看和编辑的账号、添加账号、进入账号页。"""
from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, Flyout, FlyoutAnimationType, FlyoutViewBase, FluentIcon, ScrollArea

from app.pages import style
from app.pages.common import Divider, secondary
from module.localization import tr
from .account_list import STATUS, account_line
from .avatar import paint_avatar

WIDTH = 332
MAX_ROWS = 7


class _Row(QAbstractButton):
    """一行账号，或一行带图标的操作。"""

    def __init__(self, parent, *, info=None, text="", hint="", icon=None, status=None, checked=False):
        super().__init__(parent)
        self.info, self._hint, self._icon, self._checked = info, hint, icon, checked
        self._status = status or ("idle", "")
        self.setText(info.name if info is not None else text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setFixedHeight(52 if info is not None else 38)
        self.setAccessibleName(" ".join(filter(None, (self.text(), self._status[1] if info is not None else hint))))

    def sizeHint(self):
        return QSize(WIDTH - 12, self.height())

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        rect = QRectF(self.rect())
        if self._checked or self.underMouse() or self.hasFocus():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(style.selected_fill() if self._checked or self.isDown() else style.hover_fill())
            painter.drawRoundedRect(rect, 6, 6)
        center = rect.center().y()
        align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        if self.info is None:
            self._icon.icon(color=style.muted()).paint(painter, 14, int(center) - 8, 16, 16)
            painter.setFont(style.font(14))
            painter.setPen(style.primary())
            text_width = painter.fontMetrics().horizontalAdvance(self.text())
            painter.drawText(QRectF(44, 0, rect.width() - 54, rect.height()), align, self.text())
            painter.setFont(style.font(12))
            painter.setPen(style.faint())
            space = rect.width() - 54 - text_width - 16
            painter.drawText(QRectF(rect.right() - 12 - space, 0, space, rect.height()),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             painter.fontMetrics().elidedText(self._hint, Qt.TextElideMode.ElideRight, int(space)))
            return
        paint_avatar(painter, QRectF(10, center - 17, 34, 34), self.info.color, self.info.name)
        left, right = 56.0, rect.right() - (38 if self._checked else 12)
        width = int(right - left)
        painter.setFont(style.strong(13))
        painter.setPen(style.primary())
        painter.drawText(QRectF(left, center - 19, width, 20), align,
                         painter.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, width))
        kind, text = self._status
        tone = STATUS.get(kind, ("neutral", None))[0]
        line = " · ".join(filter(None, (account_line(self.info), text)))
        painter.setFont(style.font(12))
        painter.setPen(style.status_line(tone) if tone in ("error", "warning") else style.muted())
        painter.drawText(QRectF(left, center + 1, width, 18), align,
                         painter.fontMetrics().elidedText(line, Qt.TextElideMode.ElideRight, width))
        if self._checked:
            style.glyph(painter, "check", QRectF(rect.right() - 30, center - 8, 16, 16), style.link(), 1.7)


class AccountSwitcher(FlyoutViewBase):
    accountClicked = Signal(str)
    addClicked = Signal()
    manageClicked = Signal()

    def __init__(self, model, parent=None):
        super().__init__(parent)
        active = model.active()
        reason = model.unsupported_reason()
        head = QHBoxLayout()
        head.setContentsMargins(12, 4, 12, 4)
        title = tr("切换要查看和编辑的账号") if active else tr("已保存的账号")
        head.addWidget(secondary(CaptionLabel(title, self)))
        head.addStretch(1)
        state = tr("轮流运行：开") if active else tr("轮流运行：关")
        head.addWidget(secondary(CaptionLabel(state, self)))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 8, 6, 8)
        layout.setSpacing(2)
        layout.addLayout(head)
        current = model.current()
        infos = model.accounts()
        rows = QWidget(self)
        rows.setObjectName("view")
        rows.setStyleSheet("#view{background: transparent}")
        column = QVBoxLayout(rows)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(2)
        for info in infos:
            if active:
                status, checked = (info.status.kind, info.status.text), info.uid == current
            else:
                status, checked = ("login", tr("当前登录")) if info.logged_in else ("idle", ""), info.logged_in
            row = _Row(rows, info=info, status=status, checked=checked)
            row.clicked.connect(lambda _=False, uid=info.uid: self._emit(self.accountClicked, uid))
            column.addWidget(row)
        if len(infos) > MAX_ROWS:
            scroll = ScrollArea(self)
            scroll.setWidgetResizable(True)
            scroll.enableTransparentBackground()
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setWidget(rows)
            scroll.setFixedHeight(MAX_ROWS * 54)
            layout.addWidget(scroll)
        else:
            layout.addWidget(rows)
        if reason:
            note = secondary(CaptionLabel(reason, self))
            note.setWordWrap(True)
            note.setContentsMargins(12, 4, 12, 6)
            layout.addWidget(note)
        layout.addWidget(Divider(self))
        add = _Row(self, text=tr("添加账号"), hint=tr("从当前游戏登录导入"), icon=FluentIcon.ADD)
        add.clicked.connect(lambda: self._emit(self.addClicked))
        manage = _Row(self, text=tr("管理账号与轮流顺序"), icon=FluentIcon.PEOPLE)
        manage.clicked.connect(lambda: self._emit(self.manageClicked))
        layout.addWidget(add)
        layout.addWidget(manage)
        self.setFixedWidth(WIDTH)
        self.flyout = None

    def _emit(self, signal, *args):
        if self.flyout is not None:
            self.flyout.close()
        signal.emit(*args)

    def open(self, target):
        self.flyout = Flyout.make(self, target, target.window(), aniType=FlyoutAnimationType.DROP_DOWN)
        return self.flyout
