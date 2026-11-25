"""总览页的卡片：四张状态卡、完整运行清单、上次运行、快捷启动、建议检查。"""
from datetime import timedelta
import math
import sys

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import Action, CaptionLabel, DropDownPushButton, FluentIcon as FIF, IconWidget, InfoBarIcon, \
    PushButton, RoundMenu, SimpleCardWidget, StrongBodyLabel, BodyLabel, getFont, isDarkTheme, setFont

from module.localization import tr
from module.overview.labels import result_label, trigger_label
from module.overview.readings import POWER_CAP, SECONDS_PER_POWER, next_power_in, power_now

from .style import CHECK_TONES, PLAN_TONES, RESULT_TONES, accent, brand, format_duration, format_when, resolve_icon, \
    tone, with_alpha
from .widgets import ElidedLabel, IconTile, LinkButton, MeterBar, Pill, RecoveryBadge

SECONDARY = (QColor(96, 96, 96), QColor(206, 206, 206))
CHEVRON = FIF.CHEVRON_RIGHT_MED.colored(QColor(138, 138, 138), QColor(160, 160, 160))
FOLDED = ("disabled", "unsupported")


def secondary(label):
    label.setTextColor(*SECONDARY)
    return label


def card_title(parent):
    label = StrongBodyLabel(parent)
    setFont(label, 15, QFont.Weight.DemiBold)
    return label


class OverviewCard(SimpleCardWidget):
    linkActivated = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBorderRadius(8)
        self.vBox = QVBoxLayout(self)
        self.vBox.setContentsMargins(16, 14, 16, 14)
        self.vBox.setSpacing(0)

    def _emitLink(self, link):
        if link:
            self.linkActivated.emit(link)


class StatCard(OverviewCard):
    """开拓力、每日实训、本周周常、下次定时运行。"""

    def __init__(self, icon, parent=None):
        super().__init__(parent)
        self._target = None
        header = QHBoxLayout()
        header.setSpacing(6)
        self.iconWidget = IconWidget(icon, self)
        self.iconWidget.setFixedSize(16, 16)
        self.titleLabel = secondary(CaptionLabel(self))
        setFont(self.titleLabel, 13)
        header.addWidget(self.iconWidget)
        header.addWidget(self.titleLabel)
        header.addStretch(1)
        self.valueRow = QHBoxLayout()
        self.valueRow.setSpacing(6)
        self.valueLabel = StrongBodyLabel(self)
        setFont(self.valueLabel, 26, QFont.Weight.DemiBold)
        self.unitLabel = secondary(CaptionLabel(self))
        setFont(self.unitLabel, 13)
        self.unitLabel.setContentsMargins(0, 0, 0, 5)
        self.valueRow.addWidget(self.valueLabel, 0, Qt.AlignmentFlag.AlignBottom)
        self.valueRow.addWidget(self.unitLabel, 0, Qt.AlignmentFlag.AlignBottom)
        self.valueRow.addStretch(1)
        self.meter = MeterBar(self)
        note = QHBoxLayout()
        note.setSpacing(4)
        self.noteLabel = secondary(ElidedLabel(self, size=12))
        self.noteLink = LinkButton("", self, size=12)
        self.noteLink.hide()
        self.noteLink.clicked.connect(lambda: self._emitLink(self._target))
        note.addWidget(self.noteLabel)
        note.addWidget(self.noteLink)
        note.addStretch(1)
        self.vBox.addLayout(header)
        self.vBox.addSpacing(4)
        self.vBox.addLayout(self.valueRow)
        self.vBox.addSpacing(8)
        self.vBox.addWidget(self.meter)
        self.vBox.addSpacing(10)
        self.vBox.addLayout(note)

    def setTitle(self, text):
        self.titleLabel.setText(text)

    def setValue(self, value, unit=""):
        self.valueLabel.setText(value)
        self.unitLabel.setText(unit)
        self.unitLabel.setVisible(bool(unit))

    def setNote(self, text, link_text="", target=None, *, evernight=False):
        self.noteLabel.setFullText(text)
        self._target = target
        self.noteLink.setText(link_text)
        self.noteLink.setEvernight(evernight)
        self.noteLink.setVisible(bool(link_text and target))


