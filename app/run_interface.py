"""运行：当前运行、运行记录、定时计划。进程、定时和热键由 app.content.run_controller 负责，这里只显示和转发操作。"""
import sys

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, InfoBar, SegmentedWidget, TitleLabel, qconfig

from app.overview.style import format_duration, format_when
from module.localization import tr
from utils.desktop import open_log_folder
from .pages.common import refresh_on_restore, secondary, shared
from .run.cards import CurrentRunCard, run_text
from .run.history import HistoryPage
from .run.log_view import LogPanel
from .run.schedule import SchedulePage

PAGES = ("current", "history", "schedule")


class CurrentPage(QWidget):
    def __init__(self, controller, window, parent=None):
        super().__init__(parent)
        self.controller, self.window_ = controller, window
        self.card = CurrentRunCard(self)
        self.log = LogPanel(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(self.card)
        layout.addWidget(self.log, 1)
        self.card.startClicked.connect(controller.start_full)
        self.card.startAllClicked.connect(controller.start_all)
        self.card.pauseClicked.connect(controller.toggle_pause)
        self.card.stopClicked.connect(controller.stop)
        self.card.skipClicked.connect(controller.skip_account)
        self.card.overlayToggled.connect(controller.set_overlay)
        self.card.finishToggled.connect(controller.set_finish_skipped)
        self.card.footLink.clicked.connect(self._openLast)
        self.log.clearRequested.connect(controller.clear_log)
        self.log.folderRequested.connect(open_log_folder)
        controller.changed.connect(self._changed)
        controller.logAppended.connect(self.log.append)
        controller.logCleared.connect(self.log.clear)
        # 每秒只更新已运行时间，不读文件。
        self._clock = QTimer(self)
        self._clock.setInterval(1000)
        self._clock.timeout.connect(self._tick)
        self._idle_link = ""
        self.retranslateUi()
        self.log.setEntries(controller.log_entries())

    def retranslateUi(self):
        windows = sys.platform == "win32"
        self.card.retranslateUi(pause_key=self.controller.pause_key() if windows else "",
                                stop_key=self.controller.stop_key() if windows else "")
        self.log.retranslateUi()
        self.log.setEmptyText(tr("任务运行时，日志会显示在这里"))
        self.refresh()

    def restyle(self):
        self.card.restyle()
        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._clock.stop()

    def _changed(self):
        if self.isVisible() and not self.window().isMinimized():
            self.refresh()

    def _tick(self):
        if self.window().isMinimized():
            return
        if self._counting_down:
            self.refresh()
        else:
            self.card.setElapsed(self.controller.elapsed())

    def refresh(self):
        view = self.controller.view()
        self._counting_down = view.countdown is not None
        self.card.setOverlay(self.controller.overlay_enabled(), sys.platform == "win32")
        running = view.state != "idle"
        self._idle_link = ""
        if running:
            self.card.setRunning(view)
            if self.isVisible() and not self._clock.isActive():
                self._clock.start()
        else:
            if view.countdown is not None and self.isVisible():
                self._clock.start()
            else:
                self._clock.stop()
            self._setIdle(view)
        self.log.setRunning(running)

    def _setIdle(self, view):
        last = view.last
        text, link = "", ""
        if view.countdown is not None:
            text = tr("完成后操作：{action}，{seconds} 秒后执行").format(action=view.finish_text, seconds=view.countdown)
            link = tr("取消")
        elif last is not None:
            parts = [last.title, run_text(last.status), format_when(last.started_at, self.controller.now())]
            if last.seconds:
                parts.append(tr("用时 {time}").format(time=format_duration(last.seconds)))
            text = tr("上次：{detail}").format(detail=" · ".join(filter(None, parts)))
            link = tr("查看记录")
            self._idle_link = last.id
        self.card.setIdle(text, link, can_start=view.can_start, can_start_all=view.can_start_all)

    def _openLast(self):
        view = self.controller.view()
        if view.state != "idle":
            return
        if view.countdown is not None:
            self.controller.cancel_finish()
        elif self._idle_link:
            self.window_.navigate(f"run:{self._idle_link}")


class RunInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 沿用原来的对象名，侧栏路由和链接不变。
        self.setObjectName("logInterface")
        from app.content.run_controller import RunController
        from app.content.run_models import RunHistory, ScheduleModel
        self.window_ = parent
        self.controller = shared(parent, "runController", lambda: RunController(parent))
        self.history = shared(parent, "runHistory", lambda: RunHistory(parent))
        self.schedule = shared(parent, "scheduleModel", lambda: ScheduleModel(parent))
        self.titleLabel = TitleLabel(self)
        self.segment = SegmentedWidget(self)
        for key in PAGES:
            self.segment.addItem(key, "", onClick=lambda _=False, k=key: self.showPage(k))
        self.nextLabel = secondary(BodyLabel(self))
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 12, 0)
        head.setSpacing(18)
        head.addWidget(self.titleLabel)
        head.addWidget(self.segment, 0, Qt.AlignmentFlag.AlignVCenter)
        head.addStretch(1)
        head.addWidget(self.nextLabel, 0, Qt.AlignmentFlag.AlignVCenter)
        self.currentPage = CurrentPage(self.controller, parent, self)
        self.historyPage = HistoryPage(self.history, self)
        self.schedulePage = SchedulePage(self.schedule, self)
        self.schedulePage.addClicked.connect(lambda: self._edit(None))
        self.schedulePage.editClicked.connect(self._edit)
        self.schedulePage.runClicked.connect(self._runSchedule)
        self.stack = QStackedWidget(self)
        for page in (self.currentPage, self.historyPage, self.schedulePage):
            self.stack.addWidget(page)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 12, 20)
        layout.setSpacing(14)
        layout.addLayout(head)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 12, 0)
        body.addWidget(self.stack)
        layout.addLayout(body, 1)
        self.schedule.changed.connect(self._refreshHeader)
        qconfig.themeChanged.connect(self._restyle)
        qconfig.themeColorChanged.connect(self._restyle)
        self._setTexts()
        self.showPage("current")
        refresh_on_restore(self, parent, self._resume)

    def _resume(self):
        page = self.stack.currentWidget()
        page.refresh()
        if page is self.currentPage:
            page.log.resume()

    def _setTexts(self):
        self.titleLabel.setText(tr("运行"))
        for key, text in (("current", tr("当前运行")), ("history", tr("运行记录")), ("schedule", tr("定时计划"))):
            self.segment.items[key].setText(text)
        self._refreshHeader()

    def _refreshHeader(self):
        count = self.schedule.enabled_count()
        self.segment.items["schedule"].setText(f"{tr('定时计划')} {count}" if count else tr("定时计划"))
        self.segment.items["schedule"].adjustSize()
        self.nextLabel.setText(self.schedule.next_text())

    def retranslateUi(self):
        self._setTexts()
        for page in (self.currentPage, self.historyPage, self.schedulePage):
            page.retranslateUi()

    def _restyle(self, *_):
        self.currentPage.restyle()
        self.update()

    def page(self):
        return PAGES[self.stack.currentIndex()]

    def showPage(self, key):
        if key not in PAGES:
            return False
        self.segment.setCurrentItem(key)
        self.stack.setCurrentIndex(PAGES.index(key))
        return True

    def showRun(self, run_id):
        """链接 run:<运行编号>。"""
        self.showPage("history")
        return self.historyPage.select(run_id)

    def showSchedule(self, item_id=None):
        """链接 run:schedule。"""
        self.showPage("schedule")
        return item_id is None or self.schedulePage.reveal(item_id)

    def _edit(self, item_id):
        self.schedule.edit(item_id, self.window_)

    def _runSchedule(self, item_id):
        outcome = self.schedule.run_now(item_id)
        if outcome.ok:
            self.showPage("current")
        elif outcome.text:
            InfoBar.warning(tr("现在无法运行"), outcome.text, duration=4000, parent=self.window_)
