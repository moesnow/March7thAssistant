"""账号页右侧：所选账号的登录、任务方案和最近 7 天结果。"""
from datetime import datetime

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QHBoxLayout, QToolTip, QVBoxLayout, QWidget
from qfluentwidgets import (Action, BodyLabel, CaptionLabel, ComboBox, FluentIcon, IconWidget, PushButton, RoundMenu,
                            ScrollArea, SegmentedWidget, SimpleCardWidget, StrongBodyLabel, TransparentToolButton)

from app.overview.style import format_when
from app.overview.widgets import ElidedLabel, LinkButton, Pill
from app.pages import style
from app.pages.common import Divider, NoticeStrip, bare_switch, icon_of, is_evernight, popup_menu, secondary
from module.localization import tr
from .account_list import account_line, server_text
from .avatar import Avatar

DAY = {"success": ("success", "check"), "partial": ("warning", "alert"), "failed": ("error", "cross"),
       "stopped": ("neutral", "dash"), "none": ("neutral", "dash")}


class Row(QWidget):
    """一行设置：标题、说明和右侧的控件。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = BodyLabel(self)
        self.descriptionLabel = secondary(CaptionLabel(self))
        self.descriptionLabel.setWordWrap(True)
        column = QVBoxLayout()
        column.setSpacing(2)
        column.addStretch(1)
        column.addWidget(self.titleLabel)
        column.addWidget(self.descriptionLabel)
        column.addStretch(1)
        self.trailing = QHBoxLayout()
        self.trailing.setSpacing(10)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 11, 16, 11)
        layout.setSpacing(16)
        layout.addLayout(column, 1)
        layout.addLayout(self.trailing)
        self.setMinimumHeight(58)

    def setTexts(self, title, description):
        self.titleLabel.setText(title)
        self.descriptionLabel.setText(description)
        self.descriptionLabel.setVisible(bool(description))

    def addTrailing(self, widget):
        widget.setParent(self)
        self.trailing.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
        return widget


class Group(QWidget):
    """小标题加一张卡片。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = StrongBodyLabel(self)
        self.card = SimpleCardWidget(self)
        self.card.setBorderRadius(8)
        self.rows = QVBoxLayout(self.card)
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(0)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.titleLabel)
        layout.addWidget(self.card)

    def addRow(self, widget):
        if self.rows.count():
            self.rows.addWidget(Divider(self.card))
        self.rows.addWidget(widget)
        return widget


