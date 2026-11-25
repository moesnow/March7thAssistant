"""任务：左侧按每天、每周、按月分组的任务列表，右侧是所选任务的页头、估算和设置卡。

卡片由 app.content 按任务建造，状态和操作来自 app.content.task_model.TaskModel。
"""
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, ExpandSettingCard, ScrollArea, TitleLabel, qconfig

from app.content import PageHost, build_page
from app.content.base import card_for
from app.content.visibility import setting_visible
from app.content.task_model import TaskModel
from module.localization import tr
from module.logger import log
from app.content.account_model import AccountModel
from .accounts.editing import EditingAccount
from .pages.common import NoticeStrip, SectionView, is_evernight, secondary, shared
from .pages.decorations import CardDecorations
from .pages.power_order import PowerOrderView
from .pages.tasks import ChecksCard, TaskHeader, TaskListPanel


class TaskPage(ScrollArea):
    def __init__(self, interface, task, parent=None):
        super().__init__(parent or interface)
        self.interface, self.task = interface, task
        window, model = interface.window_, interface.model
        self.setWidgetResizable(True)
        self.enableTransparentBackground()
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view = QWidget()
        self.view.setObjectName("view")
        self.setWidget(self.view)
        self.view.setStyleSheet("#view{background: transparent}")
        self.vBoxLayout = QVBoxLayout(self.view)
        self.vBoxLayout.setContentsMargins(0, 0, 12, 24)
        self.vBoxLayout.setSpacing(14)
        self.header = TaskHeader(task, model, window, self.view)
        self.vBoxLayout.addWidget(self.header)
        self.notice = NoticeStrip(self.view, kind="warning")
        self.notice.setAction(tr("更新策略"))
        self.notice.actionClicked.connect(model.update_strategy)
        self.notice.hide()
        self.vBoxLayout.addWidget(self.notice)
        self.estimate = NoticeStrip(self.view, kind="info")
        self.estimate.hide()
        self.vBoxLayout.addWidget(self.estimate)
        self.host = PageHost(window, self.view)
        self.views = {}
        self.checks = self.order = None
        for section in build_page(task.id, self.host):
            if section.id == "header" and not section.cards:
                continue
            if (task.id, section.id) == ("power", "instances"):
                view = self.order = PowerOrderView(section, model.config, self.view)
            else:
                view = SectionView(section, self.view)
            if section.checks:
                self.checks = ChecksCard(model, view)
                view.addExtra(self.checks)
            self.views[section.id] = view
            self.vBoxLayout.addWidget(view)
        self.vBoxLayout.addStretch(1)
        self.decorations = CardDecorations(self.host, window)
        self.host.visibilityChanged.connect(self.refreshSections)
        self.refreshSections()
        self.refresh()

    def refreshSections(self):
        for view in self.views.values():
            view.refresh()

    def refresh(self):
        model = self.interface.model
        task_id = self.task.id
        try:
            self.header.refresh()
            notice = model.notice(task_id)
            self.notice.setKind("warning", is_evernight())
            self.notice.setText(notice)
            self.notice.setVisible(bool(notice))
            estimate = model.estimate(task_id)
            self.estimate.setKind("info", is_evernight())
            self.estimate.setVisible(estimate is not None)
            if estimate is not None:
                self.estimate.setText(estimate.text)
                self.estimate.setRatio(estimate.ratio)
            if self.checks is not None:
                self.checks.refresh()
            if self.order is not None:
                self.order.refreshOrder()
        except Exception as exc:
            log.warning(f"刷新任务页失败：{task_id} {type(exc).__name__}: {exc}")


class TaskInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("taskInterface")
        self.window_ = parent
        self.model = shared(parent, "taskModel", lambda: TaskModel(parent))
        self.titleLabel = TitleLabel(tr("任务"), self)
        self.subtitleLabel = secondary(BodyLabel(tr("打开开关的任务会加入「完整运行」，每项也可以单独立即运行"), self))
        self.accountModel = shared(parent, "accountModel", lambda: AccountModel(parent))
        self.editing = EditingAccount(self.accountModel, parent, self)
        title = QHBoxLayout()
        title.setContentsMargins(0, 0, 12, 0)
        title.setSpacing(16)
        title.addWidget(self.titleLabel)
        title.addWidget(self.subtitleLabel, 1, Qt.AlignmentFlag.AlignBottom)
        title.addWidget(self.editing, 0, Qt.AlignmentFlag.AlignVCenter)
        self.body = QHBoxLayout()
        self.body.setSpacing(16)
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(20, 14, 12, 0)
        self.vBoxLayout.setSpacing(14)
        self.vBoxLayout.addLayout(title)
        self.vBoxLayout.addLayout(self.body, 1)
        self.listPanel = None
        self.stack = None
        self.pages = {}
        self._build()
        self.model.changed.connect(self.refresh)
        qconfig.themeChanged.connect(self._restyle)
        qconfig.themeColorChanged.connect(self._restyle)

    def _build(self):
        stack = QStackedWidget(self)
        pages = {}
        try:
            for task in self.model.tasks():
                page = TaskPage(self, task, stack)
                pages[task.id] = page
                stack.addWidget(page)
            panel = TaskListPanel(self.model, self)
        except Exception:
            stack.deleteLater()
            raise
        for old in (self.listPanel, self.stack):
            if old is not None:
                self.body.removeWidget(old)
                old.hide()
                old.deleteLater()
        self.listPanel, self.stack, self.pages = panel, stack, pages
        panel.setFixedWidth(256)
        panel.currentChanged.connect(self.showTask)
        self.body.addWidget(self.listPanel)
        self.body.addWidget(self.stack, 1)
        first = next(iter(self.pages), None)
        if first:
            self.showTask(first)

    def rebuild(self, *, account_changed=False):
        """切换语言后重建列表和各任务页，保留所选任务、滚动位置和展开状态。"""
        state = self.captureViewState()
        if account_changed:
            state.pop("cards", None)
        self.titleLabel.setText(tr("任务"))
        self.subtitleLabel.setText(tr("打开开关的任务会加入「完整运行」，每项也可以单独立即运行"))
        self.editing.refresh()
        self._build()
        self.restoreViewState(state)

    def retranslateUi(self):
        self.rebuild()

    def refresh(self):
        self.listPanel.refresh()
        for page in self.pages.values():
            page.refresh()

    def _restyle(self, *_):
        for page in self.pages.values():
            page.header.restyle()
            page.refresh()
        self.update()

    def currentTask(self):
        return self.listPanel.current() if self.listPanel else None

    def showTask(self, task_id):
        if task_id not in self.pages:
            return False
        self.listPanel.setCurrent(task_id)
        self.stack.setCurrentWidget(self.pages[task_id])
        return True

    def _target(self, page, setting):
        widget = card_for(setting, page.host)
        if widget is not None:
            return widget
        if setting.role == "check" and page.checks is not None:
            return page.checks.boxes.get(setting.id, page.checks)
        if setting.id == "currencywarsStrategyCard":
            return page.notice
        if setting.id in ("currencywarsPresetCard", "fightPresetCard"):
            return page.header.presetButton
        if setting.role in ("header", "state"):
            return page.header
        view = page.views.get(setting.section)
        return view if view is not None else page.header

    def locate(self, setting):
        if not setting_visible(setting):
            return False
        page = self.pages.get(setting.page)
        if page is None or not self.showTask(setting.page):
            return False
        widget = self._target(page, setting)
        if widget is None or widget.isHidden():
            return False
        parent = widget.parentWidget()
        while parent is not None and parent is not page.view:
            if isinstance(parent, ExpandSettingCard) and not parent.isExpand:
                parent.setExpand(True)
                parent.expandAni.setCurrentTime(parent.expandAni.duration())
            if isinstance(parent, SectionView):
                if parent.isHidden():
                    return False
                if not parent.isExpanded():
                    parent.setExpanded(True)
            parent = parent.parentWidget()
        QTimer.singleShot(0, widget, lambda: self._scrollTo(page, widget))
        return True

    @staticmethod
    def _scrollTo(page, widget):
        from app.navigation import highlight
        try:
            page.view.layout().activate()
            target = getattr(widget, "card", widget) if isinstance(widget, ExpandSettingCard) else widget
            top = target.mapTo(page.view, QPoint(0, 0)).y()
            viewport = page.viewport().height()
            page.verticalScrollBar().setValue(max(0, top - max(0, (viewport - target.height()) // 2)))
            highlight(target)
        except RuntimeError:
            pass

    def captureViewState(self):
        state = {"task": self.currentTask(), "scroll": {}, "sections": {}, "cards": {}}
        for task_id, page in self.pages.items():
            state["scroll"][task_id] = page.verticalScrollBar().value()
            state["sections"][task_id] = {key: view.isExpanded() for key, view in page.views.items()}
            try:
                state["cards"][task_id] = page.host.capture_card_state()
            except Exception:
                pass
        return state

    def restoreViewState(self, state):
        for task_id, page in self.pages.items():
            for key, expanded in state.get("sections", {}).get(task_id, {}).items():
                if key in page.views and page.views[key].header is not None:
                    page.views[key].setExpanded(expanded)
            if task_id in state.get("cards", {}):
                try:
                    page.host.restore_card_state(state["cards"][task_id])
                except Exception:
                    pass
        if state.get("task") in self.pages:
            self.showTask(state["task"])
        scroll = state.get("scroll", {})
        QTimer.singleShot(0, self.stack, lambda: [page.verticalScrollBar().setValue(scroll.get(key, 0))
                                      for key, page in self.pages.items()])
