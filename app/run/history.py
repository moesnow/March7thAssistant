"""运行记录：按天列出每次运行，右侧看步骤、原因、截图和日志。"""
from datetime import timedelta

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QStackedWidget, QStyle, QStyledItemDelegate, QVBoxLayout, QWidget)
from qfluentwidgets import (BodyLabel, ComboBox, FluentIcon, PrimaryPushButton, PushButton, SimpleCardWidget,
                            SmoothScrollDelegate, TitleLabel, TransparentPushButton, qconfig)

from app.common.mascot import Mascot, load_mascot
from app.common.schedule import schedule_weekday_labels
from app.overview.style import format_duration
from app.overview.widgets import LinkButton
from app.pages import style
from app.pages.common import Divider, is_evernight, secondary, style_primary
from module.localization import tr
from .cards import BADGES, RUN_TONES, RunCard, run_text
from .log_view import LogPanel

ENTRY_ROLE = Qt.ItemDataRole.UserRole
HEADER_HEIGHT, ROW_HEIGHT, LIST_WIDTH = 34, 56, 336


def day_text(day, today):
    if day == today:
        return tr("今天")
    if day == today - timedelta(days=1):
        return tr("昨天")
    weekday = schedule_weekday_labels()[day.isoweekday() - 1]
    date = day.strftime("%m-%d") if day.year == today.year else day.strftime("%Y-%m-%d")
    return f"{date} {weekday}"


class HistoryDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(0, ROW_HEIGHT if index.data(ENTRY_ROLE) else HEADER_HEIGHT)

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        rect = QRectF(option.rect)
        align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        entry = self.parent().entry(index.data(ENTRY_ROLE))
        if entry is None:
            painter.setFont(style.strong(12))
            painter.setPen(style.muted())
            painter.drawText(rect.adjusted(16, 8, -12, 0), align, index.data(Qt.ItemDataRole.DisplayRole) or "")
            painter.restore()
            return
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if selected or option.state & QStyle.StateFlag.State_MouseOver:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(style.selected_fill() if selected else style.hover_fill())
            painter.drawRoundedRect(rect.adjusted(6, 1, -6, -1), 6, 6)
        if selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(style.link())
            painter.drawRoundedRect(QRectF(rect.left() + 6, rect.center().y() - 10, 3, 20), 1.5, 1.5)
        center = rect.center().y()
        circle = QRectF(rect.left() + 18, center - 11, 22, 22)
        tone, mark = BADGES.get(entry.status, (RUN_TONES.get(entry.status, "neutral"), "dot"))
        if entry.status in ("aborted", "interrupted", "blocked"):
            mark = "alert"
        background, foreground = style.status_colors(tone)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawEllipse(circle)
        inner = circle.adjusted(4, 4, -4, -4) if mark == "alert" else circle.adjusted(5, 5, -5, -5)
        style.glyph(painter, mark, inner, foreground, 1.5)
        left, right = rect.left() + 52, rect.right() - 16
        duration = format_duration(entry.seconds)
        painter.setFont(style.font(12))
        painter.setPen(style.faint())
        space = painter.fontMetrics().horizontalAdvance(duration) if duration else 0
        painter.drawText(QRectF(right - space, center - 20, space, 20), align, duration)
        width = max(0, int(right - space - 10 - left))
        painter.setFont(style.strong(13))
        painter.setPen(style.primary())
        painter.drawText(QRectF(left, center - 20, width, 20), align,
                         painter.fontMetrics().elidedText(entry.title, Qt.TextElideMode.ElideRight, width))
        painter.setFont(style.font(12))
        who = tr("{count} 个账号").format(count=len(entry.accounts)) if entry.accounts else entry.account.name if entry.account else ""
        parts = [entry.started_at.strftime("%H:%M"), who, entry.trigger_text]
        problem = entry.status not in ("success", "running")
        if problem:
            parts.insert(1, run_text(entry.status))
        line = " · ".join(filter(None, parts))
        width = int(right - left)
        painter.setPen(style.status_line(tone) if tone in ("error", "warning") else style.muted())
        painter.drawText(QRectF(left, center, width, 18), align,
                         painter.fontMetrics().elidedText(line, Qt.TextElideMode.ElideRight, width))
        painter.restore()


