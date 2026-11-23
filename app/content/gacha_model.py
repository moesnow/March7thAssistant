"""QTableView adapters for one pool or a combination of pools."""
from enum import IntEnum

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt

from module.gacha.filters import DetailFilter, newest_first
from module.gacha.pools import POOLS
from module.localization import tr


class Column(IntEnum):
    TIME, NAME, TYPE, STARS, POOL, PITY = range(6)


class Role(IntEnum):
    STARS = Qt.ItemDataRole.UserRole + 1
    PITY = STARS + 1
    TIME = PITY + 1
    POOL = TIME + 1
    NUMBER = POOL + 1
    ID = NUMBER + 1
    SORT = ID + 1


_HEADERS = ("时间", "名称", "类型", "星级", "卡池", "第几抽（保底内）")


class GachaTableModel(QAbstractTableModel):
    def __init__(self, rows=(), parent=None):
        super().__init__(parent)
        self.rows = newest_first(rows)

    def set_rows(self, rows):
        ordered = newest_first(rows)
        self.beginResetModel()
        self.rows = ordered
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(Column)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(_HEADERS):
                return tr(_HEADERS[section])
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        if role == Role.STARS:
            return row.stars
        if role == Role.PITY:
            return row.pity
        if role == Role.TIME:
            return row.time
        if role == Role.POOL:
            return row.pool_id
        if role == Role.NUMBER:
            return row.number
        if role == Role.ID:
            return row.id
        if role in (Qt.ItemDataRole.DisplayRole, Role.SORT):
            col = index.column()
            if col == Column.POOL:
                return POOLS[row.pool_id].label
            return (row.time, row.name, row.item_type, row.stars, None, row.pity)[col]
        return None


class GachaFilterProxy(QSortFilterProxyModel):
    def __init__(self, source, parent=None):
        super().__init__(parent)
        self.rule = DetailFilter.make()
        self.setSortRole(Role.SORT)
        self.setSourceModel(source)

    def set_filters(self, *, stars=None, keyword="", start=None, end=None):
        rule = DetailFilter.make(stars, keyword, start, end)
        if rule != self.rule:
            self.beginFilterChange()
            self.rule = rule
            self.endFilterChange(QSortFilterProxyModel.Direction.Rows)
        return self.rowCount()

    def filterAcceptsRow(self, row, parent):
        return self.rule.accepts(self.sourceModel().rows[row])