class HeaderCard(SimpleCardWidget):
    renameClicked = Signal()
    switchClicked = Signal()
    runClicked = Signal()
    rotateToggled = Signal(bool)
    folderClicked = Signal()
    deleteClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBorderRadius(8)
        self.avatar = Avatar(48, self)
        self.nameLabel = ElidedLabel(self, size=20)
        self.nameLabel.setFont(style.strong(20))
        self.renameButton = TransparentToolButton(FluentIcon.EDIT, self)
        self.renameButton.setFixedSize(28, 28)
        self.renameButton.clicked.connect(self.renameClicked)
        self.lineLabel = secondary(ElidedLabel(self, size=13))
        self.planPill = Pill(self)
        self.switchButton = PushButton(self)
        self.switchButton.clicked.connect(self.switchClicked)
        self.runButton = PushButton(self)
        self.runButton.setIcon(FluentIcon.PLAY)
        self.runButton.clicked.connect(self.runClicked)
        self.moreButton = TransparentToolButton(FluentIcon.MORE, self)
        self.moreButton.setFixedSize(32, 32)
        self.moreButton.clicked.connect(self._openMenu)
        self._active = False
        self._rotate = False
        name = QHBoxLayout()
        name.setSpacing(4)
        name.addWidget(self.nameLabel)
        name.addWidget(self.renameButton)
        name.addStretch(1)
        line = QHBoxLayout()
        line.setSpacing(8)
        line.addWidget(self.lineLabel)
        line.addWidget(self.planPill)
        line.addStretch(1)
        column = QVBoxLayout()
        column.setSpacing(4)
        column.addLayout(name)
        column.addLayout(line)
        self.buttons = QHBoxLayout()
        self.buttons.setSpacing(8)
        self.buttons.addWidget(self.switchButton)
        self.buttons.addWidget(self.runButton)
        self.buttons.addWidget(self.moreButton)
        top = QHBoxLayout()
        top.setSpacing(14)
        top.addWidget(self.avatar)
        top.addLayout(column, 1)
        top.addLayout(self.buttons)
        self.setLayout(top)
        top.setContentsMargins(18, 16, 14, 16)

    def event(self, event):
        # 按钮文字或字体变了也会改变可用宽度，不只是缩放窗口。
        if event.type() in (QEvent.Type.Resize, QEvent.Type.LayoutRequest) and hasattr(self, "buttons"):
            self._fit()
        return super().event(event)

    def _fit(self):
        """名字一栏放不下方案胶囊时收起它，下面的「任务方案」里也有。"""
        column = self.width() - 32 - 48 - 14 * 2 - self.buttons.sizeHint().width()
        needed = self.lineLabel.sizeHint().width() + 20 + self.planPill.sizeHint().width()
        self.planPill.setVisible(self._active and needed <= column)

    def setAccount(self, info, *, active, current, busy):
        """active：多账号生效；current：界面正在查看和编辑的账号；busy：有任务在运行。"""
        self._active, self._rotate = active, info.rotate
        self.avatar.setAccount(info.color, info.name)
        self.nameLabel.setFullText(info.name)
        self.lineLabel.setFullText(account_line(info))
        self.planPill.setPill(tr("任务方案：独立") if info.plan == "independent" else tr("任务方案：共享"),
                              "neutral", evernight=is_evernight())
        if active:
            self.switchButton.setIcon(FluentIcon.PEOPLE)
            self.switchButton.setText(tr("正在使用") if current else tr("切换到此账号"))
            self.switchButton.setEnabled(not current)
            self.switchButton.setToolTip(tr("任务页和总览改为查看、编辑这个账号；游戏没在运行时，同时切换登录"))
        else:
            self.switchButton.setIcon(FluentIcon.PEOPLE)
            self.switchButton.setText(tr("当前登录") if info.logged_in else tr("切换登录"))
            self.switchButton.setEnabled(not info.logged_in and info.login != "missing")
            self.switchButton.setToolTip(tr("把这个账号的登录信息写回游戏，需要先退出游戏"))
        self.runButton.setVisible(active)
        self.runButton.setText(tr("只运行此账号"))
        self.runButton.setEnabled(not busy)
        self._fit()

    def _openMenu(self):
        menu = RoundMenu(parent=self)
        if self._active:
            text = tr("不参与轮流") if self._rotate else tr("参与轮流")
            menu.addAction(Action(FluentIcon.SYNC, text, triggered=lambda: self.rotateToggled.emit(not self._rotate)))
        menu.addAction(Action(FluentIcon.FOLDER, tr("打开账号文件夹"), triggered=lambda: self.folderClicked.emit()))
        menu.addSeparator()
        menu.addAction(Action(FluentIcon.DELETE, tr("删除账号…"), triggered=lambda: self.deleteClicked.emit()))
        popup_menu(self, menu, self.moreButton.mapToGlobal(self.moreButton.rect().bottomLeft()))