class PowerCard(StatCard):
    """开拓力：从上次读数起按时间估算，右边是恢复下一点的倒计时。"""

    def __init__(self, icon, parent=None):
        super().__init__(icon, parent)
        self._reading = None
        self._now = None
        self._evernight = False
        self._elapsed = QElapsedTimer()
        self._timer = QTimer(self, singleShot=True)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._refresh)
        self.badge = RecoveryBadge(self)
        self.badge.hide()
        self.valueRow.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignVCenter)

    def setReading(self, reading, now, *, unavailable=False, evernight=False):
        known = not unavailable and reading is not None and reading.value is not None
        self._reading = reading if known else None
        self._now, self._evernight = now, evernight
        self._elapsed.start()
        self.setToolTip(tr("按上次记录的数值和每 6 分钟恢复 1 点估算，可能和游戏里差几点") if known else "")
        self._refresh()
        if not known:
            self.setValue("—", f"/ {getattr(reading, 'maximum', POWER_CAP)}")
            self.meter.setFraction(0, brand(evernight))
            self.setNote(tr("暂时读不到开拓力") if unavailable else tr("运行一次清体力后显示"))

    def _refresh(self):
        reading = self._reading
        self._timer.stop()
        self.badge.setVisible(reading is not None)
        if reading is None:
            return
        now = self._now + timedelta(milliseconds=self._elapsed.elapsed())
        value = power_now(reading, now)
        left = next_power_in(reading, now)
        self.setValue(str(value), f"/ {reading.maximum}")
        self.meter.setFraction(value / max(1, reading.maximum), brand(self._evernight))
        note = tr("{time} 时为 {value}").format(time=format_when(reading.read_at, now), value=reading.value)
        if reading.value < reading.maximum:
            note = tr("约{time} 回满").format(time=format_when(reading.full_at, now)) + " · " + note
        self.setNote(note)
        if left is None:
            self.badge.setFull(tr("已回满"), evernight=self._evernight)
            return
        self.badge.setCountdown(math.ceil(left), 1 - left / SECONDS_PER_POWER, evernight=self._evernight)
        if self.isVisible():
            self._timer.start(int(left * 1000) % 1000 + 10)  # 正好在跳秒之后

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()


class PlanRow(QWidget):
    clicked = Signal(str)

    def __init__(self, item, name_width, *, evernight=False, last=False, parent=None):
        super().__init__(parent)
        self.item = item
        self._hover = False
        self._last = last
        self._evernight = evernight
        self.setFixedHeight(40)
        if item.link:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        kind = PLAN_TONES.get(item.status, "neutral")
        muted = item.status in ("disabled", "unsupported")
        self.tile = IconTile(self)
        self.tile.setIcon(resolve_icon(item.icon), "accent" if kind == "accent" else "neutral", evernight=evernight)
        self.nameLabel = StrongBodyLabel(item.name, self)
        setFont(self.nameLabel, 14, QFont.Weight.DemiBold)
        self.nameLabel.setFixedWidth(name_width)
        if muted:
            secondary(self.nameLabel)
        self.summaryLabel = secondary(ElidedLabel(self, size=13))
        self.summaryLabel.setFullText(item.summary)
        self.pill = Pill(self, height=22)
        self.pill.setPill(item.status_text, kind, evernight=evernight)
        self.chevron = IconWidget(CHEVRON, self)
        self.chevron.setFixedSize(10, 10)
        self.chevron.setVisible(bool(item.link))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(12)
        layout.addWidget(self.tile)
        layout.addWidget(self.nameLabel)
        layout.addWidget(self.summaryLabel, 1)
        layout.addWidget(self.pill)
        layout.addWidget(self.chevron)

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            if self.item.link:
                self.clicked.emit(self.item.link)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        rect = QRectF(self.rect()).adjusted(4, 2, -4, -2)
        if self.item.status == "running":
            painter.setBrush(with_alpha(accent(self._evernight), 0.08))
            painter.drawRoundedRect(rect, 6, 6)
        if self._hover and self.item.link:
            painter.setBrush(QColor(255, 255, 255, 12) if isDarkTheme() else QColor(0, 0, 0, 9))
            painter.drawRoundedRect(rect, 6, 6)
        if not self._last:
            painter.setPen(QColor(255, 255, 255, 16) if isDarkTheme() else QColor(0, 0, 0, 13))
            painter.drawLine(QPointF(12, self.height() - 0.5), QPointF(self.width() - 12, self.height() - 0.5))


