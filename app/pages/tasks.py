"""任务页的控件：左侧任务列表、页头、领取项目复选框。数据来自 TaskModel。"""
from datetime import datetime

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (Action, BodyLabel, CaptionLabel, CheckBox, DropDownPushButton, FluentIcon, IconWidget,
                            InfoBar, PrimaryPushButton, PrimarySplitPushButton, RoundMenu, ScrollArea,
                            SearchLineEdit, SimpleCardWidget, StrongBodyLabel, SubtitleLabel, isDarkTheme)

from app.overview.style import accent, brand, primary_button_qss, text_color, tone
from app.overview.widgets import ElidedLabel, IconTile, LinkButton, Pill
from module.localization import tr
from module.search import normalize
from .common import STATUS_TONES, bare_switch, icon_of, is_evernight, secondary, style_primary

GROUPS = ("每天", "每周", "按月和其他")
EDITABLE = {"echo_of_war_timestamp", "universe_timestamp"}
RESETTABLE = {"last_run_timestamp", "currencywars_timestamp", "weekly_divergent_timestamp", "fight_timestamp",
              "echo_of_war_timestamp", "universe_timestamp", "divergent_universe_daily_completed_count"}
PROGRESS_LABELS = {
    "last_run_timestamp": "上次完成每日实训",
    "currencywars_timestamp": "上次拿满本周积分",
    "weekly_divergent_timestamp": "上次拿满本周积分",
    "fight_timestamp": "上次完成锄大地",
    "echo_of_war_timestamp": "上次完成历战余响",
    "universe_timestamp": "上次运行模拟宇宙",
    "divergent_universe_daily_completed_count": "差分宇宙今日已完成",
}


def _progress_text(key, value):
    if key.endswith("_count"):
        return tr("{count} 次").format(count=value or 0)
    try:
        moment = datetime.fromtimestamp(float(value or 0))
    except (TypeError, ValueError, OSError, OverflowError):
        moment = None
    if moment is None or moment.year < 2000:
        return tr("从未完成")
    return moment.strftime("%m-%d %H:%M")


class TaskRow(QWidget):
    clicked = Signal(str)
    toggled = Signal(str, bool)

    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.task = task
        self.taskId = task.id
        self._selected = False
        self._hover = False
        self._available = True
        self._overridden = False
        self.setFixedHeight(54)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.iconWidget = IconWidget(icon_of(task.icon), self)
        self.iconWidget.setFixedSize(18, 18)
        self.nameLabel = StrongBodyLabel(tr(task.name), self)
        self.statusLabel = secondary(ElidedLabel(self, size=12))
        self.switch = bare_switch(self)
        self.switch.checkedChanged.connect(lambda on: self.toggled.emit(self.taskId, on))
        column = QVBoxLayout()
        column.setSpacing(0)
        column.addWidget(self.nameLabel)
        column.addWidget(self.statusLabel)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 4, 10, 4)
        layout.setSpacing(12)
        layout.addWidget(self.iconWidget)
        layout.addLayout(column, 1)
        layout.addWidget(self.switch)

    def setState(self, status, enabled, available):
        self._available = available
        detail = next((step.summary for step in status.steps if getattr(step, "summary", "")), "")
        self.statusLabel.setFullText(f"{status.text} · {detail}" if detail and status.kind not in ("disabled", "unsupported") else status.text)
        self.switch.blockSignals(True)
        self.switch.setChecked(bool(enabled))
        self.switch.blockSignals(False)
        self.switch.setEnabled(available)
        self.nameLabel.setEnabled(available)
        self.update()

    def setOverridden(self, overridden):
        """当前账号的独立方案里改过这项任务，和共享方案不同。"""
        if self._overridden != bool(overridden):
            self._overridden = bool(overridden)
            self.setToolTip(tr("这个账号改过，和共享方案不同") if overridden else "")
            self.update()

    def setSelected(self, selected):
        self._selected = bool(selected)
        self.update()

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.taskId)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        c = 255 if isDarkTheme() else 0
        if self._selected or self._hover:
            painter.setBrush(QColor(c, c, c, 15 if self._selected else 8))
            painter.drawRoundedRect(QRectF(self.rect()), 6, 6)
        if self._selected:
            painter.setBrush(accent(is_evernight()))
            painter.drawRoundedRect(QRectF(0, self.height() / 2 - 9, 3, 18), 1.5, 1.5)
        if self._overridden:
            # 名称后的小圆点；名称标签占满一列，圆点跟在文字后面。
            x = self.nameLabel.x() + min(self.nameLabel.width(), self.nameLabel.fontMetrics().horizontalAdvance(self.nameLabel.text())) + 9
            painter.setBrush(brand(is_evernight()))
            painter.drawEllipse(QRectF(x - 3, self.nameLabel.geometry().center().y() - 2.5, 6, 6))


