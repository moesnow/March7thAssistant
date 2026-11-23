"""全局搜索（Ctrl+K）：一次搜设置、任务、帮助、工具和页面，回车跳转并高亮目标。"""
from collections import Counter

from PySide6.QtCore import QEvent, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget)
from qfluentwidgets import (BodyLabel, CaptionLabel, FluentIcon, IconWidget, ScrollArea, StrongBodyLabel, getFont,
                            isDarkTheme)

from app.common.mascot import Mascot, load_mascot
from app.overview.style import accent, css, text_color, tone, with_alpha
from module.localization import tr
from module.logger import log
from module.search import SYNONYMS, SearchIndex, normalize
from .pages.common import Divider, border_color, is_evernight, secondary, shared
from .pages.search_rows import ResultRow

GROUP_LABELS = {"setting": "设置", "task": "任务", "doc": "帮助", "tool": "工具", "page": "页面"}


def result_group(result):
    return "setting" if result.kind == "category" else result.kind


class FilterPill(QWidget):
    clicked = Signal(str)

    def __init__(self, key, parent=None, *, chip=False):
        super().__init__(parent)
        self.key = key
        self._chip = chip
        self._text = ""
        self._selected = False
        self.setFixedHeight(28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def setText(self, text):
        self._text = text
        self.setFixedWidth(self.fontMetrics().horizontalAdvance(text) + 28)
        self.update()

    def setSelected(self, selected):
        self._selected = bool(selected)
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.key)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        if self._selected:
            background, foreground = tone("accent", is_evernight())
            painter.setBrush(background)
            painter.drawRoundedRect(QRectF(self.rect()), 14, 14)
        elif self._chip:
            background = tone("neutral")[0]
            painter.setBrush(background)
            painter.drawRoundedRect(QRectF(self.rect()), 14, 14)
            foreground = text_color()
        else:
            foreground = text_color(secondary=True)
        painter.setPen(foreground)
        painter.setFont(getFont(13, QFont.Weight.DemiBold if self._selected else QFont.Weight.Normal))
        painter.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter, self._text)


class KeyHint(QWidget):
    """底部的按键提示：按键框加说明。"""

    def __init__(self, keys, text, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        for key in keys:
            label = secondary(CaptionLabel(key, self))
            label.setObjectName("key")
            label.setContentsMargins(5, 0, 5, 0)
            layout.addWidget(label)
        layout.addSpacing(2)
        self.textLabel = secondary(CaptionLabel(text, self))
        layout.addWidget(self.textLabel)
        self.restyle()

    def restyle(self):
        color = "rgba(255,255,255,0.18)" if isDarkTheme() else "rgba(0,0,0,0.16)"
        for label in self.findChildren(CaptionLabel, "key"):
            label.setStyleSheet(f"#key {{ border: 1px solid {color}; border-radius: 4px; padding: 0px 2px; }}")


class SearchPanel(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(border_color(), 1))
        painter.setBrush(QColor(43, 43, 43) if isDarkTheme() else QColor(251, 251, 251))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)


