"""当前运行和运行记录共用的卡片：标题行、账号进度、步骤条和收尾说明。"""
from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QFontMetrics, QPainter
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QToolTip, QVBoxLayout, QWidget
from qfluentwidgets import (Action, BodyLabel, FluentIcon, PrimaryPushButton, PrimarySplitPushButton,
                            PushButton, RoundMenu, SimpleCardWidget, isDarkTheme)

from app.accounts.avatar import paint_avatar
from app.overview.widgets import ElidedLabel, LinkButton, Pill
from app.pages import style
from app.pages.common import Divider, bare_switch, is_evernight, secondary, style_primary
from module.localization import tr
from .stepper import Stepper

# 运行状态 -> 配色
RUN_TONES = {"running": "accent", "pausing": "warning", "paused": "warning", "stopping": "warning",
             "finishing": "accent", "success": "success", "partial": "warning", "failed": "error",
             "aborted": "error", "interrupted": "warning", "blocked": "warning", "stopped": "neutral",
             "timeout": "error", "skipped": "neutral", "waiting": "neutral"}
BADGES = {"success": ("success", "check"), "partial": ("warning", "alert"), "failed": ("error", "cross"),
          "timeout": ("error", "cross"), "stopped": ("neutral", "dash"), "skipped": ("neutral", "dash")}


def run_text(status):
    return {"running": tr("运行中"), "pausing": tr("正在暂停"), "paused": tr("已暂停"), "stopping": tr("正在停止"),
            "finishing": tr("收尾中"), "success": tr("成功"), "partial": tr("部分完成"), "failed": tr("失败"),
            "aborted": tr("异常结束"), "interrupted": tr("中断"), "blocked": tr("未执行"), "stopped": tr("已停止"),
            "timeout": tr("超时"), "skipped": tr("已跳过"), "waiting": tr("等待中")}.get(status, "")