class TaskListPanel(SimpleCardWidget):
    currentChanged = Signal(str)

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self.setBorderRadius(8)
        self.rows = {}
        self.groupHeaders = {}
        self._current = None
        self.filterBox = SearchLineEdit(self)
        self.filterBox.setPlaceholderText(tr("筛选任务"))
        self.filterBox.textChanged.connect(self._filter)
        self.scroll = ScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.enableTransparentBackground()
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view = QWidget()
        self.view.setObjectName("view")
        self.scroll.setWidget(self.view)
        self.view.setStyleSheet("#view{background: transparent}")
        lines = QVBoxLayout(self.view)
        lines.setContentsMargins(0, 0, 4, 0)
        lines.setSpacing(2)
        tasks = self.model.tasks()
        for group in GROUPS:
            members = [task for task in tasks if task.group == group]
            if not members:
                continue
            header = QWidget(self.view)
            title = secondary(CaptionLabel(tr(group), header))
            count = secondary(CaptionLabel(header))
            row = QHBoxLayout(header)
            row.setContentsMargins(12, 10, 12, 2)
            row.addWidget(title)
            row.addStretch(1)
            row.addWidget(count)
            self.groupHeaders[group] = (header, count, members)
            lines.addWidget(header)
            for task in members:
                widget = TaskRow(task, self.view)
                widget.clicked.connect(self.setCurrentEmit)
                widget.toggled.connect(self._toggled)
                self.rows[task.id] = widget
                lines.addWidget(widget)
        lines.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 6, 10)
        layout.setSpacing(6)
        filterRow = QHBoxLayout()
        filterRow.setContentsMargins(0, 0, 4, 0)
        filterRow.addWidget(self.filterBox)
        layout.addLayout(filterRow)
        layout.addWidget(self.scroll, 1)
        self.refresh()

    def refresh(self):
        for task_id, row in self.rows.items():
            try:
                row.setState(self.model.status(task_id), self.model.enabled(task_id), self.model.available(task_id))
                row.setOverridden(self.model.overridden(task_id))
            except Exception:
                continue
        for group, (header, count, members) in self.groupHeaders.items():
            enabled = sum(1 for task in members if self.model.enabled(task.id))
            count.setText(tr("{enabled} / {total} 已开启").format(enabled=enabled, total=len(members)))

    def _toggled(self, task_id, enabled):
        if not self.model.set_enabled(task_id, enabled):
            self.refresh()

    def _filter(self, text):
        query = normalize(text)
        for group, (header, count, members) in self.groupHeaders.items():
            shown = 0
            for task in members:
                row = self.rows[task.id]
                haystack = normalize(" ".join((tr(task.name), task.name, row.statusLabel.fullText())))
                visible = not query or all(term in haystack for term in query.split())
                row.setVisible(visible)
                shown += visible
            header.setVisible(bool(shown))

    def setCurrentEmit(self, task_id):
        if task_id != self._current:
            self.setCurrent(task_id)
            self.currentChanged.emit(task_id)

    def setCurrent(self, task_id):
        self._current = task_id
        for key, row in self.rows.items():
            row.setSelected(key == task_id)
        if task_id in self.rows:
            self.scroll.ensureWidgetVisible(self.rows[task_id], 0, 24)

    def current(self):
        return self._current