class LoginGroup(Group):
    saveClicked = Signal()
    credentialsClicked = Signal()
    clearCredentialsClicked = Signal()
    autoLoginToggled = Signal(bool)
    pathClicked = Signal()
    pathCleared = Signal()
    hourChanged = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.snapshotRow = self.addRow(Row(self.card))
        self.saveButton = self.snapshotRow.addTrailing(PushButton(self))
        self.saveButton.setIcon(FluentIcon.SYNC)
        self.saveButton.clicked.connect(self.saveClicked)
        self.credentialsRow = self.addRow(Row(self.card))
        self.credentialsPill = self.credentialsRow.addTrailing(Pill(self))
        self.credentialsButton = self.credentialsRow.addTrailing(LinkButton("", self, size=13))
        self.credentialsButton.clicked.connect(self._openCredentials)
        self.autoSwitch = self.credentialsRow.addTrailing(bare_switch(self))
        self.autoSwitch.checkedChanged.connect(self.autoLoginToggled)
        self.clientRow = self.addRow(Row(self.card))
        self.clearPathButton = self.clientRow.addTrailing(LinkButton("", self, size=13))
        self.clearPathButton.clicked.connect(self.pathCleared)
        self.pathButton = self.clientRow.addTrailing(PushButton(self))
        self.pathButton.clicked.connect(self.pathClicked)
        self.hourRow = self.addRow(Row(self.card))
        self.hourCombo = self.hourRow.addTrailing(ComboBox(self))
        self.hourCombo.setMinimumWidth(150)
        self.hourCombo.currentIndexChanged.connect(self._hourChanged)
        self._saved = False

    def _openCredentials(self):
        if not self._saved:
            self.credentialsClicked.emit()
            return
        menu = RoundMenu(parent=self)
        menu.addAction(Action(FluentIcon.EDIT, tr("重新填写…"), triggered=lambda: self.credentialsClicked.emit()))
        menu.addAction(Action(FluentIcon.DELETE, tr("清除保存的密码"), triggered=lambda: self.clearCredentialsClicked.emit()))
        popup_menu(self, menu, self.credentialsButton.mapToGlobal(self.credentialsButton.rect().bottomLeft()))

    def _hourChanged(self, index):
        if index >= 0:
            self.hourChanged.emit(self.hourCombo.itemData(index))

    def setAccount(self, info, *, active, default_hour, now=None):
        now = now or datetime.now()
        evernight = is_evernight()
        self.titleLabel.setText(tr("登录"))
        if info.login == "missing":
            text = tr("还没有保存登录。在游戏里登录这个账号，完全进入游戏后点「保存」。")
        elif info.login == "expired":
            text = tr("登录已过期。在游戏里重新登录这个账号，完全进入游戏后点「重新保存」。")
        else:
            saved = format_when(info.saved_at, now) if info.saved_at else tr("时间未知")
            text = tr("切换账号时写回游戏的登录信息 · 上次保存于{time}").format(time=saved)
            if active:
                text += tr("，运行结束后自动更新")
        self.snapshotRow.setTexts(tr("游戏登录快照"), text)
        self.saveButton.setText(tr("保存") if info.login == "missing" else tr("重新保存"))
        self._saved = info.credentials == "saved"
        self.credentialsRow.setTexts(tr("登录过期时自动填写账号密码"),
                                     tr("使用 Windows 加密保存在本机，仅当前 Windows 用户可以解密"))
        states = {"saved": ("success", tr("已保存")), "unreadable": ("warning", tr("需要重新保存")), "none": ("neutral", "")}
        kind, text = states.get(info.credentials, states["none"])
        self.credentialsPill.setVisible(bool(text))
        self.credentialsPill.setPill(text, kind, evernight=evernight)
        self.credentialsButton.setText(tr("修改") if self._saved else tr("填写账号密码"))
        self.credentialsButton.setEvernight(evernight)
        self.autoSwitch.blockSignals(True)
        self.autoSwitch.setChecked(bool(info.auto_login and self._saved))
        self.autoSwitch.blockSignals(False)
        self.autoSwitch.setVisible(self._saved)
        self.autoSwitch.setAccessibleName(tr("登录过期时自动填写账号密码"))
        own = bool(info.game_path)
        text = info.game_path if own else tr("使用「运行方式」里设置的游戏路径")
        if info.status.kind == "need_path":
            text = tr("这个账号是{server}，和「运行方式」里的游戏客户端不同，需要单独选择。").format(server=server_text(info.server))
        self.clientRow.setTexts(tr("游戏客户端"), text)
        self.clientRow.descriptionLabel.setToolTip(info.game_path if own else "")
        self.clearPathButton.setText(tr("恢复默认"))
        self.clearPathButton.setEvernight(evernight)
        self.clearPathButton.setVisible(own)
        self.pathButton.setText(tr("选择…"))
        self.hourRow.setTexts(tr("游戏每日刷新时间"), tr("其他服务器的刷新时间换算成本机时间后可能不同"))
        self.hourCombo.blockSignals(True)
        self.hourCombo.clear()
        self.hourCombo.addItem(tr("跟随设置（{hour}:00）").format(hour=default_hour), userData=None)
        for hour in range(24):
            self.hourCombo.addItem(f"{hour}:00", userData=hour)
        self.hourCombo.setCurrentIndex(0 if info.refresh_hour is None else info.refresh_hour + 1)
        self.hourCombo.blockSignals(False)