def elapsed_text(seconds):
    if seconds is None:
        return ""
    seconds = int(max(0, seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"


class StatusDot(QWidget):
    """标题前的状态圆点。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self._status = ""

    def setStatus(self, status):
        self._status = status
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        if self._status in BADGES and self._status != "skipped":
            tone, mark = BADGES[self._status]
            background, foreground = style.status_colors(tone)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(background)
            painter.drawEllipse(rect)
            style.glyph(painter, mark, rect.adjusted(4, 4, -4, -4), foreground, 1.5)
            return
        color = style.status_line(RUN_TONES.get(self._status, "neutral"))
        halo = style.status_colors(RUN_TONES.get(self._status, "neutral"))[0]
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(rect)
        painter.setBrush(color)
        painter.drawEllipse(rect.center(), 4.5, 4.5)


class AccountStrip(QWidget):
    """轮流运行的账号进度：一排头像，角标是结果，当前账号有一圈强调色。"""
    accountClicked = Signal(str)
    SIZE, STEP = 28, 40

    def __init__(self, parent=None):
        super().__init__(parent)
        self._accounts = ()
        self._current = None
        self.setMouseTracking(True)
        self.setFixedHeight(34)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def setAccounts(self, accounts, current):
        self._accounts, self._current = tuple(accounts), current
        self.setFixedWidth(max(0, len(self._accounts) * self.STEP - (self.STEP - self.SIZE) + 8))
        self.setAccessibleName("；".join(f"{item.name} {run_text(item.status)}" for item in self._accounts))
        self.update()

    def _rect(self, index):
        return QRectF(4 + index * self.STEP, 3, self.SIZE, self.SIZE)

    def _at(self, position):
        for index, item in enumerate(self._accounts):
            if self._rect(index).adjusted(-4, -3, 4, 3).contains(QPointF(position)):
                return item
        return None

    def event(self, event):
        if event.type() == QEvent.Type.ToolTip:
            item = self._at(event.pos())
            if item is not None:
                text = " · ".join(filter(None, (item.name, run_text(item.status))))
                QToolTip.showText(event.globalPos(), f"{text}\n{item.reason}" if item.reason else text, self)
            return True
        return super().event(event)

    def mouseMoveEvent(self, event):
        item = self._at(event.position())
        clickable = item is not None and bool(item.run_id)
        self.setCursor(Qt.CursorShape.PointingHandCursor if clickable else Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event):
        item = self._at(event.position())
        if event.button() == Qt.MouseButton.LeftButton and item is not None and item.run_id:
            self.accountClicked.emit(item.run_id)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for index, item in enumerate(self._accounts):
            rect = self._rect(index)
            if index:
                painter.setPen(style.stroke(style.rule(), 2))
                y = rect.center().y()
                painter.drawLine(QPointF(rect.left() - 9, y), QPointF(rect.left() - 4, y))
            waiting = item.status in ("waiting", "skipped")
            paint_avatar(painter, rect, item.color, item.name, faded=waiting)
            if item.uid == self._current:
                painter.setPen(style.stroke(style.link(), 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(rect.adjusted(-2, -2, 2, 2))
            if item.status in BADGES:
                tone, mark = BADGES[item.status]
                color = style.status_line(tone)
                badge = QRectF(rect.right() - 10, rect.bottom() - 10, 13, 13)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(Qt.GlobalColor.black if isDarkTheme() else Qt.GlobalColor.white)
                painter.drawEllipse(badge)
                painter.setBrush(color)
                painter.drawEllipse(badge.adjusted(1, 1, -1, -1))
                foreground = Qt.GlobalColor.black if isDarkTheme() else Qt.GlobalColor.white
                style.glyph(painter, "cross" if mark == "alert" else mark, badge.adjusted(3, 3, -3, -3), foreground, 1.3)


class AccountPill(QWidget):
    """正在运行的账号：小头像、名字和「第几个」。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._color, self._name, self._extra = 0, "", ""
        self.setFixedHeight(26)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def setAccount(self, color, name, extra=""):
        self._color, self._name, self._extra = color, name, extra
        self.setAccessibleName(f"{name} {extra}".strip())
        self.setFixedWidth(self.sizeHint().width())
        self.update()

    def _text(self):
        return f"{self._name}{self._extra}"

    def sizeHint(self):
        return QSize(min(260, 30 + QFontMetrics(style.font(12)).horizontalAdvance(self._text()) + 12), 26)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        rect = QRectF(self.rect())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(style.status_colors("neutral")[0])
        painter.drawRoundedRect(rect, 13, 13)
        paint_avatar(painter, QRectF(3, 3, 20, 20), self._color, self._name)
        painter.setPen(style.muted())
        painter.setFont(style.font(12))
        space = rect.width() - 30 - 10
        painter.drawText(QRectF(30, 0, space, rect.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         painter.fontMetrics().elidedText(self._text(), Qt.TextElideMode.ElideRight, int(space)))


class RunCard(SimpleCardWidget):
    """标题行 + 步骤条 + 一行说明。当前运行和运行记录各自往 actions 里放按钮。"""
    accountClicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBorderRadius(8)
        self.dot = StatusDot(self)
        self.titleLabel = ElidedLabel(self, size=18)
        self.titleLabel.setFont(style.strong(18))
        self.strip = AccountStrip(self)
        self.strip.accountClicked.connect(self.accountClicked)
        self.accountPill = AccountPill(self)
        self.statusPill = Pill(self, height=26)
        self.timePill = Pill(self, height=26)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(8)
        head = QHBoxLayout()
        head.setSpacing(10)
        head.addWidget(self.dot)
        head.addWidget(self.titleLabel)
        head.addWidget(self.accountPill)
        head.addWidget(self.strip)
        head.addWidget(self.statusPill)
        head.addWidget(self.timePill)
        head.addStretch(1)
        head.addLayout(self.actions)
        self.subLabel = secondary(ElidedLabel(self, size=12))
        self.subLabel.hide()
        self.stepper = Stepper(self)
        self.divider = Divider(self)
        self.foot = QHBoxLayout()
        self.foot.setSpacing(8)
        self.footLabel = ElidedLabel(self, size=13)
        self.footLink = LinkButton("", self, size=13)
        self.foot.addWidget(self.footLabel)
        self.foot.addStretch(1)
        self.foot.addWidget(self.footLink)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(18, 14, 16, 12)
        self.body.setSpacing(10)
        self.body.addLayout(head)
        self.body.addWidget(self.subLabel)
        self.body.addWidget(self.stepper)
        self.body.addWidget(self.divider)
        self.body.addLayout(self.foot)
        self.accountPill.hide()
        self.strip.hide()
        self.setFoot("")

    def setTitle(self, title, status):
        self.titleLabel.setFullText(title)
        self.dot.setStatus(status)

    def setPills(self, status_text="", tone="neutral", time_text=""):
        evernight = is_evernight()
        self.statusPill.setVisible(bool(status_text))
        self.statusPill.setPill(status_text, tone, evernight=evernight)
        self.timePill.setVisible(bool(time_text))
        self.timePill.setPill(time_text, "neutral", evernight=evernight)

    def setSubtitle(self, text):
        self.subLabel.setFullText(text)
        self.subLabel.setVisible(bool(text))

    def setAccount(self, account=None, extra=""):
        self.accountPill.setVisible(account is not None)
        if account is not None:
            self.accountPill.setAccount(account.color, account.name, extra)

    def setAccounts(self, accounts, current=None):
        self.strip.setVisible(len(accounts) > 1)
        self.strip.setAccounts(accounts, current)

    def setSteps(self, steps):
        self.stepper.setVisible(len(steps) > 1)
        self.stepper.setSteps(steps)

    def setFoot(self, text, link="", *, tone=None):
        shown = bool(text or link)
        self.divider.setVisible(shown)
        self.footLabel.setVisible(bool(text))
        self.footLabel.setFullText(text)
        color = style.status_line(tone) if tone else style.muted()
        self.footLabel.setTextColor(color, color)
        self.footLink.setText(link)
        self.footLink.setVisible(bool(link))
        self.footLink.setEvernight(is_evernight())


class CurrentRunCard(RunCard):
    """正在运行（或空闲）的卡片。"""
    startClicked = Signal()
    startAllClicked = Signal()
    pauseClicked = Signal()
    stopClicked = Signal()
    skipClicked = Signal()
    overlayToggled = Signal(bool)
    finishToggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.overlaySwitch = bare_switch(self)
        self.overlaySwitch.checkedChanged.connect(self.overlayToggled)
        self.overlayLabel = secondary(BodyLabel(self))
        self.pauseButton = PushButton(FluentIcon.PAUSE, "", self)
        self.pauseButton.clicked.connect(self.pauseClicked)
        self.stopButton = PrimaryPushButton(FluentIcon.CLOSE, "", self)
        self.stopButton.clicked.connect(self.stopClicked)
        self.stopSplit = PrimarySplitPushButton(FluentIcon.CLOSE, "", self)
        self.stopSplit.clicked.connect(self.stopClicked)
        self.stopMenu = RoundMenu(parent=self)
        self.skipAction = Action(FluentIcon.CHEVRON_RIGHT, "", triggered=lambda: self.skipClicked.emit())
        self.stopMenu.addAction(self.skipAction)
        self.stopSplit.setFlyout(self.stopMenu)
        self.startAllButton = PushButton(FluentIcon.PEOPLE, "", self)
        self.startAllButton.clicked.connect(self.startAllClicked)
        self.startButton = PrimaryPushButton(FluentIcon.PLAY, "", self)
        self.startButton.clicked.connect(self.startClicked)
        for widget in (self.overlaySwitch, self.overlayLabel, self.pauseButton, self.stopButton, self.stopSplit,
                       self.startAllButton, self.startButton):
            self.actions.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
        self.footLink.clicked.connect(lambda: self.finishToggled.emit(not self._finishSkipped) if self._running else None)
        self._running = False
        self._finishSkipped = False
        self.restyle()

    def restyle(self):
        evernight = is_evernight()
        for button in (self.stopButton, self.stopSplit, self.startButton):
            style_primary(button, evernight)

    def retranslateUi(self, *, pause_key="", stop_key=""):
        self._keys = (pause_key, stop_key)
        self.overlayLabel.setText(tr("在游戏内显示日志"))
        self.overlaySwitch.setAccessibleName(tr("在游戏内显示日志"))
        self.skipAction.setText(tr("跳过当前账号"))
        self.startButton.setText(tr("开始完整运行"))
        self.startAllButton.setText(tr("轮流运行全部"))
        self.stopSplit.setToolTip(tr("停止整轮；箭头里可以只跳过当前账号"))

    def setOverlay(self, enabled, available=True):
        self.overlaySwitch.blockSignals(True)
        self.overlaySwitch.setChecked(enabled)
        self.overlaySwitch.blockSignals(False)
        self.overlaySwitch.setEnabled(available)

    def _key(self, text, key):
        return f"{text} ({key})" if key else text

    def setIdle(self, text, link, *, can_start, can_start_all):
        """没有任务在运行：只显示上次结果和开始按钮。"""
        self._running = False
        self.setTitle(tr("没有任务在运行"), "waiting")
        self.setPills()
        self.setAccount()
        self.setAccounts(())
        self.setSteps(())
        self.setFoot(text, link)
        for widget in (self.pauseButton, self.stopButton, self.stopSplit):
            widget.hide()
        self.startButton.show()
        self.startButton.setEnabled(can_start)
        self.startAllButton.setVisible(can_start_all)

    def setRunning(self, view):
        """view：app.content.run_controller 给出的当前运行。"""
        self._running = True
        self._finishSkipped = view.finish_skipped
        self.setTitle(view.title, view.state)
        special = view.state in ("pausing", "paused", "stopping", "finishing")
        self.setPills(run_text(view.state) if special else "", RUN_TONES.get(view.state, "neutral"), self.timeText(view.seconds))
        rotating = len(view.accounts) > 1
        extra = tr("（{index} / {total}）").format(index=view.account_index, total=len(view.accounts)) if rotating else ""
        self.setAccount(view.account, extra)
        self.setAccounts(view.accounts, view.account.uid if view.account else None)
        self.setSteps(view.steps)
        if view.finish_text:
            skipped = view.finish_skipped
            text = tr("全部完成后：{action}").format(action=tr("不执行完成后操作") if skipped else view.finish_text)
            link = "" if not view.can_skip_finish else tr("恢复") if skipped else tr("本次不执行")
            self.setFoot(text, link)
        else:
            self.setFoot("")
        self.startButton.hide()
        self.startAllButton.hide()
        pause_key, stop_key = getattr(self, "_keys", ("", ""))
        paused = view.state == "paused"
        self.pauseButton.setVisible(view.can_pause)
        self.pauseButton.setEnabled(view.state in ("running", "paused"))
        self.pauseButton.setIcon(FluentIcon.PLAY if paused else FluentIcon.PAUSE)
        self.pauseButton.setText(self._key(tr("继续") if paused else tr("暂停"), pause_key))
        self.stopButton.setVisible(not view.can_skip)
        self.stopSplit.setVisible(view.can_skip)
        enabled = view.can_stop and view.state != "stopping"
        for button in (self.stopButton, self.stopSplit):
            button.setText(self._key(tr("停止"), stop_key))
            button.setEnabled(enabled)

    def timeText(self, seconds):
        return tr("已运行 {time}").format(time=elapsed_text(seconds)) if seconds is not None else ""

    def setElapsed(self, seconds):
        if self.timePill.isVisible() or seconds is not None:
            self.timePill.setVisible(seconds is not None)
            self.timePill.setPill(self.timeText(seconds), "neutral", evernight=is_evernight())