class ProgressRow(QWidget):
    def __init__(self, key, model, parent=None):
        super().__init__(parent)
        self.key, self.model = key, model
        self.label = secondary(CaptionLabel(tr(PROGRESS_LABELS.get(key, key)), self))
        self.value = CaptionLabel(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.label)
        layout.addWidget(self.value)
        self.editButton = self.resetButton = None
        if key in EDITABLE:
            self.editButton = LinkButton(tr("修改"), self, size=12)
            self.editButton.clicked.connect(lambda: self.model.edit_progress(self.key))
            layout.addWidget(self.editButton)
        if key in RESETTABLE:
            self.resetButton = LinkButton(tr("重置"), self, size=12)
            self.resetButton.setToolTip(tr("清除记录后，下次运行会重新执行这一项"))
            self.resetButton.clicked.connect(lambda: self.model.reset_progress(self.key))
            layout.addWidget(self.resetButton)
        layout.addStretch(1)

    def setValue(self, value):
        self.value.setText(_progress_text(self.key, value))
        for button in (self.editButton, self.resetButton):
            if button is not None:
                button.setEvernight(is_evernight())


class TaskHeader(SimpleCardWidget):
    def __init__(self, task, model, window, parent=None):
        super().__init__(parent)
        self.task, self.model, self.window_ = task, model, window
        self.setBorderRadius(8)
        self.tile = IconTile(self, size=52, icon_size=26)
        self.titleLabel = SubtitleLabel(tr(task.name), self)
        self.statusPill = Pill(self, dot=True, height=22)
        self.descriptionLabel = secondary(BodyLabel(tr(task.description), self))
        self.descriptionLabel.setWordWrap(True)
        self.joinLabel = BodyLabel(tr("加入完整运行"), self)
        self.joinSwitch = bare_switch(self)
        self.joinSwitch.checkedChanged.connect(self._toggled)
        menu = model.menu(task.id)
        if menu:
            self.runButton = PrimarySplitPushButton(FluentIcon.PLAY, tr("立即运行"), self)
            self.runMenu = RoundMenu(parent=self)
            for action, label in menu:
                self.runMenu.addAction(Action(label, triggered=lambda _=False, a=action: self._run(a)))
            self.runButton.setFlyout(self.runMenu)
        else:
            self.runButton = PrimaryPushButton(FluentIcon.PLAY, tr("立即运行"), self)
        self.runButton.clicked.connect(lambda: self._run(None))
        self.presetButton = None
        presets = model.presets(task.id)
        if presets:
            self.presetButton = DropDownPushButton(FluentIcon.ROBOT, tr("快捷配置"), self)
            presetMenu = RoundMenu(parent=self)
            for key, label in presets:
                presetMenu.addAction(Action(label, triggered=lambda _=False, k=key: self.model.apply_preset(task.id, k)))
            self.presetButton.setMenu(presetMenu)
        self.progressRows = []
        titleRow = QHBoxLayout()
        titleRow.setSpacing(10)
        titleRow.addWidget(self.titleLabel)
        titleRow.addWidget(self.statusPill, 0, Qt.AlignmentFlag.AlignVCenter)
        titleRow.addStretch(1)
        self.textColumn = QVBoxLayout()
        self.textColumn.setSpacing(4)
        self.textColumn.addLayout(titleRow)
        self.textColumn.addWidget(self.descriptionLabel)
        self.progressLayout = QVBoxLayout()
        self.progressLayout.setContentsMargins(0, 4, 0, 0)
        self.progressLayout.setSpacing(2)
        self.textColumn.addLayout(self.progressLayout)
        # 开关和按钮放在一个容器里：宽时在右侧，窄时挪到说明下面，避免页面被撑出视口。
        self.actions = QWidget(self)
        for widget in (self.joinLabel, self.joinSwitch, self.runButton, self.presetButton):
            if widget is not None:
                widget.setParent(self.actions)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(self.joinLabel)
        row.addWidget(self.joinSwitch)
        row.addSpacing(6)
        row.addWidget(self.runButton)
        self.actionsLayout = QVBoxLayout(self.actions)
        self.actionsLayout.setContentsMargins(0, 0, 0, 0)
        self.actionsLayout.setSpacing(8)
        self.actionsLayout.addLayout(row)
        if self.presetButton is not None:
            self.actionsLayout.addWidget(self.presetButton, 0, Qt.AlignmentFlag.AlignRight)
        self.mainLayout = QHBoxLayout(self)
        self.mainLayout.setContentsMargins(20, 16, 20, 16)
        self.mainLayout.setSpacing(16)
        self.mainLayout.addWidget(self.tile, 0, Qt.AlignmentFlag.AlignTop)
        self.mainLayout.addLayout(self.textColumn, 1)
        self.mainLayout.addWidget(self.actions, 0, Qt.AlignmentFlag.AlignTop)
        self._narrow = False
        self.restyle()

    def _wideWidth(self):
        title = self.titleLabel.sizeHint().width() + 10 + self.statusPill.sizeHint().width()
        return 40 + 52 + 16 + max(title, 220) + 16 + self.actions.sizeHint().width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        narrow = event.size().width() < self._wideWidth()
        if narrow == self._narrow:
            return
        self._narrow = narrow
        side = Qt.AlignmentFlag.AlignLeft if narrow else Qt.AlignmentFlag.AlignRight
        if self.presetButton is not None:
            self.actionsLayout.setAlignment(self.presetButton, side)
        if narrow:
            self.mainLayout.removeWidget(self.actions)
            self.actionsLayout.setContentsMargins(0, 8, 0, 0)
            self.textColumn.addWidget(self.actions, 0, Qt.AlignmentFlag.AlignLeft)
        else:
            self.textColumn.removeWidget(self.actions)
            self.actionsLayout.setContentsMargins(0, 0, 0, 0)
            self.mainLayout.addWidget(self.actions, 0, Qt.AlignmentFlag.AlignTop)

    def restyle(self):
        evernight = is_evernight()
        self.tile.setIcon(icon_of(self.task.icon), "accent", evernight=evernight)
        style_primary(self.runButton, evernight)

    def refresh(self):
        status = self.model.status(self.task.id)
        available = self.model.available(self.task.id)
        self.statusPill.setPill(status.text, STATUS_TONES.get(status.kind, "neutral"), evernight=is_evernight())
        self.joinSwitch.blockSignals(True)
        self.joinSwitch.setChecked(self.model.enabled(self.task.id))
        self.joinSwitch.blockSignals(False)
        self.joinSwitch.setEnabled(available)
        self.runButton.setEnabled(self.model.can_run(self.task.id))
        if self.presetButton is not None:
            self.presetButton.setEnabled(available)
        keys = [key for key, _ in status.progress if key in EDITABLE | RESETTABLE]
        if [row.key for row in self.progressRows] != keys:
            for row in self.progressRows:
                row.hide()
                row.deleteLater()
            self.progressRows = [ProgressRow(key, self.model, self) for key in keys]
            for row in self.progressRows:
                self.progressLayout.addWidget(row)
        values = dict(status.progress)
        for row in self.progressRows:
            row.setValue(values.get(row.key))

    def _toggled(self, enabled):
        if not self.model.set_enabled(self.task.id, enabled):
            self.refresh()

    def _run(self, action):
        if not self.model.run(self.task.id, action):
            InfoBar.warning(tr("现在无法运行"), tr("当前运行方式不支持这项任务，或者已有任务正在运行"),
                            duration=3000, parent=self.window_)


class ChecksCard(SimpleCardWidget):
    """「领取奖励」的子项：一组复选框。"""

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self.setBorderRadius(6)
        self.boxes = {}
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(18, 14, 18, 14)
        self.grid.setHorizontalSpacing(24)
        self.grid.setVerticalSpacing(10)
        self.refresh()

    def refresh(self):
        items = self.model.reward_items()
        if [key for key, _, _ in items] != list(self.boxes):
            for box in self.boxes.values():
                self.grid.removeWidget(box)
                box.hide()
                box.deleteLater()
            self.boxes = {}
            for index, (key, name, _) in enumerate(items):
                box = CheckBox(name, self)
                box.stateChanged.connect(lambda _=0, k=key: self._toggled(k))
                self.boxes[key] = box
                self.grid.addWidget(box, index // 4, index % 4)
        for key, _, checked in items:
            box = self.boxes[key]
            box.blockSignals(True)
            box.setChecked(checked)
            box.blockSignals(False)

    def _toggled(self, key):
        if not self.model.set_reward(key, self.boxes[key].isChecked()):
            self.refresh()
