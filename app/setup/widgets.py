"""首次配置向导用的控件：大选项、任务格、设置行、说明列表和候选路径。"""
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QFontMetrics, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QPushButton, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CaptionLabel, ComboBox, SimpleCardWidget, StrongBodyLabel, isDarkTheme, setFont

from app.overview.style import accent, with_alpha
from app.overview.widgets import ElidedLabel, IconTile
from app.pages import style
from app.pages.common import Divider, bare_switch, border_color, icon_of, is_evernight, secondary, surface_color
from app.pages.run_mode import ChoiceCard


def focus_ring(painter, rect, radius):
    painter.setPen(QPen(style.primary(), 1.6))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(rect.adjusted(2.5, 2.5, -2.5, -2.5), radius - 2, radius - 2)


def paint_choice(painter, rect, selected, hover, radius=8):
    """选中时浅强调色底加描边，和运行方式的大卡片一致。"""
    color = accent(is_evernight())
    if selected:
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        gradient.setColorAt(0, with_alpha(color, 0.16 if isDarkTheme() else 0.09))
        gradient.setColorAt(1, surface_color(hover))
        painter.setBrush(gradient)
        painter.setPen(QPen(with_alpha(color, 0.5), 1))
    else:
        painter.setBrush(surface_color(hover))
        painter.setPen(QPen(border_color(), 1))
    painter.drawRoundedRect(rect, radius, radius)


class Choice(ChoiceCard):
    """运行方式那样的三选一大卡片，可以用 Tab 和空格选。"""

    def __init__(self, option, parent=None):
        super().__init__(option, parent)
        self.setAccessibleName(option.name)
        if option.available:
            self.setFocusPolicy(Qt.FocusPolicy.TabFocus)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space and self.option.available:
            self.clicked.emit(self.option.value)
        else:
            super().keyPressEvent(event)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.hasFocus():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            focus_ring(painter, QRectF(self.rect()), 8)


class ElidedComboBox(ComboBox):
    """文字放不下时省略，完整文字放进提示。"""

    def setText(self, text):
        self._full = text
        self._elide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()

    def _elide(self):
        full = getattr(self, "_full", "")
        shown = self.fontMetrics().elidedText(full, Qt.TextElideMode.ElideRight, max(0, self.width() - 42))
        QPushButton.setText(self, shown)
        self.setToolTip(full if shown != full else "")


class TaskTile(QWidget):
    """一项任务：图标、名称、一句说明和开关，点哪里都能切换。"""
    toggled = Signal(str, bool)
    HEIGHT = 54

    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.taskId = task.id
        self._icon = icon_of(task.icon)
        self._hover = False
        self.setFixedHeight(self.HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tile = IconTile(self, size=32, icon_size=18)
        self.nameLabel = StrongBodyLabel(task.name, self)
        self.descriptionLabel = secondary(ElidedLabel(self, size=12))
        self.descriptionLabel.setFullText(task.description)
        self.switch = bare_switch(self)
        self.switch.setAccessibleName(task.name)
        self.switch.checkedChanged.connect(self._changed)
        texts = QVBoxLayout()
        texts.setContentsMargins(0, 0, 0, 0)
        texts.setSpacing(1)
        texts.addStretch(1)
        texts.addWidget(self.nameLabel)
        texts.addWidget(self.descriptionLabel)
        texts.addStretch(1)
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(12, 0, 12, 0)
        self.row.setSpacing(12)
        self.row.addWidget(self.tile)
        self.row.addLayout(texts, 1)
        self.row.addWidget(self.switch)
        self.restyle()

    def isChecked(self):
        return self.switch.isChecked()

    def setChecked(self, on):
        self.switch.blockSignals(True)
        self.switch.setChecked(bool(on))
        self.switch.blockSignals(False)
        self.restyle()

    def _changed(self, on):
        self.restyle()
        self.toggled.emit(self.taskId, on)

    def restyle(self):
        self.tile.setIcon(self._icon, "accent" if self.isChecked() else "neutral", evernight=is_evernight())
        self.update()

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.switch.setChecked(not self.switch.isChecked())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        paint_choice(painter, QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), self.isChecked(), self._hover)


class PowerTile(TaskTile):
    """清体力：右边就地选副本类型和副本。"""
    instanceChanged = Signal()
    HEIGHT = 60

    def __init__(self, task, parent=None):
        super().__init__(task, parent)
        self.typeCombo = ElidedComboBox(self)
        self.typeCombo.setFixedWidth(140)
        self.nameCombo = ElidedComboBox(self)
        self.nameCombo.setFixedWidth(224)
        for combo in (self.typeCombo, self.nameCombo):
            combo.setMaxVisibleItems(9)
            combo.setCursor(Qt.CursorShape.ArrowCursor)
        self.row.insertWidget(2, self.typeCombo)
        self.row.insertWidget(3, self.nameCombo)
        self._types = ()
        self._names = {}
        self._description = task.description
        self.typeCombo.currentIndexChanged.connect(self._typeChanged)
        self.nameCombo.currentIndexChanged.connect(self._nameChanged)

    def setInstances(self, types, current, names):
        """types：可选的副本类型；current：(类型, 名称)；names：每种类型现在选的副本。"""
        self._types = types
        self._names = dict(names)
        kind, name = current
        self._names[kind] = name
        self.typeCombo.blockSignals(True)
        self.typeCombo.clear()
        for item in types:
            self.typeCombo.addItem(item.text, userData=item.value)
        self.typeCombo.setCurrentIndex(max(0, self.typeCombo.findData(kind)))
        self.typeCombo.blockSignals(False)
        self._fillNames()

    def instance(self):
        return self.typeCombo.currentData(), self.nameCombo.currentData()

    def setNote(self, note):
        """体力计划、培养目标已启用时副本选择不生效。"""
        for combo in (self.typeCombo, self.nameCombo):
            combo.setVisible(not note)
        self.descriptionLabel.setFullText(note or self._description)

    def _fillNames(self):
        kind = self.typeCombo.currentData()
        items = next((item.items for item in self._types if item.value == kind), ())
        self.nameCombo.blockSignals(True)
        self.nameCombo.clear()
        for item in items:
            self.nameCombo.addItem(f"{item.text} · {item.info}" if item.info else item.text, userData=item.value)
        index = self.nameCombo.findData(self._names.get(kind))
        self.nameCombo.setCurrentIndex(max(0, index))
        self.nameCombo.blockSignals(False)

    def _typeChanged(self, _index):
        self._fillNames()
        self.instanceChanged.emit()

    def _nameChanged(self, _index):
        self._names[self.typeCombo.currentData()] = self.nameCombo.currentData()
        self.instanceChanged.emit()