class HistoryList(QListWidget):
    entrySelected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries = {}
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("QListWidget { background: transparent; border: none; outline: none; }")
        self.viewport().setAutoFillBackground(False)
        self.setMouseTracking(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setItemDelegate(HistoryDelegate(self))
        self.scrollDelegate = SmoothScrollDelegate(self)
        self.setAccessibleName(tr("运行记录"))
        self.currentItemChanged.connect(self._changed)

    def entry(self, run_id):
        return self._entries.get(run_id) if run_id else None

    def setDays(self, days, today, selected=None):
        self._entries = {entry.id: entry for _, entries in days for entry in entries}
        position = self.verticalScrollBar().value()
        self.blockSignals(True)
        self.clear()
        for day, entries in days:
            header = QListWidgetItem(day_text(day, today))
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            self.addItem(header)
            for entry in entries:
                item = QListWidgetItem()
                item.setData(ENTRY_ROLE, entry.id)
                item.setData(Qt.ItemDataRole.AccessibleTextRole, f"{entry.title} {run_text(entry.status)}")
                self.addItem(item)
        self.blockSignals(False)
        self.verticalScrollBar().setValue(position)
        if not self.select(selected):
            self.select(next(iter(self._entries), None))

    def select(self, run_id):
        for index in range(self.count()):
            if run_id and self.item(index).data(ENTRY_ROLE) == run_id:
                self.setCurrentRow(index)
                return True
        return False

    def selectedId(self):
        item = self.currentItem()
        return item.data(ENTRY_ROLE) if item is not None else None

    def _changed(self, item, previous):
        if item is not None and item.data(ENTRY_ROLE):
            self.entrySelected.emit(item.data(ENTRY_ROLE))


class HistoryPage(QWidget):
    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self._shown = None
        self.accountCombo = ComboBox(self)
        self.resultCombo = ComboBox(self)
        for combo in (self.accountCombo, self.resultCombo):
            combo.currentIndexChanged.connect(lambda *_: self.refresh())
        filters = QHBoxLayout()
        filters.setContentsMargins(12, 10, 12, 8)
        filters.setSpacing(8)
        filters.addWidget(self.accountCombo, 1)
        filters.addWidget(self.resultCombo, 1)
        self.listCard = SimpleCardWidget(self)
        self.listCard.setBorderRadius(8)
        self.listCard.setFixedWidth(LIST_WIDTH)
        self.list = HistoryList(self.listCard)
        self.list.entrySelected.connect(self.show_)
        self.noneLabel = secondary(BodyLabel(self.listCard))
        self.noneLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side = QVBoxLayout(self.listCard)
        side.setContentsMargins(0, 0, 0, 6)
        side.setSpacing(0)
        side.addLayout(filters)
        side.addWidget(Divider(self.listCard))
        side.addWidget(self.list, 1)
        side.addWidget(self.noneLabel, 1)
        self.card = RunCard(self)
        self.card.accountClicked.connect(self.show_)
        self.screenshotButton = PushButton(FluentIcon.PHOTO, "", self)
        self.screenshotButton.clicked.connect(lambda: self.model.open_screenshot(self._shown))
        self.retryButton = PushButton(FluentIcon.SYNC, "", self)
        self.retryButton.clicked.connect(lambda: self.model.retry(self._shown))
        self.parentButton = TransparentPushButton(FluentIcon.PEOPLE, "", self)
        self.parentButton.clicked.connect(self._showParent)
        for widget in (self.parentButton, self.screenshotButton, self.retryButton):
            self.card.actions.addWidget(widget)
        self.log = LogPanel(self, live=False)
        self.log.setFilter("important")
        self.log.folderRequested.connect(lambda: self.model.open_log(self._shown))
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(12)
        right.addWidget(self.card)
        right.addWidget(self.log, 1)
        self.body = QWidget(self)
        columns = QHBoxLayout(self.body)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(16)
        columns.addWidget(self.listCard)
        columns.addLayout(right, 1)
        self.empty = QWidget(self)
        self.mascot = QLabel(self.empty)
        self.emptyTitle = TitleLabel(self.empty)
        self.emptyText = secondary(BodyLabel(self.empty))
        column = QVBoxLayout(self.empty)
        column.setSpacing(8)
        column.addStretch(1)
        for widget in (self.mascot, self.emptyTitle, self.emptyText):
            column.addWidget(widget, 0, Qt.AlignmentFlag.AlignHCenter)
        column.addStretch(2)
        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.body)
        self.stack.addWidget(self.empty)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)
        self.model.changed.connect(self._modelChanged)
        qconfig.themeChanged.connect(self._restyle)
        qconfig.themeColorChanged.connect(self._restyle)
        self.retranslateUi()

    def retranslateUi(self):
        self.screenshotButton.setText(tr("查看截图"))
        self.parentButton.setText(tr("查看整轮"))
        self.emptyTitle.setText(tr("还没有运行记录"))
        self.emptyText.setText(tr("运行过的任务会按天列在这里，可以查看步骤、原因和日志。"))
        self.noneLabel.setText(tr("没有符合条件的记录"))
        self.log.retranslateUi()
        self.log.folderButton.setText(tr("打开日志文件"))
        self._fillFilters()
        self._restyle()
        self.refresh()

    def _restyle(self, *_):
        self.mascot.setPixmap(load_mascot(Mascot.OK, 180, self.devicePixelRatioF(), evernight=is_evernight()))
        if self.isVisible() and self._shown is not None:
            self._render(self._shown)
        self.list.viewport().update()

    def _fillFilters(self):
        account, result = self.accountCombo.currentData(), self.resultCombo.currentData()
        for combo in (self.accountCombo, self.resultCombo):
            combo.blockSignals(True)
            combo.clear()
        self.accountCombo.addItem(tr("全部账号"), userData=None)
        for ref in self.model.accounts():
            self.accountCombo.addItem(ref.name, userData=ref.uid)
        self.accountCombo.setVisible(self.accountCombo.count() > 1)
        self.resultCombo.addItem(tr("全部结果"), userData=False)
        self.resultCombo.addItem(tr("失败和异常"), userData=True)
        self.accountCombo.setCurrentIndex(max(0, self.accountCombo.findData(account)))
        self.resultCombo.setCurrentIndex(1 if result else 0)
        for combo in (self.accountCombo, self.resultCombo):
            combo.blockSignals(False)

    def _modelChanged(self):
        if self.isVisible():
            self._fillFilters()
            self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self._fillFilters()
        self.refresh()

    def refresh(self):
        if not self.isVisible():
            return
        selected = self.list.selectedId()
        days = self.model.days(account=self.accountCombo.currentData(), problems=bool(self.resultCombo.currentData()))
        self.stack.setCurrentWidget(self.body if days or self.model.any() else self.empty)
        self.list.setVisible(bool(days))
        self.noneLabel.setVisible(not days)
        self.list.setDays(days, self.model.today(), selected)
        if not days:
            self._shown = None
            self.card.hide()
            self.log.clear()

    def select(self, run_id):
        """从总览、账号页跳过来：先清掉筛选，再选中这次运行。"""
        entry = self.model.entry(run_id)
        if entry is None:
            return False
        for combo in (self.accountCombo, self.resultCombo):
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        self.refresh()
        if not self.list.select(run_id) and entry.parent_id:
            self.list.select(entry.parent_id)
        self.show_(run_id)
        return True

    def show_(self, run_id):
        entry = self.model.entry(run_id)
        if entry is None:
            return
        changed = self._shown is None or self._shown.id != entry.id
        self._shown = entry
        self._render(entry)
        if changed or entry.status == "running":
            self.log.setEntries(self.model.log(entry))

    def _showParent(self):
        if self._shown is not None and self._shown.parent_id:
            self.show_(self._shown.parent_id)

    def _render(self, entry):
        self.card.show()
        self.card.setTitle(entry.title, entry.status)
        ended = entry.started_at + timedelta(seconds=entry.seconds) if entry.seconds is not None else None
        span = entry.started_at.strftime("%m-%d %H:%M") + (f" – {ended:%H:%M}" if ended else "")
        self.card.setPills(run_text(entry.status), RUN_TONES.get(entry.status, "neutral"))
        duration = tr("用时 {time}").format(time=format_duration(entry.seconds)) if entry.seconds else ""
        self.card.setSubtitle(" · ".join(filter(None, (span, duration, entry.trigger_text))))
        parent = self.model.entry(entry.parent_id) if entry.parent_id else None
        accounts = entry.accounts or (parent.accounts if parent is not None else ())
        self.card.setAccount(entry.account)
        self.card.setAccounts(accounts, entry.account.uid if entry.account else None)
        self.card.setSteps(entry.steps)
        tone = RUN_TONES.get(entry.status) if entry.status not in ("success", "running") else None
        self.card.setFoot(entry.reason, tone=tone if tone in ("error", "warning") else None)
        self.parentButton.setVisible(bool(entry.parent_id))
        self.screenshotButton.setVisible(bool(entry.screenshot))
        retry = self.model.retry_text(entry)
        self.retryButton.setVisible(bool(retry))
        self.retryButton.setText(retry)
