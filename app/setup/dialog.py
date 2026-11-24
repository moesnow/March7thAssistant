"""首次配置向导：盖在主窗口上的一块面板，左侧步骤栏，右侧一次一步。

不用模态对话框：标题栏要能照常拖动、最小化和关闭，所以只盖住标题栏以下的部分。
"""
from PySide6.QtCore import QEasingCurve, QEvent, QRectF, QSize, QThread, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import (CaptionLabel, FluentIcon, LineEdit, PrimaryPushButton, PushButton, TransparentToolButton,
                            isDarkTheme, qconfig)

from app.overview.style import animations_enabled
from app.pages.common import Divider, border_color, is_evernight, secondary, style_primary
from module.localization import tr
from .rail import RADIUS, StepRail
from .steps import DonePage, GameStep, NotifyStep, RunModeStep, ScheduleStep, TasksStep

MAX_WIDTH, MAX_HEIGHT = 1040, 680
SHADOW = 24


class TitleShade(QWidget):
    """标题栏那一条只压暗，鼠标照常落到标题栏上。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.opacity = 1.0

    def paintEvent(self, event):
        QPainter(self).fillRect(self.rect(), shade(self.opacity))


def shade(opacity):
    return QColor(0, 0, 0, int((150 if isDarkTheme() else 105) * opacity))


class Panel(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(border_color(), 1))
        painter.setBrush(QColor(43, 43, 43) if isDarkTheme() else QColor(252, 252, 253))
        painter.drawRoundedRect(rect, RADIUS, RADIUS)


class SetupDialog(QWidget):
    closed = Signal(bool)         # True 走完，False 中途关闭
    runRequested = Signal()
    linkRequested = Signal(str)

    def __init__(self, model, parent):
        super().__init__(parent)
        self.model = model
        self.window_ = parent
        self._done = False
        # 已经保存过的步骤数。重新打开时每一步都有现成的设置，可以直接跳。
        self._passed = 0 if model.first_time() else len(model.STEPS)
        self._index = -1
        self._progress = 1.0
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.titleShade = TitleShade(parent)
        self.titleShade.hide()
        self.panel = Panel(self)
        self.rail = StepRail(len(model.STEPS), self.panel)
        self.rail.stepClicked.connect(self.goTo)
        self.stack = QStackedWidget(self.panel)
        self.steps = [RunModeStep(self), GameStep(self), TasksStep(self), ScheduleStep(self), NotifyStep(self)]
        self.donePage = DonePage(self)
        self.donePage.editRequested.connect(self.goTo)
        self.donePage.linkClicked.connect(lambda link: self._finish(link=link))
        for page in (*self.steps, self.donePage):
            self.stack.addWidget(page)
            page.poseChanged.connect(self._refreshPose)
            page.nextChanged.connect(self._refreshFooter)
        self.closeButton = TransparentToolButton(FluentIcon.CLOSE, self.panel)
        self.closeButton.setFixedSize(32, 32)
        self.closeButton.setIconSize(QSize(12, 12))
        self.closeButton.setToolTip(tr("以后再设置"))
        self.closeButton.setAccessibleName(tr("以后再设置"))
        self.closeButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.closeButton.clicked.connect(self.dismiss)
        self.countLabel = secondary(CaptionLabel(self.panel))
        self.backButton = PushButton(tr("上一步"), self.panel)
        self.backButton.clicked.connect(self.back)
        self.runButton = PrimaryPushButton(FluentIcon.PLAY, tr("开始完整运行"), self.panel)
        self.runButton.clicked.connect(lambda: self._finish(run=True))
        self.nextButton = PrimaryPushButton(self.panel)
        self.nextButton.clicked.connect(self.next)
        self.doneButton = PushButton(tr("完成"), self.panel)
        self.doneButton.clicked.connect(self._finish)
        for button in (self.backButton, self.nextButton, self.doneButton):
            button.setMinimumWidth(96)
        footer = QHBoxLayout()
        footer.setContentsMargins(28, 12, 28, 14)
        footer.setSpacing(8)
        footer.addWidget(self.countLabel)
        footer.addStretch(1)
        for button in (self.backButton, self.nextButton, self.doneButton, self.runButton):
            footer.addWidget(button)
        main = QVBoxLayout()
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        main.addWidget(self.stack, 1)
        main.addWidget(Divider(self.panel))
        main.addLayout(footer)
        layout = QHBoxLayout(self.panel)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        layout.addWidget(self.rail)
        layout.addLayout(main, 1)
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(180)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self._advance)
        if model.first_time():
            self.rail.setHeading(tr("欢迎使用三月七小助手"), tr("花 1 分钟，设好每天要做的事"))
        else:
            self.rail.setHeading(tr("首次配置向导"), tr("每一步点「下一步」时保存"))
        model.changed.connect(self._refreshRail)
        qconfig.themeChanged.connect(self._restyle)
        qconfig.themeColorChanged.connect(self._restyle)
        parent.installEventFilter(self)
        self._restyle()
        self.hide()

    # ---------- 打开和关闭 ----------
    def open(self):
        self._fit()
        self.titleShade.show()
        self.titleShade.raise_()
        self.show()
        self.raise_()
        self.goTo(0)
        self.setFocus()
        if animations_enabled():
            self.animation.start()
        else:
            self._advance(1.0)

    def dismiss(self):
        """中途关闭：已经保存的步骤保留。"""
        if self.currentStep() is self.donePage:
            self._finish()
        elif self._close():
            self.model.dismiss()
            self.closed.emit(False)

    def _finish(self, *_, run=False, link=""):
        if not self._close():
            return
        self.model.finish()
        self.closed.emit(True)
        if run:
            self.runRequested.emit()
        elif link:
            self.linkRequested.emit(link)

    def _close(self):
        if self._done:
            return False
        self._done = True
        self.animation.stop()
        self.window_.removeEventFilter(self)
        self.titleShade.hide()
        self.titleShade.deleteLater()
        self.hide()
        # 按钮的点击事件还没处理完，等它返回再删除。
        QTimer.singleShot(0, self, self._dispose)
        return True

    def _dispose(self):
        """设备列表和环境检查可能还在后台跑，等它们结束再删除，否则程序会跟着退出。"""
        if any(thread.isRunning() for thread in self.findChildren(QThread)):
            QTimer.singleShot(200, self, self._dispose)
        else:
            self.deleteLater()

    @property
    def runController(self):
        """沿用设置页的卡片要通过它判断有没有任务在运行。"""
        return getattr(self.window_, "runController", None)

    # ---------- 步骤 ----------
    def currentIndex(self):
        return self._index

    def currentStep(self):
        return self.stack.currentWidget()

    def goTo(self, index):
        """index 等于步骤数时是完成页。"""
        self._index = index
        page = self.steps[index] if index < len(self.steps) else self.donePage
        page.showError("")
        page.enter()
        page.scroll.verticalScrollBar().setValue(0)
        self.stack.setCurrentWidget(page)
        self._refreshRail()
        self._refreshPose()
        self._refreshFooter()

    def next(self):
        page = self.currentStep()
        if page is self.donePage:
            self._finish()
            return
        ok, text = page.leave()
        if not ok:
            page.showError(text)
            return
        self._passed = max(self._passed, self._index + 1)
        self.goTo(self._index + 1)

    def back(self):
        if self._index > 0:
            self.goTo(self._index - 1)

    def _refreshRail(self):
        if self._done:
            return
        for index, step in enumerate(self.model.STEPS):
            title = {"run_mode": tr("游戏在哪里运行"), "game": self.steps[1].title(), "tasks": tr("每天做什么"),
                     "schedule": tr("什么时候运行"), "notify": tr("通知我")}[step]
            if index == self._index:
                state, note, kind = "current", "", "neutral"
            elif index < self._passed:
                note, kind = self.model.step_text(step)
                state = "done"
            else:
                state, note, kind = "todo", "", "neutral"
            if not note:
                note = {"run_mode": tr("电脑、云游戏或安卓设备"), "game": tr("安装位置或连接方式"), "tasks": tr("选择要自动完成的内容"),
                        "schedule": tr("定时与完成后操作"), "notify": tr("可跳过")}[step]
            self.rail.rows[index].setStep(title, note, state, kind)

    def _refreshPose(self):
        page = self.currentStep()
        if page is not None and not self._done:
            self.rail.setPose(page.pose(), bounce=self.isVisible())

    def _refreshFooter(self):
        page = self.currentStep()
        done = page is self.donePage
        total = len(self.steps)
        self.countLabel.setText("" if done else tr("第 {index} 步，共 {total} 步").format(index=self._index + 1, total=total))
        self.backButton.setVisible(0 < self._index <= total)
        self.nextButton.setVisible(not done)
        self.doneButton.setVisible(done)
        self.runButton.setVisible(done)
        if not done and page is not None:
            self.nextButton.setText(page.nextText())
            self.nextButton.setEnabled(page.nextEnabled())

    def _restyle(self, *_):
        evernight = is_evernight()
        for button in (self.nextButton, self.runButton):
            style_primary(button, evernight)
        for page in (*self.steps, self.donePage):
            if page is self.currentStep() and self._index >= 0:
                page.enter()
        self.update()

    # ---------- 布局和绘制 ----------
    def _titleHeight(self):
        bar = getattr(self.window_, "titleBar", None)
        return bar.height() if bar is not None else 0

    def _fit(self):
        top = self._titleHeight()
        width, height = self.window_.width(), self.window_.height()
        self.titleShade.setGeometry(0, 0, width, top)
        self.setGeometry(0, top, width, max(0, height - top))
        self._placePanel()

    def _placePanel(self):
        width = min(MAX_WIDTH, max(640, self.width() - 64))
        height = min(MAX_HEIGHT, max(420, self.height() - 32))
        # 标题栏那一条也算上，面板看起来在窗口正中偏上。
        y = max(8, (self.height() - height) // 2 - (4 if self.height() - height > 40 else 0))
        offset = round((1.0 - self._progress) * 14)
        self.panel.setGeometry((self.width() - width) // 2, y + offset, width, height)
        self.closeButton.move(width - 32 - 12, 12)
        self.closeButton.raise_()

    def _advance(self, value):
        self._progress = float(value)
        self.titleShade.opacity = self._progress
        self.titleShade.update()
        self._placePanel()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._placePanel()

    def eventFilter(self, watched, event):
        if watched is self.window_ and event.type() in (QEvent.Type.Resize, QEvent.Type.WindowStateChange) and not self._done:
            QTimer.singleShot(0, self, self._fit)
        return False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), shade(self._progress))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        rect = QRectF(self.panel.geometry())
        for index in range(SHADOW, 0, -2):
            painter.setBrush(QColor(0, 0, 0, int(4 * self._progress)))
            painter.drawRoundedRect(rect.adjusted(-index, -index + 10, index, index + 10), RADIUS + index, RADIUS + index)

    # ---------- 键盘 ----------
    def focusNextPrevChild(self, forward):
        """Tab 只在向导里转，不会跑到盖住的页面上。"""
        chain = [w for w in self.findChildren(QWidget)
                 if w.isVisibleTo(self) and w.isEnabled() and w.focusPolicy() & Qt.FocusPolicy.TabFocus
                 and w.focusProxy() is None]
        if not chain:
            return True
        # 按从左到右、从上到下的位置排，和看到的顺序一致。
        chain.sort(key=lambda w: (w.mapTo(self, w.rect().topLeft()).y() // 24, w.mapTo(self, w.rect().topLeft()).x()))
        current = self.focusWidget()
        index = chain.index(current) if current in chain else -1 if forward else 0
        chain[(index + (1 if forward else -1)) % len(chain)].setFocus(
            Qt.FocusReason.TabFocusReason if forward else Qt.FocusReason.BacktabFocusReason)
        return True

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.dismiss()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            focused = self.focusWidget()
            if isinstance(focused, (QAbstractButton, LineEdit)) and focused is not self:
                event.ignore()
                return
            self.next()
        else:
            event.accept()

    def mousePressEvent(self, event):
        event.accept()

    def wheelEvent(self, event):
        event.accept()
