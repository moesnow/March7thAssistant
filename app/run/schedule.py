"""定时计划：一周概览和计划列表。编辑用 app.schedule_dialog 的表单。"""
from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QFontMetrics, QPainter
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QToolTip, QVBoxLayout, QWidget
from qfluentwidgets import (Action, BodyLabel, CaptionLabel, ComboBox, FluentIcon, MessageBox, PrimaryPushButton,
                            RoundMenu, ScrollArea, SimpleCardWidget, StrongBodyLabel, TransparentToolButton, qconfig)

from app.common.mascot import Mascot
from app.common.schedule import schedule_weekday_labels
from app.components.mascot_dialog import add_mascot
from app.overview.style import format_when, with_alpha
from app.overview.widgets import ElidedLabel, Pill
from app.pages import style
from app.pages.common import Divider, bare_switch, is_evernight, popup_menu, secondary, style_primary
from module.localization import tr

CHIP_HEIGHT, CHIP_GAP, HEADER = 24, 4, 40
MAX_CHIPS = 4


class WeekView(QWidget):
    """从今天起七天，每列按时间列出当天会触发的计划。"""
    itemClicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._days = ()
        self._next = None
        self._hover = None
        self.setFixedHeight(HEADER + 2 * (CHIP_HEIGHT + CHIP_GAP) + 6)

    def setWeek(self, days):
        """days：从今天起的七天，每天 (日期, 是否今天, 当天的触发项)。"""
        self._days = tuple(days)
        rows = min(MAX_CHIPS, max([2, *(len(items) for _, _, items in self._days)]))
        self.setFixedHeight(HEADER + rows * (CHIP_HEIGHT + CHIP_GAP) + 6)
        self.update()

    def _column(self, index):
        gap, inset = 8.0, 4.0
        width = (self.width() - inset * 2 - gap * 6) / 7
        return QRectF(inset + index * (width + gap), 0, width, self.height())

    def _chips(self):
        for column, (_, _, items) in enumerate(self._days):
            rect = self._column(column)
            more = len(items) > MAX_CHIPS
            for row, item in enumerate(items[:MAX_CHIPS]):
                chip = QRectF(rect.left(), HEADER + row * (CHIP_HEIGHT + CHIP_GAP), rect.width(), CHIP_HEIGHT)
                rest = items[row:] if more and row == MAX_CHIPS - 1 else None
                yield chip, item, rest

    def _at(self, position):
        for chip, item, rest in self._chips():
            if chip.contains(QPointF(position)):
                return item, rest
        return None, None

    def event(self, event):
        if event.type() == QEvent.Type.ToolTip:
            item, rest = self._at(event.pos())
            if item is not None:
                QToolTip.showText(event.globalPos(), "\n".join(f"{entry.time} {entry.name}" for entry in rest or (item,)), self)
            return True
        return super().event(event)

    def mouseMoveEvent(self, event):
        item, _ = self._at(event.position())
        self.setCursor(Qt.CursorShape.PointingHandCursor if item is not None else Qt.CursorShape.ArrowCursor)
        if item is not self._hover:
            self._hover = item
            self.update()

    def leaveEvent(self, event):
        self._hover = None
        self.update()

    def mouseReleaseEvent(self, event):
        item, _ = self._at(event.position())
        if event.button() == Qt.MouseButton.LeftButton and item is not None:
            self.itemClicked.emit(item.id)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        labels = schedule_weekday_labels()
        for index, (day, today, items) in enumerate(self._days):
            rect = self._column(index)
            if today:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(with_alpha(style.status_colors("accent")[1], 0.06))
                painter.drawRoundedRect(rect.adjusted(-4, 0, 4, 0), 6, 6)
            painter.setFont(style.strong(13) if today else style.font(13))
            painter.setPen(style.link() if today else style.muted())
            painter.drawText(QRectF(rect.left() + 2, 4, rect.width() - 4, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             f"{labels[day.isoweekday() - 1]}" + (f" · {tr('今天')}" if today else ""))
            painter.setFont(style.font(12))
            painter.setPen(style.faint())
            painter.drawText(QRectF(rect.left() + 2, 20, rect.width() - 4, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             day.strftime("%m-%d"))
            if not items:
                painter.setPen(style.faint())
                painter.drawText(QRectF(rect.left() + 2, HEADER, rect.width() - 4, CHIP_HEIGHT),
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "–")
        for chip, item, rest in self._chips():
            background, foreground = style.status_colors("accent" if item.next else "neutral")
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(background)
            painter.drawRoundedRect(chip, 5, 5)
            if item is self._hover:
                painter.setBrush(style.hover_fill())
                painter.drawRoundedRect(chip, 5, 5)
            painter.setBrush(foreground if item.next else style.faint())
            painter.drawRoundedRect(QRectF(chip.left(), chip.top(), 3, chip.height()), 1.5, 1.5)
            color = style.link() if item.next else style.faint() if item.past else style.primary()
            if rest:
                painter.setFont(style.font(12))
                painter.setPen(style.muted())
                painter.drawText(chip.adjusted(10, 0, -6, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                                 tr("还有 {count} 项").format(count=len(rest)))
                continue
            bold = style.strong(12)
            painter.setFont(bold)
            painter.setPen(color)
            width = QFontMetrics(bold).horizontalAdvance(item.time)
            painter.drawText(chip.adjusted(10, 0, 0, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, item.time)
            normal = style.font(12)
            painter.setFont(normal)
            space = int(chip.width() - width - 10 - 8 - 6)
            painter.drawText(QRectF(chip.left() + 10 + width + 8, chip.top(), space, chip.height()),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             QFontMetrics(normal).elidedText(item.name, Qt.TextElideMode.ElideRight, space))


class TimeMark(QWidget):
    """计划行左侧的时间；链式计划画一个承接上一项的折线。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(66, 40)
        self._time, self._enabled = "", True

    def setTime(self, time, enabled):
        self._time, self._enabled = time, enabled
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        color = style.primary() if self._enabled else style.faint()
        if self._time:
            painter.setFont(style.strong(18))
            painter.setPen(color)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._time)
            return
        painter.setPen(style.stroke(style.faint(), 1.6))
        painter.drawLine(QPointF(26, 4), QPointF(26, 20))
        painter.drawLine(QPointF(26, 20), QPointF(46, 20))
        painter.drawLine(QPointF(41, 15), QPointF(46, 20))
        painter.drawLine(QPointF(41, 25), QPointF(46, 20))


class ScheduleRow(QWidget):
    toggled = Signal(str, bool)
    runClicked = Signal(str)
    editClicked = Signal(str)
    menuRequested = Signal(str, QWidget)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.id = ""
        self.setFixedHeight(62)
        self.switch = bare_switch(self)
        self.switch.checkedChanged.connect(lambda on: self.toggled.emit(self.id, on))
        self.time = TimeMark(self)
        self.nameLabel = ElidedLabel(self, size=14)
        self.nameLabel.setFont(style.strong(14))
        self.detailLabel = secondary(ElidedLabel(self, size=12))
        self.accountPill = Pill(self)
        self.nextPill = Pill(self)
        self.runButton = TransparentToolButton(FluentIcon.PLAY, self)
        self.runButton.clicked.connect(lambda: self.runClicked.emit(self.id))
        self.editButton = TransparentToolButton(FluentIcon.EDIT, self)
        self.editButton.clicked.connect(lambda: self.editClicked.emit(self.id))
        self.moreButton = TransparentToolButton(FluentIcon.MORE, self)
        self.moreButton.clicked.connect(lambda: self.menuRequested.emit(self.id, self.moreButton))
        for button in (self.runButton, self.editButton, self.moreButton):
            button.setFixedSize(32, 32)
        name = QHBoxLayout()
        name.setSpacing(8)
        name.addWidget(self.nameLabel)
        name.addWidget(self.accountPill)
        name.addWidget(self.nextPill)
        name.addStretch(1)
        column = QVBoxLayout()
        column.setSpacing(2)
        column.addLayout(name)
        column.addWidget(self.detailLabel)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 8, 12, 8)
        layout.setSpacing(14)
        layout.addWidget(self.switch)
        layout.addWidget(self.time)
        layout.addLayout(column, 1)
        for button in (self.runButton, self.editButton, self.moreButton):
            layout.addWidget(button)
        self._highlight = False

    def setItem(self, item, now):
        self.id = item.id
        self.switch.blockSignals(True)
        self.switch.setChecked(item.enabled)
        self.switch.blockSignals(False)
        self.switch.setAccessibleName(item.name)
        self.time.setTime("" if item.chained else item.time, item.enabled)
        self.nameLabel.setFullText(item.name)
        color = style.primary() if item.enabled else style.faint()
        self.nameLabel.setTextColor(color, color)
        self.detailLabel.setFullText(item.detail)
        evernight = is_evernight()
        self.accountPill.setVisible(bool(item.account_text))
        self.accountPill.setPill(item.account_text, "warning" if item.account_problem else "neutral", evernight=evernight)
        self.accountPill.setToolTip(item.account_problem)
        self.nextPill.setVisible(item.next)
        self.nextPill.setPill(tr("下次：{time}").format(time=format_when(item.next_at, now)) if item.next else "", "accent", evernight=evernight)
        for button, text in ((self.runButton, tr("立即运行")), (self.editButton, tr("编辑")), (self.moreButton, tr("更多"))):
            button.setToolTip(text)
            button.setAccessibleName(text)

    def flash(self):
        self._highlight = True
        self.update()

    def enterEvent(self, event):
        self.update()

    def leaveEvent(self, event):
        self._highlight = False
        self.update()

    def mouseDoubleClickEvent(self, event):
        self.editClicked.emit(self.id)

    def paintEvent(self, event):
        if self._highlight or self.underMouse():
            painter = QPainter(self)
            painter.fillRect(self.rect(), style.status_colors("accent")[0] if self._highlight else style.hover_fill())


class SchedulePage(QWidget):
    addClicked = Signal()
    editClicked = Signal(str)
    runClicked = Signal(str)

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self.summaryLabel = secondary(BodyLabel(self))
        self.addButton = PrimaryPushButton(FluentIcon.ADD, "", self)
        self.addButton.clicked.connect(self.addClicked)
        head = QHBoxLayout()
        head.setSpacing(12)
        head.addWidget(self.summaryLabel, 1)
        head.addWidget(self.addButton)
        self.weekCard = SimpleCardWidget(self)
        self.weekCard.setBorderRadius(8)
        self.week = WeekView(self.weekCard)
        self.week.itemClicked.connect(self.reveal)
        inner = QVBoxLayout(self.weekCard)
        inner.setContentsMargins(18, 12, 18, 10)
        inner.addWidget(self.week)
        self.listCard = SimpleCardWidget(self)
        self.listCard.setBorderRadius(8)
        self.scroll = ScrollArea(self.listCard)
        self.scroll.setWidgetResizable(True)
        self.scroll.enableTransparentBackground()
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view = QWidget()
        self.view.setObjectName("view")
        self.scroll.setWidget(self.view)
        self.view.setStyleSheet("#view{background: transparent}")
        self.rowsLayout = QVBoxLayout(self.view)
        self.rowsLayout.setContentsMargins(0, 0, 0, 0)
        self.rowsLayout.setSpacing(0)
        self.emptyLabel = StrongBodyLabel(self.view)
        self.emptyLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.emptyHint = secondary(CaptionLabel(self.view))
        self.emptyHint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rowsLayout.addStretch(1)
        self.rowsLayout.addWidget(self.emptyLabel)
        self.rowsLayout.addWidget(self.emptyHint)
        self.rowsLayout.addStretch(1)
        self.rows = []
        self.conflictLabel = secondary(CaptionLabel(self.listCard))
        self.conflictCombo = ComboBox(self.listCard)
        self.conflictCombo.currentIndexChanged.connect(self._conflictChanged)
        self.chainLabel = secondary(CaptionLabel(self.listCard))
        self.chainCombo = ComboBox(self.listCard)
        self.chainCombo.currentIndexChanged.connect(self._chainChanged)
        foot = QHBoxLayout()
        foot.setContentsMargins(18, 8, 14, 8)
        foot.setSpacing(8)
        foot.addWidget(self.conflictLabel)
        foot.addWidget(self.conflictCombo)
        foot.addSpacing(16)
        foot.addWidget(self.chainLabel)
        foot.addWidget(self.chainCombo)
        foot.addStretch(1)
        body = QVBoxLayout(self.listCard)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self.scroll, 1)
        body.addWidget(Divider(self.listCard))
        body.addLayout(foot)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addLayout(head)
        layout.addWidget(self.weekCard)
        layout.addWidget(self.listCard, 1)
        self.model.changed.connect(self._modelChanged)
        qconfig.themeChanged.connect(self._restyle)
        qconfig.themeColorChanged.connect(self._restyle)
        self.retranslateUi()
        self._restyle()

    def retranslateUi(self):
        self.addButton.setText(tr("添加定时计划"))
        self.emptyLabel.setText(tr("还没有定时计划"))
        self.emptyHint.setText(tr("添加后，到点会自动运行任务、流程或外部程序"))
        self.conflictLabel.setText(tr("已有任务在运行时"))
        self.chainLabel.setText(tr("链式任务失败后"))
        for combo, options in ((self.conflictCombo, (("skip", tr("跳过需要运行的任务")), ("stop", tr("停止正在运行的任务")))),
                               (self.chainCombo, ((True, tr("继续后续任务")), (False, tr("停止后续任务"))))):
            combo.blockSignals(True)
            combo.clear()
            for value, text in options:
                combo.addItem(text, userData=value)
            combo.blockSignals(False)
        self.refresh()

    def _restyle(self, *_):
        style_primary(self.addButton, is_evernight())
        self.refresh()

    def _modelChanged(self):
        if self.isVisible() and not self.window().isMinimized():
            self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def refresh(self):
        items = self.model.items()
        now = self.model.now()
        while len(self.rows) > len(items):
            row, line = self.rows.pop()
            for widget in (row, line):
                self.rowsLayout.removeWidget(widget)
                widget.hide()
                widget.deleteLater()
        while len(self.rows) < len(items):
            row, line = ScheduleRow(self.view), Divider(self.view)
            row.toggled.connect(self.model.set_enabled)
            row.runClicked.connect(self.runClicked)
            row.editClicked.connect(self.editClicked)
            row.menuRequested.connect(self._menu)
            index = len(self.rows) * 2
            self.rowsLayout.insertWidget(index, row)
            self.rowsLayout.insertWidget(index + 1, line)
            self.rows.append((row, line))
        for (row, _), item in zip(self.rows, items):
            row.setItem(item, now)
        self.emptyLabel.setVisible(not items)
        self.emptyHint.setVisible(not items)
        self.weekCard.setVisible(bool(items))
        self.week.setWeek(self.model.week())
        self.summaryLabel.setText(self.model.summary())
        for combo, value in ((self.conflictCombo, self.model.conflict()), (self.chainCombo, self.model.chain_continue())):
            combo.blockSignals(True)
            combo.setCurrentIndex(max(0, combo.findData(value)))
            combo.blockSignals(False)

    def reveal(self, item_id):
        for row, _ in self.rows:
            if row.id == item_id:
                self.scroll.ensureWidgetVisible(row)
                row.flash()
                return True
        return False

    def _conflictChanged(self, index):
        self.model.set_conflict(self.conflictCombo.itemData(index))

    def _chainChanged(self, index):
        self.model.set_chain_continue(self.chainCombo.itemData(index))

    def _remove(self, item_id):
        item = next((item for item in self.model.items() if item.id == item_id), None)
        if item is None:
            return
        box = MessageBox(tr("删除定时计划"), tr("确定删除「{name}」吗？").format(name=item.name), self.window())
        box.yesButton.setText(tr("删除"))
        box.cancelButton.setText(tr("取消"))
        add_mascot(box, Mascot.BOX)
        box.cancelButton.setFocus()
        if box.exec():
            self.model.remove(item_id)

    def _menu(self, item_id, button):
        menu = RoundMenu(parent=self)
        up = Action(FluentIcon.UP, tr("上移"), triggered=lambda: self.model.move(item_id, -1))
        down = Action(FluentIcon.DOWN, tr("下移"), triggered=lambda: self.model.move(item_id, 1))
        up.setEnabled(self.model.can_move(item_id, -1))
        down.setEnabled(self.model.can_move(item_id, 1))
        menu.addAction(up)
        menu.addAction(down)
        menu.addAction(Action(FluentIcon.COPY, tr("复制一份"), triggered=lambda: self.model.duplicate(item_id, self.window())))
        menu.addSeparator()
        menu.addAction(Action(FluentIcon.DELETE, tr("删除…"), triggered=lambda: self._remove(item_id)))
        popup_menu(self, menu, button.mapToGlobal(button.rect().bottomLeft()))