class SearchPopup(QWidget):
    """覆盖在主窗口上的搜索面板。Esc 或点面板外关闭。"""

    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.index = shared(window, "searchIndex", lambda: SearchIndex(_config()))
        self.results = []
        self.rows = []
        self.selected = -1
        self.filter = "all"
        self.hide()
        self.panel = SearchPanel(self)
        shadow = QGraphicsDropShadowEffect(self.panel)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 70))
        self.panel.setGraphicsEffect(shadow)
        self.searchIcon = IconWidget(FluentIcon.SEARCH, self.panel)
        self.searchIcon.setFixedSize(20, 20)
        self.input = QLineEdit(self.panel)
        self.input.setFrame(False)
        self.input.setFont(getFont(18))
        self.input.setPlaceholderText(tr("搜索设置、任务、帮助和工具"))
        self.input.installEventFilter(self)
        self.escHint = KeyHint(("Esc",), "", self.panel)
        inputRow = QHBoxLayout()
        inputRow.setContentsMargins(18, 12, 16, 12)
        inputRow.setSpacing(12)
        inputRow.addWidget(self.searchIcon)
        inputRow.addWidget(self.input, 1)
        inputRow.addWidget(self.escHint)
        self.filterRow = QHBoxLayout()
        self.filterRow.setContentsMargins(14, 8, 14, 4)
        self.filterRow.setSpacing(4)
        self.pills = {}
        for key in ("all", *GROUP_LABELS):
            pill = FilterPill(key, self.panel)
            pill.clicked.connect(self.setFilter)
            self.pills[key] = pill
            self.filterRow.addWidget(pill)
        self.filterRow.addStretch(1)
        self.scroll = ScrollArea(self.panel)
        self.scroll.setWidgetResizable(True)
        self.scroll.enableTransparentBackground()
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view = QWidget()
        self.view.setObjectName("view")
        self.scroll.setWidget(self.view)
        self.view.setStyleSheet("#view{background: transparent}")
        self.listLayout = QVBoxLayout(self.view)
        self.listLayout.setContentsMargins(6, 4, 10, 8)
        self.listLayout.setSpacing(0)
        self.empty = QWidget(self.panel)
        self.mascot = QLabel(self.empty)
        self.emptyTitle = StrongBodyLabel(self.empty)
        self.emptyHint = secondary(BodyLabel(self.empty))
        self.emptyHint.setWordWrap(True)
        self.suggestionRow = QHBoxLayout()
        self.suggestionRow.setSpacing(6)
        emptyText = QVBoxLayout()
        emptyText.setSpacing(6)
        emptyText.addStretch(1)
        emptyText.addWidget(self.emptyTitle)
        emptyText.addWidget(self.emptyHint)
        emptyText.addLayout(self.suggestionRow)
        emptyText.addStretch(1)
        emptyLayout = QHBoxLayout(self.empty)
        emptyLayout.setContentsMargins(28, 12, 28, 16)
        emptyLayout.setSpacing(20)
        emptyLayout.addWidget(self.mascot)
        emptyLayout.addLayout(emptyText, 1)
        footer = QHBoxLayout()
        footer.setContentsMargins(16, 8, 16, 10)
        footer.setSpacing(14)
        self.hints = [KeyHint(("↑", "↓"), tr("选择"), self.panel), KeyHint(("Enter",), tr("打开并定位"), self.panel),
                      KeyHint(("Tab",), tr("切换分类"), self.panel)]
        for hint in self.hints:
            footer.addWidget(hint)
        footer.addStretch(1)
        self.synonymLabel = secondary(CaptionLabel(self.panel))
        footer.addWidget(self.synonymLabel)
        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(inputRow)
        layout.addWidget(Divider(self.panel))
        layout.addLayout(self.filterRow)
        layout.addWidget(self.scroll, 1)
        layout.addWidget(self.empty, 1)
        layout.addWidget(Divider(self.panel))
        layout.addLayout(footer)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._query)
        self.input.textChanged.connect(lambda _: self._timer.start())
        window.installEventFilter(self)

    # 打开和关闭
    def open(self, text=None):
        self.setGeometry(self.window_.rect())
        self._place()
        self._restyle()
        if text is not None:
            self.input.setText(text)
        self.show()
        self.raise_()
        self.input.setFocus()
        self.input.selectAll()
        self._query()

    def retranslateUi(self):
        self.input.setPlaceholderText(tr("搜索设置、任务、帮助和工具"))
        for hint, text in zip(self.hints, (tr("选择"), tr("打开并定位"), tr("切换分类"))):
            hint.textLabel.setText(text)
        if self.isVisible():
            self._restyle()
            self._query()

    def close(self):
        self.hide()
        return True

    def _place(self):
        width = min(760, max(420, self.width() - 96))
        height = min(560, max(260, self.height() - 120))
        self.panel.setGeometry((self.width() - width) // 2, 56, width, height)

    def _restyle(self):
        color = css(text_color())
        self.input.setStyleSheet(f"QLineEdit {{ background: transparent; border: none; color: {color}; }}")
        for hint in (*self.hints, self.escHint):
            hint.restyle()
        self.mascot.setPixmap(load_mascot(Mascot.SEARCH, 132, self.devicePixelRatioF(), evernight=is_evernight()))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 110 if isDarkTheme() else 60))

    def mousePressEvent(self, event):
        if not self.panel.geometry().contains(event.position().toPoint()):
            self.close()
            event.accept()
            return
        super().mousePressEvent(event)

    def eventFilter(self, watched, event):
        if watched is self.window_ and event.type() == QEvent.Type.Resize and self.isVisible():
            self.setGeometry(self.window_.rect())
            self._place()
        elif watched is self.input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.close()
                return True
            navigation_keys = (Qt.Key.Key_Down, Qt.Key.Key_Up, Qt.Key.Key_Return, Qt.Key.Key_Enter,
                               Qt.Key.Key_Tab, Qt.Key.Key_Backtab)
            if key in navigation_keys and self._timer.isActive():
                self._timer.stop()
                self._query()
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                self._move(1 if key == Qt.Key.Key_Down else -1)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._activate()
                return True
            if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                self._cycleFilter(-1 if key == Qt.Key.Key_Backtab else 1)
                return True
        return super().eventFilter(watched, event)

    # 查询和显示
    def _query(self):
        text = self.input.text().strip()
        try:
            if text:
                self.results = list(self.index.query(text, limit=40))
            else:
                self.index.prepare()
                self.results = []
        except Exception as exc:
            log.warning(f"全局搜索失败：{type(exc).__name__}: {exc}")
            self.results = []
        available = {result_group(r) for r in self.results}
        if self.filter != "all" and self.filter not in available:
            self.filter = "all"
        self._render(text)

    def _filtered(self):
        if self.filter == "all":
            return self.results
        return [result for result in self.results if result_group(result) == self.filter]

    def _render(self, text):
        for widget in self.rows + [self.listLayout.itemAt(i).widget() for i in range(self.listLayout.count())]:
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        while self.listLayout.count():
            self.listLayout.takeAt(0)
        self.rows = []
        counts = Counter(map(result_group, self.results))
        self.pills["all"].setText(tr("全部") + (f" {len(self.results)}" if self.results else ""))
        for key, name in GROUP_LABELS.items():
            pill = self.pills[key]
            pill.setText(f"{tr(name)} {counts[key]}")
            pill.setVisible(bool(counts[key]))
        for key, pill in self.pills.items():
            pill.setSelected(key == self.filter)
        shown = self._filtered()
        # 每类只出一个标题：类别按其中最相关的一条排序，类内保持相关度顺序，键盘顺序与屏幕一致。
        grouped = {}
        for result in shown:
            grouped.setdefault(result_group(result), []).append(result)
        for key, members in grouped.items():
            header = secondary(CaptionLabel(tr(GROUP_LABELS[key]), self.view))
            header.setContentsMargins(12, 10, 0, 4)
            self.listLayout.addWidget(header)
            for result in members:
                row = ResultRow(result, text, self.view)
                row.clicked.connect(self._open)
                self.rows.append(row)
                self.listLayout.addWidget(row)
        self.listLayout.addStretch(1)
        has_rows = bool(self.rows)
        self.scroll.setVisible(has_rows)
        self.empty.setVisible(not has_rows)
        self.selected = 0 if has_rows else -1
        self._select()
        if not has_rows:
            self._renderEmpty(text)
        self.synonymLabel.setText(self._synonyms(text))

    def _renderEmpty(self, text):
        while self.suggestionRow.count():
            widget = self.suggestionRow.takeAt(0).widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        if text:
            self.emptyTitle.setText(tr("没有找到「{query}」").format(query=text))
            self.emptyHint.setText(tr("换个说法试试，比如用功能的名字，或者下面这些常用词："))
        else:
            self.emptyTitle.setText(tr("想找什么？"))
            self.emptyHint.setText(tr("输入功能、设置或问题里的词。用平时的说法也行，比如「挂机」「体力」「刷本」。"))
        try:
            words = self.index.suggestions()
        except Exception:
            words = ()
        for word in words:
            pill = FilterPill(word, self.empty, chip=True)
            pill.setText(word)
            pill.clicked.connect(lambda w: self.input.setText(w))
            self.suggestionRow.addWidget(pill)
        self.suggestionRow.addStretch(1)

    @staticmethod
    def _synonyms(text):
        terms = set(normalize(text).split())
        for group in SYNONYMS:
            names = [word for word in group if normalize(word) in terms or normalize(tr(word)) in terms]
            if names:
                others = [word for word in group if word not in names]
                return tr("也匹配了：{words}").format(words=tr("、").join(tr(word) for word in others[:4])) if others else ""
        return ""

    def setFilter(self, key):
        self.filter = key
        self._render(self.input.text().strip())
        self.input.setFocus()

    def _cycleFilter(self, step):
        keys = ["all"] + [key for key in GROUP_LABELS if self.pills[key].isVisible()]
        index = keys.index(self.filter) if self.filter in keys else 0
        self.setFilter(keys[(index + step) % len(keys)])

    def _move(self, step):
        if not self.rows:
            return
        self.selected = (self.selected + step) % len(self.rows)
        self._select()

    def _select(self):
        for index, row in enumerate(self.rows):
            row.setSelected(index == self.selected)
        if 0 <= self.selected < len(self.rows):
            self.scroll.ensureWidgetVisible(self.rows[self.selected], 0, 12)

    def _activate(self):
        if 0 <= self.selected < len(self.rows):
            self._open(self.rows[self.selected].result)

    def _open(self, result):
        self.close()
        QTimer.singleShot(0, self.window_, lambda: self.window_.navigate(result.link))


def _config():
    from module.config import cfg
    return cfg
