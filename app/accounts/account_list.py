"""账号列表：头像、服务器、遮挡后的 UID 和今天的状态，拖动调整轮流顺序。"""
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QFontMetrics, QPainter
from PySide6.QtWidgets import QAbstractItemView, QFrame, QListWidget, QListWidgetItem, QStyle, QStyledItemDelegate
from qfluentwidgets import SmoothScrollDelegate

from app.pages import style
from module.localization import tr
from .avatar import paint_avatar

ROW_HEIGHT = 56
UID_ROLE = Qt.ItemDataRole.UserRole

# 账号状态 -> (配色, 小记号)
STATUS = {
    "running": ("accent", "dot"), "waiting": ("neutral", None), "done": ("success", "check"),
    "partial": ("warning", "alert"), "failed": ("error", "alert"), "expired": ("error", "alert"),
    "no_login": ("error", "alert"), "need_path": ("warning", "alert"), "off": ("neutral", None),
    "idle": ("neutral", None), "login": ("success", "check"),
}


def server_text(server):
    return {"cn": tr("国服"), "global": tr("国际服")}.get(server, "")


def account_line(info):
    """「国服 · UID 1•••789」。"""
    return " · ".join(filter(None, (server_text(info.server), f"UID {info.masked}")))


def paint_pill(painter, right, center, text, kind, glyph=None, *, maximum=None):
    """画一个靠右的状态胶囊，返回它的左边界。"""
    background, foreground = style.status_colors(kind)
    font = style.font(12)
    metrics = QFontMetrics(font)
    extra = 16 if glyph else 0
    if maximum is not None:
        text = metrics.elidedText(text, Qt.TextElideMode.ElideRight, max(0, maximum - 20 - extra))
    width = metrics.horizontalAdvance(text) + 20 + extra
    rect = QRectF(right - width, center - 11, width, 22)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(background)
    painter.drawRoundedRect(rect, 11, 11)
    x = rect.left() + 10
    if glyph:
        style.glyph(painter, glyph, QRectF(x - 1, center - 6, 12, 12), foreground, 1.4)
        x += 16
    painter.setPen(foreground)
    painter.setFont(font)
    painter.drawText(QRectF(x, rect.top(), rect.right() - x, rect.height()),
                     Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
    return rect.left()


class AccountDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(0, ROW_HEIGHT)

    def paint(self, painter, option, index):
        view = self.parent()
        info = view.info(index.data(UID_ROLE))
        if info is None:
            return
        painter.save()
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        rect = QRectF(option.rect)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if selected or option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(rect, style.selected_fill() if selected else style.hover_fill())
        if selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(style.link())
            painter.drawRoundedRect(QRectF(rect.left(), rect.center().y() - 11, 3, 22), 1.5, 1.5)
        center = rect.center().y()
        x = rect.left() + 14
        if view.movable:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(style.faint())
            for column in (0, 5):
                for row in (-5, 0, 5):
                    painter.drawEllipse(QPointF(x + 1 + column, center + row), 1.15, 1.15)
            x += 18
            circle = QRectF(x, center - 10, 20, 20)
            painter.setBrush(style.inset_fill())
            painter.drawEllipse(circle)
            painter.setPen(style.muted() if info.rotate else style.faint())
            painter.setFont(style.font(11))
            painter.drawText(circle, Qt.AlignmentFlag.AlignCenter, str(index.row() + 1) if info.rotate else "–")
            x += 32
        faded = view.movable and not info.rotate
        paint_avatar(painter, QRectF(x, center - 17, 34, 34), info.color, info.name, faded=faded)
        x += 46
        right = rect.right() - 14
        kind, text = view.statusOf(info)
        if text:
            tone, glyph = STATUS.get(kind, ("neutral", None))
            right = paint_pill(painter, right, center, text, tone, glyph, maximum=int(rect.width() * 0.36)) - 10
        width = max(0.0, right - x)
        align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        painter.setFont(style.strong(14))
        painter.setPen(style.muted() if faded else style.primary())
        painter.drawText(QRectF(x, center - 21, width, 22), align,
                         painter.fontMetrics().elidedText(info.name, Qt.TextElideMode.ElideRight, int(width)))
        painter.setFont(style.font(12))
        painter.setPen(style.faint() if faded else style.muted())
        painter.drawText(QRectF(x, center + 1, width, 18), align,
                         painter.fontMetrics().elidedText(account_line(info), Qt.TextElideMode.ElideRight, int(width)))
        painter.fillRect(QRectF(rect.left(), rect.bottom() - 1, rect.width(), 1), style.rule())
        painter.restore()


class AccountList(QListWidget):
    accountSelected = Signal(str)
    orderChanged = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.movable = False
        self._infos = {}
        self._status = None
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("QListWidget { background: transparent; border: none; outline: none; }")
        self.viewport().setAutoFillBackground(False)
        self.setMouseTracking(True)
        self.setUniformItemSizes(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setItemDelegate(AccountDelegate(self))
        self.scrollDelegate = SmoothScrollDelegate(self)
        self.setAccessibleName(tr("账号列表"))
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.currentItemChanged.connect(self._currentChanged)
        self.setMovable(False)

    def setMovable(self, movable):
        self.movable = bool(movable)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove if movable
                             else QAbstractItemView.DragDropMode.NoDragDrop)
        self.viewport().update()

    def setStatusSource(self, function):
        self._status = function

    def statusOf(self, info):
        return self._status(info) if self._status else (info.status.kind, info.status.text)

    def info(self, uid):
        return self._infos.get(uid)

    def setAccounts(self, infos, selected=None):
        """内容更新时保留选中项和滚动位置；顺序没变就不重建。"""
        uids = [info.uid for info in infos]
        self._infos = {info.uid: info for info in infos}
        if uids != self.order():
            position = self.verticalScrollBar().value()
            keep = selected or self.selectedUid()
            self.blockSignals(True)
            self.clear()
            for uid in uids:
                item = QListWidgetItem()
                item.setData(UID_ROLE, uid)
                self.addItem(item)
            self.blockSignals(False)
            self.verticalScrollBar().setValue(position)
            selected = keep if keep in uids else (uids[0] if uids else None)
        for index in range(self.count()):
            info = self._infos[self.item(index).data(UID_ROLE)]
            kind, text = self.statusOf(info)
            self.item(index).setData(Qt.ItemDataRole.AccessibleTextRole, f"{info.name} {account_line(info)} {text}")
            self.item(index).setToolTip(text if kind in ("failed", "partial", "expired", "need_path") else "")
        if selected is not None:
            self.select(selected)
        self.viewport().update()

    def order(self):
        return [self.item(index).data(UID_ROLE) for index in range(self.count())]

    def selectedUid(self):
        item = self.currentItem()
        return item.data(UID_ROLE) if item is not None else None

    def select(self, uid):
        for index in range(self.count()):
            if self.item(index).data(UID_ROLE) == uid:
                if self.currentRow() != index:
                    self.setCurrentRow(index)
                return True
        return False

    def _currentChanged(self, item, previous):
        if item is not None:
            self.accountSelected.emit(item.data(UID_ROLE))

    def dropEvent(self, event):
        before = self.order()
        super().dropEvent(event)
        if self.order() != before:
            self.orderChanged.emit(self.order())

    def keyPressEvent(self, event):
        step = {Qt.Key.Key_Up: -1, Qt.Key.Key_Down: 1}.get(event.key())
        if self.movable and step and event.modifiers() & Qt.KeyboardModifier.AltModifier:
            row = self.currentRow()
            if row >= 0 and 0 <= row + step < self.count():
                self.blockSignals(True)
                item = self.takeItem(row)
                self.insertItem(row + step, item)
                self.setCurrentItem(item)
                self.blockSignals(False)
                self.orderChanged.emit(self.order())
            return
        super().keyPressEvent(event)