class DiffRow(QWidget):
    restoreClicked = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.diff = None
        self.iconWidget = IconWidget(self)
        self.iconWidget.setFixedSize(16, 16)
        self.titleLabel = StrongBodyLabel(self)
        self.valueLabel = ElidedLabel(self, size=13)
        self.sharedLabel = secondary(ElidedLabel(self, size=12))
        self.restoreButton = LinkButton("", self, size=13)
        self.restoreButton.clicked.connect(lambda: self.restoreClicked.emit(self.diff))
        head = QHBoxLayout()
        head.setSpacing(10)
        head.addWidget(self.titleLabel)
        head.addWidget(self.valueLabel, 1)
        column = QVBoxLayout()
        column.setSpacing(1)
        column.addLayout(head)
        column.addWidget(self.sharedLabel)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(12)
        layout.addWidget(self.iconWidget)
        layout.addLayout(column, 1)
        layout.addWidget(self.restoreButton)

    def setDiff(self, diff):
        self.diff = diff
        self.iconWidget.setIcon(icon_of(diff.icon))
        self.titleLabel.setText(f"{diff.page_title} · {diff.title}" if diff.page_title else diff.title)
        self.valueLabel.setFullText(diff.value_text)
        self.sharedLabel.setFullText(tr("共享方案：{value}").format(value=diff.shared_text))
        self.restoreButton.setText(tr("恢复共享"))
        self.restoreButton.setEvernight(is_evernight())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(style.inset_fill())
        painter.drawRoundedRect(QRectF(self.rect()), 6, 6)


class PlanGroup(Group):
    planChanged = Signal(str)
    restoreClicked = Signal(object)
    editClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.modeRow = self.addRow(Row(self.card))
        self.segment = self.modeRow.addTrailing(SegmentedWidget(self))
        self.segment.addItem("shared", "")
        self.segment.addItem("independent", "")
        self.segment.currentItemChanged.connect(self._changed)
        self._syncing = False
        self.body = QWidget(self.card)
        self.list = QVBoxLayout(self.body)
        self.list.setContentsMargins(16, 0, 16, 0)
        self.list.setSpacing(6)
        self.emptyLabel = secondary(CaptionLabel(self.body))
        self.emptyLabel.setWordWrap(True)
        self.list.addWidget(self.emptyLabel)
        self.diffRows = []
        self.editButton = PushButton(self.card)
        self.editButton.clicked.connect(self.editClicked)
        footer = QHBoxLayout()
        footer.setContentsMargins(16, 10, 16, 14)
        footer.addStretch(1)
        footer.addWidget(self.editButton)
        self.rows.addWidget(self.body)
        self.rows.addLayout(footer)

    def _changed(self, key):
        if not self._syncing:
            self.planChanged.emit(key)

    def setAccount(self, info, diffs):
        independent = info.plan == "independent"
        self.titleLabel.setText(tr("任务方案"))
        self.modeRow.setTexts(tr("使用哪套任务设置"),
                              tr("独立方案从共享方案复制而来，只记录与共享方案不同的地方；共享方案更新时，未改动的项目会一起更新"))
        self._syncing = True
        self.segment.items["shared"].setText(tr("共享方案"))
        self.segment.items["independent"].setText(tr("独立方案"))
        self.segment.setCurrentItem(info.plan if info.plan in self.segment.items else "shared")
        self._syncing = False
        shown = list(diffs) if independent else []
        while len(self.diffRows) > len(shown):
            row = self.diffRows.pop()
            row.hide()
            row.deleteLater()
        while len(self.diffRows) < len(shown):
            row = DiffRow(self.body)
            row.restoreClicked.connect(self.restoreClicked)
            self.list.addWidget(row)
            self.diffRows.append(row)
        for row, diff in zip(self.diffRows, shown):
            row.setDiff(diff)
        if not independent and diffs:
            text = tr("这个账号有 {count} 项独立设置，切回独立方案后会恢复。").format(count=len(diffs))
        elif independent and not shown:
            text = tr("还没有和共享方案不同的设置。在任务页修改的内容只对这个账号生效。")
        else:
            text = ""
        self.emptyLabel.setText(text)
        self.emptyLabel.setVisible(bool(text))
        self.editButton.setText(tr("编辑此账号的任务") + " ›")


