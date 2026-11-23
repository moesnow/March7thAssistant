"""明细表：按星级、名称、时间筛选，可以只看当前卡池，也可以看全部卡池。"""
from datetime import date, timedelta

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QAbstractItemView, QHBoxLayout, QHeaderView, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, CheckBox, ComboBox, FluentIcon as FIF, SearchLineEdit, TableItemDelegate,
                            TableView, TransparentPushButton)

from app.common.design_tokens import PAGE_MARGIN
from app.content.gacha_model import Column, GachaFilterProxy, GachaTableModel, Role
from app.overview.widgets import ElidedLabel
from app.pages.common import secondary
from module.localization import tr

from . import style
from .chips import Chip

PERIODS = (None, 30, 90, 365)
WIDTHS = {Column.TIME: 176, Column.TYPE: 84, Column.STARS: 104, Column.POOL: 196, Column.PITY: 150}


class RecordDelegate(TableItemDelegate):
    """星级画成星号；五星、四星的名称和星号用稀有度颜色，旁边总有星号，不单靠颜色区分。"""

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        stars = index.data(Role.STARS)
        column = index.column()
        if column == Column.STARS and isinstance(stars, int):
            option.text = "★" * stars
        color = style.rarity(stars)
        if color is not None and column in (Column.NAME, Column.STARS):
            option.palette.setColor(QPalette.ColorRole.Text, color)
            option.palette.setColor(QPalette.ColorRole.HighlightedText, color)
        if stars == 5 and column in (Column.NAME, Column.PITY):
            option.font = style.strong(13)


class DetailView(QWidget):
    back = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pools = {}
        self._pool = None
        self._total = 0
        self.model = GachaTableModel(parent=self)
        self.proxy = GachaFilterProxy(self.model, self)
        self.backButton = TransparentPushButton(FIF.LEFT_ARROW, "", self)
        self.backButton.clicked.connect(self.back)
        self.starChips = {}
        for stars in (5, 4, 3):
            chip = Chip(parent=self, soft=True)
            chip.setChecked(True)
            chip.toggled.connect(self._applyFilters)
            self.starChips[stars] = chip
        self.searchBox = SearchLineEdit(self)
        self.searchBox.textChanged.connect(self._applyFilters)
        self.periodBox = ComboBox(self)
        self.periodBox.currentIndexChanged.connect(self._applyFilters)
        self.allPools = CheckBox(self)
        self.allPools.toggled.connect(self._fillRows)
        self.countLabel = secondary(ElidedLabel(self, size=13))
        self.countLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table = TableView(self)
        self.table.delegate = RecordDelegate(self.table)
        self.table.setItemDelegate(self.table.delegate)
        self.table.setModel(self.proxy)
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(8)
        self.table.setWordWrap(False)
        self.table.verticalHeader().hide()
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(Column.NAME, QHeaderView.ResizeMode.Stretch)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for column, width in WIDTHS.items():
            self.table.setColumnWidth(column, width)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(Column.TIME, Qt.SortOrder.DescendingOrder)
        self.emptyLabel = secondary(BodyLabel(self.table.viewport()))
        self.emptyLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.emptyLabel.hide()
        self.table.viewport().installEventFilter(self)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        filters.addWidget(self.backButton)
        filters.addSpacing(8)
        for chip in self.starChips.values():
            filters.addWidget(chip)
        filters.addSpacing(8)
        filters.addWidget(self.searchBox)
        filters.addWidget(self.periodBox)
        filters.addSpacing(4)
        filters.addWidget(self.allPools)
        filters.addStretch(1)
        filters.addWidget(self.countLabel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(PAGE_MARGIN, 2, PAGE_MARGIN, 20)
        layout.setSpacing(12)
        layout.addLayout(filters)
        layout.addWidget(self.table, 1)
        self.retranslateUi()

    def retranslateUi(self):
        self.backButton.setText(tr("返回统计"))
        for stars, text in ((5, tr("五星")), (4, tr("四星")), (3, tr("三星"))):
            self.starChips[stars].setLabel(text)
        self.searchBox.setPlaceholderText(tr("搜索名称"))
        # 按提示文字定宽：右侧有搜索和清除两个按钮。
        hint = self.searchBox.fontMetrics().horizontalAdvance(self.searchBox.placeholderText())
        self.searchBox.setFixedWidth(min(280, max(180, hint + 110)))
        index = max(0, self.periodBox.currentIndex())
        self.periodBox.blockSignals(True)
        self.periodBox.clear()
        self.periodBox.addItems([tr("全部时间"), tr("最近 30 天"), tr("最近 90 天"), tr("最近一年")])
        self.periodBox.setCurrentIndex(index)
        self.periodBox.blockSignals(False)
        self.allPools.setText(tr("全部卡池"))
        self.emptyLabel.setText(tr("没有符合条件的记录"))
        self.model.headerDataChanged.emit(Qt.Orientation.Horizontal, 0, len(Column) - 1)
        self._applyFilters()

    def setData(self, pools, pool_id):
        changed = pools is not self._pools or pool_id != self._pool
        self._pools, self._pool = pools, pool_id
        if changed:
            self._fillRows()

    def _fillRows(self, *args):
        show_all = self.allPools.isChecked()
        if show_all:
            rows = [row for stats in self._pools.values() for row in stats.details]
        else:
            stats = self._pools.get(self._pool)
            rows = stats.details if stats is not None else ()
        self._total = len(rows)
        self.model.set_rows(rows)
        self.table.setColumnHidden(Column.POOL, not show_all)
        self._applyFilters()

    def _applyFilters(self, *args):
        stars = {key for key, chip in self.starChips.items() if chip.isChecked()}
        index = self.periodBox.currentIndex()
        days = PERIODS[index] if 0 <= index < len(PERIODS) else None
        end = date.today() if days else None
        start = end - timedelta(days=days - 1) if days else None
        count = self.proxy.set_filters(stars=None if len(stars) == len(self.starChips) else stars,
                                       keyword=self.searchBox.text().strip(), start=start, end=end)
        if count == self._total:
            text = tr("共 {count} 条").format(count=style.number(count))
        else:
            text = tr("筛选出 {count} 条，共 {total} 条").format(count=style.number(count), total=style.number(self._total))
        self.countLabel.setFullText(text)
        self.emptyLabel.setVisible(count == 0)

    def eventFilter(self, watched, event):
        if watched is self.table.viewport() and event.type() == QEvent.Type.Resize:
            self.emptyLabel.setGeometry(watched.rect())
        return super().eventFilter(watched, event)

    def restyle(self):
        for chip in self.starChips.values():
            chip.update()
        self.table.viewport().update()
