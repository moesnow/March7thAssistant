"""任务日志：时间、级别和内容分列，按级别筛选，跟随最新一行。"""
from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import (QColor, QFontMetricsF, QTextBlockFormat, QTextCharFormat, QTextCursor, QTextFormat,
                           QTextOption)
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QTextEdit, QVBoxLayout
from qfluentwidgets import (Action, FluentIcon, MenuAnimationType, PushButton, RoundMenu, SimpleCardWidget,
                            SmoothScrollDelegate, StrongBodyLabel, TransparentPushButton, qconfig)

from app.common.icon import UiIcon
from app.gacha.chips import Chip
from app.overview.style import css, with_alpha
from app.pages import style
from app.pages.common import Divider, popup_menu
from module.localization import tr

MAX_LINES = 5000
FILTERS = ("important", "all", "problems")
TIME_WIDTH, LEVEL_GAP = 84, 14


def level_text(level):
    return {"debug": tr("调试"), "info": tr("信息"), "warning": tr("警告"), "error": tr("错误")}.get(level, "")


class LogView(QTextEdit):
    """只读日志。换行后的内容对齐到消息列，可以跨行选择和复制。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setUndoRedoEnabled(False)
        self.setAcceptRichText(False)
        self.setFrameShape(QTextEdit.Shape.NoFrame)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.document().setMaximumBlockCount(MAX_LINES)
        self.document().setDocumentMargin(12)
        self.scrollDelegate = SmoothScrollDelegate(self)
        self._highlight = False
        self._count = 0
        self.setAccessibleName(tr("任务日志"))
        self.restyle()

    def restyle(self):
        self.setFont(style.mono(13))
        self.setStyleSheet(f"QTextEdit {{ background: transparent; border: none; color: {css(style.primary())};"
                           f" selection-background-color: {css(with_alpha(style.link(), 0.30))};"
                           f" selection-color: {css(style.primary())}; }}")

    def _columns(self):
        metrics = QFontMetricsF(self.font())
        time = max(TIME_WIDTH, metrics.horizontalAdvance("00:00:00") + 14)
        level = max(metrics.horizontalAdvance(level_text(name)) for name in ("debug", "info", "warning", "error"))
        return time, time + level + LEVEL_GAP

    def _block(self, entry, columns):
        time, message = columns
        block = QTextBlockFormat()
        block.setLineHeight(150, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        if entry.kind == "title":
            block.setTopMargin(8)
            block.setBottomMargin(2)
        elif entry.kind == "line":
            block.setLeftMargin(message)
            block.setTextIndent(-message)
            block.setTabPositions([QTextOption.Tab(time, QTextOption.TabType.LeftTab),
                                   QTextOption.Tab(message, QTextOption.TabType.LeftTab)])
        else:
            block.setLeftMargin(message)
        return block

    @staticmethod
    def _char(color, *, bold=False):
        result = QTextCharFormat()
        result.setForeground(QColor(color))
        if bold:
            result.setFontWeight(600)
        return result

    def _insert(self, cursor, entry, columns):
        block = self._block(entry, columns)
        if self._count:
            cursor.insertBlock(block)
        else:
            cursor.setBlockFormat(block)
        self._count += 1
        if entry.kind == "title":
            cursor.insertText(entry.text, self._char(style.link(), bold=True))
        elif entry.kind == "line":
            problem = entry.level in ("warning", "error")
            tone = {"warning": "warning", "error": "error"}.get(entry.level)
            cursor.insertText(entry.time + "\t", self._char(style.faint()))
            cursor.insertText(level_text(entry.level) + "\t", self._char(style.status_line(tone) if tone else style.muted()))
            color = style.status_line("error") if entry.level == "error" else style.muted() if entry.level == "debug" else style.primary()
            cursor.insertText(entry.text, self._char(color if not problem or entry.level == "error" else style.primary()))
        else:
            cursor.insertText(entry.text, self._char(style.muted()))

    def atBottom(self):
        bar = self.verticalScrollBar()
        return bar.value() >= bar.maximum() - 6

    def toBottom(self):
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

    def setEntries(self, entries):
        self.setUpdatesEnabled(False)
        try:
            self.clear()
            self._count = 0
            columns = self._columns()
            cursor = QTextCursor(self.document())
            cursor.beginEditBlock()
            for entry in entries[-MAX_LINES:]:
                self._insert(cursor, entry, columns)
            cursor.endEditBlock()
        finally:
            self.setUpdatesEnabled(True)
        self._refreshHighlight()
        self.toBottom()

    def append(self, entries):
        follow = self.atBottom()
        columns = self._columns()
        cursor = QTextCursor(self.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.beginEditBlock()
        for entry in entries[-MAX_LINES:]:
            self._insert(cursor, entry, columns)
        cursor.endEditBlock()
        self._refreshHighlight()
        if follow:
            self.toBottom()
        return follow

    def setHighlightLast(self, on):
        if self._highlight != bool(on):
            self._highlight = bool(on)
            self._refreshHighlight()

    def _refreshHighlight(self):
        selections = []
        if self._highlight and self._count:
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(style.status_colors("accent")[0])
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = QTextCursor(self.document())
            selection.cursor.movePosition(QTextCursor.MoveOperation.End)
            selections.append(selection)
        self.setExtraSelections(selections)


class LogPanel(SimpleCardWidget):
    clearRequested = Signal()
    folderRequested = Signal()

    def __init__(self, parent=None, *, live=True):
        super().__init__(parent)
        self.setBorderRadius(8)
        self._live = live
        self._entries = []
        self._pending = []
        self._dirty = False
        self._empty = ""
        self.titleLabel = StrongBodyLabel(self)
        self.group = QButtonGroup(self)
        self.chips = {}
        head = QHBoxLayout()
        head.setContentsMargins(16, 8, 10, 8)
        head.setSpacing(8)
        head.addWidget(self.titleLabel)
        head.addSpacing(4)
        for key in FILTERS:
            chip = Chip(parent=self, soft=True)
            chip.setChecked(key == "important")
            chip.clicked.connect(self._rebuild)
            self.group.addButton(chip)
            self.chips[key] = chip
            head.addWidget(chip)
        head.addStretch(1)
        self.folderButton = TransparentPushButton(FluentIcon.FOLDER, "", self)
        self.folderButton.clicked.connect(self.folderRequested)
        self.copyButton = TransparentPushButton(FluentIcon.COPY, "", self)
        self.copyButton.clicked.connect(self.copyAll)
        head.addWidget(self.folderButton)
        head.addWidget(self.copyButton)
        self.view = LogView(self)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._menu)
        self.view.verticalScrollBar().valueChanged.connect(self._scrolled)
        self.emptyLabel = StrongBodyLabel(self.view)
        self.emptyLabel.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.emptyLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.latestButton = PushButton(FluentIcon.DOWN, "", self)
        self.latestButton.clicked.connect(self.view.toBottom)
        self.latestButton.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(0)
        layout.addLayout(head)
        layout.addWidget(Divider(self))
        layout.addWidget(self.view, 1)
        # 高频日志合并成一批再写入文档，避免逐行重排。
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self._flush)
        qconfig.themeChanged.connect(self._restyle)
        qconfig.themeColorChanged.connect(self._restyle)
        self.retranslateUi()

    def retranslateUi(self):
        self.titleLabel.setText(tr("日志"))
        self.folderButton.setText(tr("打开日志文件夹"))
        self.copyButton.setText(tr("复制"))
        self.latestButton.setText(tr("回到最新"))
        self._updateChips()
        self._rebuild()

    def _restyle(self, *_):
        self.view.restyle()
        self._rebuild()

    def setEmptyText(self, text):
        self._empty = text
        self._updateEmpty()

    def filter(self):
        return next((key for key, chip in self.chips.items() if chip.isChecked()), "important")

    def setFilter(self, key):
        if key in self.chips:
            self.chips[key].setChecked(True)
            self._rebuild()

    def _matches(self, entry):
        key = self.filter()
        if key == "all":
            return True
        if key == "problems":
            return entry.level in ("warning", "error")
        return entry.important

    def _updateChips(self):
        problems = sum(entry.level in ("warning", "error") and entry.kind == "line" for entry in self._entries)
        self.chips["important"].setLabel(tr("重要信息"))
        self.chips["all"].setLabel(tr("全部"))
        self.chips["problems"].setLabel(tr("警告和错误"), str(problems) if problems else "")

    def _updateEmpty(self):
        shown = not self._entries and bool(self._empty)
        self.emptyLabel.setText(self._empty)
        self.emptyLabel.setVisible(shown)
        self.emptyLabel.setGeometry(self.view.rect())

    # ---------- 内容 ----------

    def setEntries(self, entries):
        self._entries = list(entries)[-MAX_LINES:]
        self._pending.clear()
        self._timer.stop()
        self._updateChips()
        self._rebuild()

    def append(self, entries):
        entries = list(entries)
        if not entries:
            return
        self._entries.extend(entries)
        if len(self._entries) > MAX_LINES:
            del self._entries[:-MAX_LINES]
        if not self.isVisible() or self.window().isMinimized():
            self._dirty = True
            return
        self._pending.extend(entries[-MAX_LINES:])
        if len(self._pending) > MAX_LINES:
            del self._pending[:-MAX_LINES]
        if not self._timer.isActive():
            self._timer.start()

    def clear(self):
        self.setEntries(())

    def _flush(self):
        if not self._pending:
            return
        if not self.isVisible() or self.window().isMinimized():
            # 看不见时只攒着，显示时一次重建。
            self._pending.clear()
            self._dirty = True
            return
        batch = [entry for entry in self._pending if self._matches(entry)]
        self._pending.clear()
        self._updateChips()
        self._updateEmpty()
        if batch:
            self.view.append(batch)

    def _rebuild(self, *_):
        self._pending.clear()
        if not self.isVisible():
            self._dirty = True
            return
        selection = self.view.textCursor()
        position, anchor = selection.position(), selection.anchor()
        scroll = self.view.verticalScrollBar()
        value, follow = scroll.value(), self.view.atBottom()
        self._dirty = False
        self.view.setEntries([entry for entry in self._entries if self._matches(entry)])
        if position != anchor:
            cursor = self.view.textCursor()
            end = self.view.document().characterCount() - 1
            cursor.setPosition(min(anchor, end))
            cursor.setPosition(min(position, end), QTextCursor.MoveMode.KeepAnchor)
            self.view.setTextCursor(cursor)
        if not follow:
            scroll.setValue(value)
        self._updateChips()
        self._updateEmpty()

    def showEvent(self, event):
        super().showEvent(event)
        self.resume()

    def resume(self):
        """看不见时攒下的日志，重新看见时一次补上。"""
        if self._dirty or self._pending:
            self._rebuild()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._updateEmpty()
        self._placeLatest()

    def _placeLatest(self):
        self.latestButton.adjustSize()
        self.latestButton.move(self.width() - self.latestButton.width() - 22, self.height() - self.latestButton.height() - 16)
        self.latestButton.raise_()

    def _scrolled(self, *_):
        away = not self.view.atBottom()
        if self.latestButton.isVisible() != (away and self._live):
            self.latestButton.setVisible(away and self._live)
            self._placeLatest()

    def setRunning(self, running):
        self.view.setHighlightLast(running)

    def copyAll(self):
        from utils.clipboard import copy
        copy(self.view.toPlainText())

    def _menu(self, position):
        menu = RoundMenu(parent=self.view)
        copy = Action(FluentIcon.COPY, tr("复制"), triggered=self.view.copy)
        copy.setEnabled(self.view.textCursor().hasSelection())
        menu.addAction(copy)
        menu.addAction(Action(UiIcon.SELECT_ALL, tr("全选"), triggered=self.view.selectAll))
        menu.addSeparator()
        if self._live:
            menu.addAction(Action(FluentIcon.DELETE, tr("清空日志"), triggered=lambda: self.clearRequested.emit()))
        menu.addAction(Action(FluentIcon.FOLDER, tr("打开日志文件夹"), triggered=lambda: self.folderRequested.emit()))
        popup_menu(self, menu, self.view.mapToGlobal(position), aniType=MenuAnimationType.DROP_DOWN)