class WeekStrip(QWidget):
    """最近 7 天，每天一个结果，点击查看当天的运行。"""
    dayClicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(62)
        self.setMouseTracking(True)
        self._days = ()

    def setDays(self, days):
        self._days = tuple(days)
        self.update()

    def _cell(self, index):
        width = self.width() / max(1, len(self._days))
        return QRectF(index * width, 0, width, self.height())

    def _at(self, position):
        for index, day in enumerate(self._days):
            if self._cell(index).contains(QPointF(position)):
                return day
        return None

    def mouseMoveEvent(self, event):
        day = self._at(event.position())
        clickable = day is not None and bool(day.run_id)
        self.setCursor(Qt.CursorShape.PointingHandCursor if clickable else Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event):
        day = self._at(event.position())
        if event.button() == Qt.MouseButton.LeftButton and day is not None and day.run_id:
            self.dayClicked.emit(day.run_id)

    def event(self, event):
        if event.type() == QEvent.Type.ToolTip:
            day = self._at(event.pos())
            if day is not None:
                texts = {"success": tr("成功"), "partial": tr("部分完成"), "failed": tr("失败"),
                         "stopped": tr("已停止"), "none": tr("没有完整运行")}
                QToolTip.showText(event.globalPos(), f"{day.date:%m-%d} {texts.get(day.kind, '')}", self)
            return True
        return super().event(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        for index, day in enumerate(self._days):
            cell = self._cell(index)
            tone, mark = DAY.get(day.kind, DAY["none"])
            background, foreground = style.status_colors(tone)
            circle = QRectF(cell.center().x() - 14, 4, 28, 28)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(background)
            painter.drawEllipse(circle)
            style.glyph(painter, mark, circle.adjusted(7, 7, -7, -7), foreground, 1.6)
            painter.setPen(style.muted())
            painter.setFont(style.font(12))
            painter.drawText(QRectF(cell.left(), 38, cell.width(), 18), Qt.AlignmentFlag.AlignCenter,
                             tr("{day} 日").format(day=day.date.day))


class WeekGroup(SimpleCardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBorderRadius(8)
        self.titleLabel = StrongBodyLabel(self)
        self.hintLabel = secondary(CaptionLabel(self))
        self.strip = WeekStrip(self)
        head = QHBoxLayout()
        head.setSpacing(10)
        head.addWidget(self.titleLabel)
        head.addWidget(self.hintLabel, 0, Qt.AlignmentFlag.AlignBottom)
        head.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 10)
        layout.setSpacing(8)
        layout.addLayout(head)
        layout.addWidget(self.strip)

    def setDays(self, days):
        self.titleLabel.setText(tr("最近 7 天"))
        self.hintLabel.setText(tr("点击某天查看当次运行"))
        self.strip.setDays(days)


class AccountDetail(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view = QWidget()
        self.view.setObjectName("view")
        self.setWidget(self.view)
        self.view.setStyleSheet("#view{background: transparent}")
        self.header = HeaderCard(self.view)
        self.problem = NoticeStrip(self.view, kind="error")
        self.problem.hide()
        self.login = LoginGroup(self.view)
        self.plan = PlanGroup(self.view)
        self.week = WeekGroup(self.view)
        layout = QVBoxLayout(self.view)
        layout.setContentsMargins(0, 0, 12, 24)
        layout.setSpacing(14)
        for widget in (self.header, self.problem, self.login, self.plan, self.week):
            layout.addWidget(widget)
        layout.addStretch(1)

    def setAccount(self, info, *, active, current, busy, diffs, default_hour):
        self.header.setAccount(info, active=active, current=current, busy=busy)
        failed = active and info.status.kind in ("failed", "partial") and bool(info.status.reason)
        self.problem.setKind("error" if info.status.kind == "failed" else "warning", is_evernight())
        self.problem.setText(info.status.reason if failed else "")
        self.problem.setVisible(bool(failed))
        self.login.setAccount(info, active=active, default_hour=default_hour)
        self.plan.setVisible(active)
        self.week.setVisible(active)
        if active:
            self.plan.setAccount(info, diffs)
            self.week.setDays(info.week)