class PlanCard(OverviewCard):
    """完整运行将执行：按实际顺序列出每一项。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.vBox.setContentsMargins(4, 14, 4, 8)
        header = QHBoxLayout()
        header.setContentsMargins(12, 0, 12, 0)
        header.setSpacing(10)
        self.titleLabel = card_title(self)
        self.subtitleLabel = secondary(ElidedLabel(self, size=12))
        header.addWidget(self.titleLabel)
        header.addWidget(self.subtitleLabel, 1)
        self.rowsLayout = QVBoxLayout()
        self.rowsLayout.setSpacing(0)
        self.emptyLabel = secondary(CaptionLabel(self))
        self.emptyLabel.setContentsMargins(12, 8, 12, 8)
        self.emptyLabel.hide()
        self.foldLink = LinkButton("", self, size=12)
        self.foldLink.clicked.connect(self._toggleFolded)
        footer = QHBoxLayout()
        footer.setContentsMargins(12, 6, 12, 2)
        footer.addWidget(self.foldLink)
        footer.addStretch(1)
        self.vBox.addLayout(header)
        self.vBox.addSpacing(8)
        self.vBox.addLayout(self.rowsLayout)
        self.vBox.addWidget(self.emptyLabel)
        self.vBox.addLayout(footer)
        self.rows = []
        self._items = ()
        self._unavailable = False
        self._evernight = False
        self._showFolded = False
        self.retranslateUi()

    def retranslateUi(self):
        self.titleLabel.setText(tr("完整运行将执行"))
        self.subtitleLabel.setFullText(tr("按当前设置，已完成和未开启的会自动跳过"))
        self._rebuild()

    def setItems(self, items, *, unavailable=False, evernight=False):
        self._items = tuple(items or ())
        self._unavailable = unavailable
        self._evernight = evernight
        self._rebuild()

    def _toggleFolded(self):
        self._showFolded = not self._showFolded
        self._rebuild()

    def _rebuild(self):
        for row in self.rows:
            self.rowsLayout.removeWidget(row)
            row.hide()
            row.deleteLater()
        self.rows = []
        items = self._items
        folded = [item for item in items if item.status in FOLDED]
        shown = [item for item in items if self._showFolded or item.status not in FOLDED]
        metrics = QFontMetrics(getFont(14, QFont.Weight.DemiBold))
        name_width = max([metrics.horizontalAdvance(item.name) for item in items] or [0]) + 6
        name_width = max(72, min(name_width, 168))
        for index, item in enumerate(shown):
            row = PlanRow(item, name_width, evernight=self._evernight, last=index == len(shown) - 1, parent=self)
            row.clicked.connect(self._emitLink)
            self.rowsLayout.addWidget(row)
            self.rows.append(row)
        self.emptyLabel.setText(tr("暂时读不到完整运行清单") if self._unavailable else tr("完整运行没有要执行的项目"))
        self.emptyLabel.setVisible(not shown)
        self.foldLink.setEvernight(self._evernight)
        if self._showFolded:
            self.foldLink.setText(tr("收起未开启的项目"))
        else:
            self.foldLink.setText(tr("显示未开启的 {count} 项").format(count=len(folded)))
        self.foldLink.setVisible(bool(folded))


STEP_GLYPHS = {
    "success": (FIF.ACCEPT, "success"), "failed": (FIF.CLOSE, "error"), "running": (FIF.SYNC, "accent"),
    "skipped": (FIF.REMOVE, "neutral"), "interrupted": (FIF.PAUSE, "warning"),
}


class StepRow(QWidget):
    def __init__(self, step, *, evernight=False, parent=None):
        super().__init__(parent)
        icon, kind = STEP_GLYPHS.get(step.status, (FIF.REMOVE, "neutral"))
        light, dark = self._colors(kind, evernight)
        self.glyph = IconWidget(icon.colored(light, dark), self)
        self.glyph.setFixedSize(12, 12)
        self.nameLabel = ElidedLabel(self, size=13)
        self.nameLabel.setFullText(step.name)
        self.timeLabel = secondary(CaptionLabel(format_duration(step.seconds), self))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.glyph)
        layout.addWidget(self.nameLabel, 1)
        layout.addWidget(self.timeLabel)

    @staticmethod
    def _colors(kind, evernight):
        from .style import LIGHT, DARK
        if kind == "accent":
            return QColor(LIGHT.evernight_accent if evernight else LIGHT.deep_pink), \
                QColor(DARK.evernight_accent if evernight else DARK.deep_pink)
        if kind in ("success", "error", "warning"):
            return QColor(getattr(LIGHT, kind)), QColor(getattr(DARK, kind))
        return QColor(138, 138, 138), QColor(160, 160, 160)


class LastRunCard(OverviewCard):
    MAX_STEPS = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self._link = None
        self._steps = []
        header = QHBoxLayout()
        header.setSpacing(8)
        self.titleLabel = card_title(self)
        self.resultPill = Pill(self, height=22)
        self.logLink = LinkButton("", self, size=13)
        self.logLink.clicked.connect(lambda: self._emitLink(self._link))
        header.addWidget(self.titleLabel)
        header.addWidget(self.resultPill)
        header.addStretch(1)
        header.addWidget(self.logLink)
        self.metaLabel = secondary(ElidedLabel(self, size=12))
        self.stepsLayout = QVBoxLayout()
        self.stepsLayout.setSpacing(4)
        self.moreLabel = secondary(CaptionLabel(self))
        self.errorLabel = ElidedLabel(self, size=12)
        self.errorLabel.setContentsMargins(0, 6, 0, 0)
        self.vBox.addLayout(header)
        self.vBox.addSpacing(4)
        self.vBox.addWidget(self.metaLabel)
        self.vBox.addSpacing(8)
        self.vBox.addLayout(self.stepsLayout)
        self.vBox.addWidget(self.moreLabel)
        self.vBox.addWidget(self.errorLabel)
        self.retranslateUi()

    def retranslateUi(self):
        self.titleLabel.setText(tr("上次运行"))
        self.logLink.setText(tr("查看日志") + " ›")

    def setRun(self, run, now, *, unavailable=False, evernight=False):
        for row in self._steps:
            self.stepsLayout.removeWidget(row)
            row.hide()
            row.deleteLater()
        self._steps = []
        self.logLink.setEvernight(evernight)
        if run is None:
            self._link = None
            self.resultPill.hide()
            self.logLink.hide()
            self.metaLabel.setFullText(tr("暂时读不到运行记录") if unavailable else tr("还没有运行记录，完成一次运行后会显示每一项的结果"))
            self.moreLabel.hide()
            self.errorLabel.hide()
            return
        self._link = run.link
        self.resultPill.setPill(result_label(run.status), RESULT_TONES.get(run.status, "neutral"), evernight=evernight)
        self.resultPill.show()
        self.logLink.setVisible(bool(run.link))
        parts = []
        if run.task not in ("main", "routine") or not run.steps:
            parts.append(run.name)
        parts.append(format_when(run.started_at, now))
        if run.seconds:
            parts.append(tr("用时 {duration}").format(duration=format_duration(run.seconds)))
        if run.trigger and run.trigger != "unknown":
            parts.append(tr("{trigger}触发").format(trigger=trigger_label(run.trigger)))
        self.metaLabel.setFullText(" · ".join(part for part in parts if part))
        for step in run.steps[:self.MAX_STEPS]:
            row = StepRow(step, evernight=evernight, parent=self)
            self.stepsLayout.addWidget(row)
            self._steps.append(row)
        hidden = len(run.steps) - self.MAX_STEPS
        self.moreLabel.setText(tr("以及另外 {count} 项").format(count=hidden))
        self.moreLabel.setVisible(hidden > 0)
        failed = run.status not in ("success", "running") and run.error
        self.errorLabel.setFullText(run.error or "")
        self.errorLabel.setTextColor(QColor("#c42b1c"), QColor("#ff99a4"))
        self.errorLabel.setVisible(bool(failed))


class ShortcutsCard(OverviewCard):
    shortcutTriggered = Signal(str)
    editRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons = []
        header = QHBoxLayout()
        self.titleLabel = card_title(self)
        self.editLink = LinkButton("", self, size=13)
        self.editLink.clicked.connect(self.editRequested)
        header.addWidget(self.titleLabel)
        header.addStretch(1)
        header.addWidget(self.editLink)
        self.grid = QGridLayout()
        self.grid.setSpacing(8)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)
        self.emptyLabel = secondary(CaptionLabel(self))
        self.emptyLabel.hide()
        self.vBox.addLayout(header)
        self.vBox.addSpacing(10)
        self.vBox.addLayout(self.grid)
        self.vBox.addWidget(self.emptyLabel)
        self.retranslateUi()

    def retranslateUi(self):
        self.titleLabel.setText(tr("快捷启动"))
        self.editLink.setText(tr("编辑"))

    def setShortcuts(self, shortcuts, *, hidden=False, unavailable=False, evernight=False, editable=True):
        for button in self._buttons:
            self.grid.removeWidget(button)
            button.hide()
            button.deleteLater()
        self._buttons = []
        self.editLink.setEvernight(evernight)
        self.editLink.setVisible(editable and not unavailable)
        shortcuts = tuple(shortcuts or ())
        self._buttons = [self._makeButton(shortcut) for shortcut in shortcuts]
        self._columns = 0
        self._arrangeButtons()
        if unavailable:
            self.emptyLabel.setText(tr("暂时读不到快捷启动"))
        elif hidden:
            self.emptyLabel.setText(tr("当前连接方式没有可用的快捷启动"))
        else:
            self.emptyLabel.setText(tr("还没有快捷启动，点「编辑」添加常用操作") if editable else tr("还没有快捷启动"))
        self.emptyLabel.setVisible(not shortcuts)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._arrangeButtons()

    def _arrangeButtons(self):
        if not self._buttons:
            return
        margins = self.vBox.contentsMargins()
        width = self.width() - margins.left() - margins.right()
        widest = max(button.sizeHint().width() for button in self._buttons)
        columns = 2 if width >= 2 * widest + self.grid.spacing() else 1
        if columns != self._columns:
            self._columns = columns
            span = 2 if columns == 1 else 1
            for i, button in enumerate(self._buttons):
                self.grid.addWidget(button, i // columns, i % columns, 1, span)

    def _makeButton(self, shortcut):
        icon = resolve_icon(shortcut.icon)
        if shortcut.menu:
            button = DropDownPushButton(icon, shortcut.name, self)
            menu = RoundMenu(parent=button)
            for action in shortcut.menu:
                menu.addAction(Action(action.name, triggered=lambda _=False, key=action.id: self.shortcutTriggered.emit(key)))
            button.setMenu(menu)
        else:
            button = PushButton(icon, shortcut.name, self)
            button.clicked.connect(lambda _=False, key=shortcut.id: self.shortcutTriggered.emit(key))
        if sys.platform == "darwin":
            # macOS 原生按钮的布局会扣除透明边距，但 Fluent 样式绘制覆盖整个控件。
            button.setAttribute(Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setMinimumWidth(0)
        return button


class CheckItem(QWidget):
    clicked = Signal(str)

    def __init__(self, check, *, evernight=False, parent=None):
        super().__init__(parent)
        self.check = check
        self._kind = CHECK_TONES.get(check.level, "info")
        self._evernight = evernight
        icon = {"error": InfoBarIcon.ERROR, "warning": InfoBarIcon.WARNING}.get(self._kind, InfoBarIcon.INFORMATION)
        self.iconWidget = IconWidget(icon, self)
        self.iconWidget.setFixedSize(16, 16)
        self.titleLabel = BodyLabel(check.title, self)
        setFont(self.titleLabel, 13, QFont.Weight.DemiBold)
        self.titleLabel.setWordWrap(True)
        self.descriptionLabel = secondary(CaptionLabel(check.description, self))
        self.descriptionLabel.setWordWrap(True)
        self.link = LinkButton(tr("去设置"), self, size=13)
        self.link.setEvernight(evernight)
        self.link.setVisible(bool(check.link))
        self.link.clicked.connect(lambda: self.clicked.emit(check.link))
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(self.titleLabel)
        text.addWidget(self.descriptionLabel)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)
        layout.addWidget(self.iconWidget, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text, 1)
        layout.addWidget(self.link, 0, Qt.AlignmentFlag.AlignVCenter)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(tone(self._kind, self._evernight)[0])
        painter.drawRoundedRect(QRectF(self.rect()), 6, 6)


class ChecksCard(OverviewCard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self.titleLabel = card_title(self)
        self.itemsLayout = QVBoxLayout()
        self.itemsLayout.setSpacing(8)
        self.emptyLabel = secondary(CaptionLabel(self))
        self.emptyLabel.hide()
        self.vBox.addWidget(self.titleLabel)
        self.vBox.addSpacing(10)
        self.vBox.addLayout(self.itemsLayout)
        self.vBox.addWidget(self.emptyLabel)
        self.retranslateUi()

    def retranslateUi(self):
        self.titleLabel.setText(tr("建议检查"))

    def setChecks(self, checks, *, unavailable=False, evernight=False):
        for item in self._items:
            self.itemsLayout.removeWidget(item)
            item.hide()
            item.deleteLater()
        self._items = []
        for check in tuple(checks or ()):
            item = CheckItem(check, evernight=evernight, parent=self)
            item.clicked.connect(self._emitLink)
            self.itemsLayout.addWidget(item)
            self._items.append(item)
        self.emptyLabel.setText(tr("暂时无法检查设置"))
        self.emptyLabel.setVisible(unavailable)
