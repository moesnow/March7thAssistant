"""总览页（原主页）：问候区、四张状态卡、完整运行清单、上次运行、快捷启动和建议检查。
数据和操作来自 app/overview_model.py，界面只负责显示。"""
import importlib.util
import os

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QBoxLayout, QFileDialog, QGridLayout, QVBoxLayout, QWidget
from qfluentwidgets import Action, FluentIcon as FIF, MenuAnimationType, RoundMenu, ScrollArea, qconfig

from module.localization import tr
from module.overview.labels import post_action_label

from .common.design_tokens import CARD_SPACING, PAGE_MARGIN
from .common.icon import UiIcon
from .overview.cards import ChecksCard, LastRunCard, PlanCard, PowerCard, ShortcutsCard, StatCard
from .overview.greeting import GreetingCard
from .overview.style import bar_success, brand, format_when, palette

WIDE_LAYOUT = 860
NAVIGATION_ACTIONS = {"configure", "view_reason", "view_result", "view_run"}


class OverviewInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("homeInterface")
        self.model = None
        self._snapshot = None
        self._evernight = False
        self._wide = None
        self.view = QWidget(self)
        self.view.setObjectName("view")
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("#homeInterface, #view { background: transparent; border: none; }")

        self.greeting = GreetingCard(self.view)
        self.powerCard = PowerCard(UiIcon.BATTERY_CHARGE, self.view)
        self.dailyCard = StatCard(UiIcon.CLIPBOARD_TASK, self.view)
        self.weeklyCard = StatCard(FIF.CALENDAR, self.view)
        self.scheduleCard = StatCard(FIF.DATE_TIME, self.view)
        self.planCard = PlanCard(self.view)
        self.sideWidget = QWidget(self.view)
        self.lastRunCard = LastRunCard(self.sideWidget)
        self.shortcutsCard = ShortcutsCard(self.sideWidget)
        self.checksCard = ChecksCard(self.sideWidget)

        self.vBox = QVBoxLayout(self.view)
        self.vBox.setContentsMargins(PAGE_MARGIN, 20, PAGE_MARGIN, 28)
        self.vBox.setSpacing(CARD_SPACING)
        self.vBox.addWidget(self.greeting)
        self.statsGrid = QGridLayout()
        self.statsGrid.setSpacing(CARD_SPACING)
        self.vBox.addLayout(self.statsGrid)
        self.sideLayout = QVBoxLayout(self.sideWidget)
        self.sideLayout.setContentsMargins(0, 0, 0, 0)
        self.sideLayout.setSpacing(CARD_SPACING)
        self.sideLayout.addWidget(self.lastRunCard)
        self.sideLayout.addWidget(self.shortcutsCard)
        self.sideLayout.addWidget(self.checksCard)
        self.sideLayout.addStretch(1)
        self.bottomLayout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.bottomLayout.setSpacing(CARD_SPACING)
        self.bottomLayout.addWidget(self.planCard, 1, Qt.AlignmentFlag.AlignTop)
        self.bottomLayout.addWidget(self.sideWidget, 0)
        self.vBox.addLayout(self.bottomLayout)
        self.vBox.addStretch(1)
        self._applyLayout(1000)

        self.greeting.actionTriggered.connect(self._onAction)
        self.greeting.menuRequested.connect(self._showGreetingMenu)
        for card in (self.powerCard, self.dailyCard, self.weeklyCard, self.scheduleCard, self.planCard,
                     self.lastRunCard, self.checksCard):
            card.linkActivated.connect(self._navigate)
        self.shortcutsCard.shortcutTriggered.connect(self._launchShortcut)
        self.shortcutsCard.editRequested.connect(self._editShortcuts)
        # 绑定方法：页面销毁后 PySide 会自动断开这条全局信号。
        qconfig.themeChanged.connect(self._onThemeChanged)
        self._retranslateStatic()

    # ---------- 与主窗口的接口 ----------
    def attachModel(self, model):
        self.model = model
        model.changed.connect(self.render)
        self.render(model.snapshot)

    def refreshBackendTasks(self):
        if self.model is not None:
            self.model.request_refresh()

    def retranslateUi(self):
        self._retranslateStatic()
        self.greeting.logoHint.retranslateUi()
        if self.model is not None:
            self.model.refresh()
        else:
            self._rerender()

    def setEvernightMode(self, active, animate=False):
        self._evernight = active
        self.greeting.setEvernightMode(active, animate=animate)
        self._rerender()

    def playLogoHint(self):
        self.greeting.playLogoHint()

    def dismissLogoHint(self):
        self.greeting.dismissLogoHint()

    # ---------- 显示 ----------
    def _retranslateStatic(self):
        self.powerCard.setTitle(tr("开拓力"))
        self.dailyCard.setTitle(tr("每日实训"))
        self.weeklyCard.setTitle(tr("本周周常"))
        self.scheduleCard.setTitle(tr("下次定时运行"))
        for card in (self.planCard, self.lastRunCard, self.shortcutsCard, self.checksCard):
            card.retranslateUi()

    def _onThemeChanged(self, *_):
        self._rerender()

    def _rerender(self):
        if self._snapshot is not None:
            self.render(self._snapshot)

    def render(self, snapshot):
        self._snapshot = snapshot
        if snapshot is None:
            return
        unavailable = set(snapshot.unavailable)
        evernight = self._evernight
        now = snapshot.now
        self.greeting.render(snapshot.greeting, show_mascot=snapshot.show_mascot, background=snapshot.background,
                             evernight=evernight)
        self.powerCard.setReading(snapshot.power, now, unavailable="power" in unavailable, evernight=evernight)
        self._renderDaily(snapshot.daily, now, "daily" in unavailable)
        self._renderWeekly(snapshot.weekly, "weekly" in unavailable)
        self._renderSchedule(snapshot.schedule, now, "schedule" in unavailable)
        self.planCard.setItems(snapshot.plan, unavailable="plan" in unavailable, evernight=evernight)
        self.lastRunCard.setRun(snapshot.last_run, now, unavailable="last_run" in unavailable, evernight=evernight)
        self.shortcutsCard.setShortcuts(snapshot.shortcuts, hidden=snapshot.shortcuts_hidden,
                                        unavailable="shortcuts" in unavailable,
                                        evernight=evernight, editable=self._canEditShortcuts())
        self.checksCard.setChecks(snapshot.checks, unavailable="checks" in unavailable, evernight=evernight)
        self.checksCard.setVisible(bool(snapshot.checks) or "checks" in unavailable)

    def _renderDaily(self, daily, now, unavailable):
        card = self.dailyCard
        if unavailable or daily is None:
            card.setValue("—", "/ 500")
            card.meter.setFraction(0, bar_success())
            card.setNote(tr("暂时读不到每日实训"))
            return
        target = daily.target or 500
        activity = daily.activity
        card.setValue("—" if activity is None else str(activity), f"/ {target}")
        color = bar_success() if daily.completed else brand(self._evernight)
        card.meter.setFraction((activity or 0) / target, color)
        if daily.completed:
            card.setNote(tr("{time} 完成").format(time=format_when(daily.completed_at, now)))
        elif activity is not None:
            card.setNote(tr("今天还差 {points} 活跃度").format(points=max(0, target - activity)))
        else:
            card.setNote(tr("今天还没有完成"))

    def _renderWeekly(self, weekly, unavailable):
        card = self.weeklyCard
        if unavailable or weekly is None:
            card.setValue("—")
            card.meter.setSegments((), palette().sky_blue)
            card.setNote(tr("暂时读不到周常进度"))
            return
        enabled = [item for item in weekly if item.enabled]
        done = [item for item in enabled if item.completed]
        card.setValue(str(len(done)), tr("/ {count} 项").format(count=len(enabled)))
        card.meter.setSegments([item.completed for item in enabled], palette().sky_blue)
        remaining = [item.name for item in enabled if not item.completed]
        if remaining:
            card.setNote(tr("剩余：{names}").format(names=" · ".join(remaining)))
        else:
            card.setNote(tr("本周的都完成了") if enabled else tr("没有开启每周任务"))

    def _renderSchedule(self, schedule, now, unavailable):
        card = self.scheduleCard
        card.meter.setBlank()
        if unavailable:
            card.setValue("—")
            card.setNote(tr("暂时读不到定时计划"))
            return
        if schedule is None:
            card.setValue(tr("未安排"))
            card.setNote(tr("还没有定时运行"), tr("添加定时"), "run:schedule", evernight=self._evernight)
            return
        card.setValue(format_when(schedule.at, now))
        steps = list(schedule.names)
        if schedule.post_action and schedule.post_action != "None":
            steps.append(post_action_label(schedule.post_action))
        card.setNote(" → ".join(steps) + " ·", tr("管理定时"), "run:schedule", evernight=self._evernight)

    # ---------- 布局 ----------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._applyLayout(self.viewport().width())

    def _applyLayout(self, width):
        wide = width >= WIDE_LAYOUT
        if wide != self._wide:
            self._wide = wide
            cards = (self.powerCard, self.dailyCard, self.weeklyCard, self.scheduleCard)
            for card in cards:
                self.statsGrid.removeWidget(card)
            columns = 4 if wide else 2
            for index, card in enumerate(cards):
                self.statsGrid.addWidget(card, index // columns, index % columns)
            for column in range(4):
                self.statsGrid.setColumnStretch(column, 1 if column < columns else 0)
            # 窄窗口里上下排列：上次运行、快捷启动这些短卡片放在前面，完整运行清单在后。
            self.bottomLayout.setDirection(QBoxLayout.Direction.LeftToRight if wide
                                           else QBoxLayout.Direction.BottomToTop)
        if wide:
            self.sideWidget.setFixedWidth(max(300, min(380, int((width - 2 * PAGE_MARGIN) * 0.36))))
        else:
            self.sideWidget.setMinimumWidth(0)
            self.sideWidget.setMaximumWidth(16777215)

    # ---------- 操作 ----------
    def _navigate(self, link):
        navigate = getattr(self.window(), "navigate", None)
        if link and callable(navigate):
            navigate(link)

    def _onAction(self, button, widget):
        if button.id == "choose_task":
            self._showTaskMenu(widget)
            return
        if button.id in NAVIGATION_ACTIONS:
            self._navigate(button.link)
            return
        model = self.model
        if model is None:
            return
        if button.id in ("start_full", "continue"):
            model.start_full()
        elif button.id == "start_all":
            model.window.runController.start_all()
        elif button.id == "stop":
            model.stop()
        elif button.id == "toggle_pause":
            model.toggle_pause()
        elif button.id == "start_task" and button.target:
            model.start_task(button.target)
        elif button.id == "retry_step" and button.target:
            model.retry_step(button.target)
        model.request_refresh()

    def _showTaskMenu(self, widget):
        from module.config import cfg
        from utils.tasks import supported_tasks

        menu = RoundMenu(parent=self)
        for task_id, name in supported_tasks(cfg).items():
            menu.addAction(Action(tr(name), triggered=lambda _=False, task=task_id: self._startTask(task)))
        menu.exec(widget.mapToGlobal(QPoint(0, widget.height() + 4)), aniType=MenuAnimationType.DROP_DOWN)

    def _startTask(self, task_id):
        if self.model is not None:
            self.model.start_task(task_id)
            self.model.request_refresh()

    def _launchShortcut(self, action_id):
        if self.model is not None:
            self.model.launch_shortcut(action_id)

    @staticmethod
    def _canEditShortcuts():
        return importlib.util.find_spec("app.overview.shortcut_dialog") is not None

    def _editShortcuts(self):
        if not self._canEditShortcuts():
            return
        from .overview.shortcut_dialog import ShortcutEditDialog
        if ShortcutEditDialog(self.window()).exec() and self.model is not None:
            self.model.request_refresh()

    def _showGreetingMenu(self, position):
        snapshot = self._snapshot
        menu = RoundMenu(parent=self)
        menu.addAction(Action(FIF.PHOTO, tr("更换问候区背景"), triggered=self._chooseBackground))
        if snapshot is not None and snapshot.background:
            menu.addAction(Action(FIF.CANCEL, tr("恢复默认背景"), triggered=lambda: self._setConfig("banner_path", "")))
        menu.addSeparator()
        shown = snapshot.show_mascot if snapshot is not None else True
        menu.addAction(Action(FIF.HIDE if shown else FIF.VIEW, tr("隐藏 Q 版小人") if shown else tr("显示 Q 版小人"),
                              triggered=lambda: self._setConfig("overview_show_mascot", not shown)))
        menu.exec(position)

    def _chooseBackground(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("选择图片"), os.getcwd(),
                                              "Images (*.png *.jpg *.jpeg *.bmp *.webp);;All Files (*)")
        if path:
            self._setConfig("banner_path", path)

    def _setConfig(self, key, value):
        from module.config import cfg
        cfg.set_value(key, value)
        if self.model is not None:
            self.model.refresh()