class FieldRow(QWidget):
    """标题、说明在左，控件在右的一行。"""

    def __init__(self, title, description="", control=None, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(56)
        self.titleLabel = BodyLabel(title, self)
        self.descriptionLabel = secondary(CaptionLabel(description, self))
        self.descriptionLabel.setWordWrap(True)
        self.descriptionLabel.setVisible(bool(description))
        texts = QVBoxLayout()
        texts.setContentsMargins(0, 0, 0, 0)
        texts.setSpacing(1)
        texts.addWidget(self.titleLabel)
        texts.addWidget(self.descriptionLabel)
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(16, 8, 16, 8)
        self.row.setSpacing(16)
        self.row.addLayout(texts, 1)
        if control is not None:
            self.addControl(control)

    def addControl(self, control):
        self.row.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)

    def setDescription(self, text):
        self.descriptionLabel.setText(text)
        self.descriptionLabel.setVisible(bool(text))


class Group(SimpleCardWidget):
    """几行设置放在一张卡片里，中间用细线隔开；隐藏的行连同细线一起隐藏。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBorderRadius(8)
        self.column = QVBoxLayout(self)
        self.column.setContentsMargins(0, 2, 0, 2)
        self.column.setSpacing(0)
        self._rows = []

    def addRow(self, row):
        line = Divider(self, inset=16)
        line.setVisible(bool(self._rows))
        self._rows.append((line, row))
        self.column.addWidget(line)
        self.column.addWidget(row)
        return row

    def setRowVisible(self, row, visible):
        row.setProperty("m7aShown", bool(visible))
        first = True
        for line, item in self._rows:
            shown = item.property("m7aShown") is not False
            item.setVisible(shown)
            line.setVisible(shown and not first)
            if shown:
                first = False
        self.setVisible(not first)


class Glyph(QWidget):
    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(16, 19)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = style.status_line({"check": "success", "alert": "warning"}.get(self.kind, "accent"))
        style.glyph(painter, self.kind, QRectF(1, 3, 14, 14), color)


class Notes(QWidget):
    """几条说明，前面带勾、感叹号或圆点。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.column = QVBoxLayout(self)
        self.column.setContentsMargins(4, 0, 4, 0)
        self.column.setSpacing(8)
        self._rows = []

    def setNotes(self, notes):
        for row in self._rows:
            self.column.removeWidget(row)
            row.hide()
            row.deleteLater()
        self._rows = []
        for kind, text in notes:
            row = QWidget(self)
            label = BodyLabel(text, row)
            setFont(label, 13)
            label.setWordWrap(True)
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(10)
            layout.addWidget(Glyph(kind, row), 0, Qt.AlignmentFlag.AlignTop)
            layout.addWidget(label, 1)
            self.column.addWidget(row)
            row.show()
            self._rows.append(row)

    def texts(self):
        return [row.findChild(BodyLabel).text() for row in self._rows]


class CandidateRow(QAbstractButton):
    """一个找到的游戏路径。"""
    HEIGHT = 58

    def __init__(self, candidate, parent=None):
        super().__init__(parent)
        self.candidate = candidate
        self._hover = False
        self.setCheckable(True)
        self.setFixedHeight(self.HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setAccessibleName(candidate.path)
        self.setToolTip(candidate.path)

    def sizeHint(self):
        return QSize(320, self.HEIGHT)

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        paint_choice(painter, rect, self.isChecked(), self._hover)
        center = QPointF(rect.left() + 22, rect.center().y())
        if self.isChecked():
            fill, inner = style.solid()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawEllipse(center, 9, 9)
            painter.setBrush(inner)
            painter.drawEllipse(center, 3.6, 3.6)
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(style.muted(), 1.2))
            painter.drawEllipse(center, 8.5, 8.5)
        left, width = rect.left() + 44, rect.width() - 60
        path_font = style.font(14)
        painter.setFont(path_font)
        painter.setPen(style.primary())
        shown = QFontMetrics(path_font).elidedText(self.candidate.path, Qt.TextElideMode.ElideMiddle, int(width))
        painter.drawText(QRectF(left, 9, width, 20), Qt.AlignmentFlag.AlignVCenter, shown)
        painter.setFont(style.font(12))
        painter.setPen(style.muted())
        detail = " · ".join(filter(None, (self.candidate.source_text, self.candidate.server_text)))
        painter.drawText(QRectF(left, 30, width, 18), Qt.AlignmentFlag.AlignVCenter, detail)
        if self.hasFocus():
            focus_ring(painter, rect, 8)
