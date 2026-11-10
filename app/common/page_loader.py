"""Cooperative page construction. Widgets always stay on the GUI thread.

A timer budget is cooperative, not preemptive: each builder must yield between
small, internally consistent units. Partially built pages are never published.
"""
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field
from time import perf_counter
import traceback

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

from module.localization import tr
from module.logger import log


class PendingPage(QWidget):
    retryRequested = Signal()

    def __init__(self, route, parent=None):
        super().__init__(parent)
        self.setObjectName(route)
        self.failed = False
        layout = QVBoxLayout(self)
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.retryButton = QPushButton(self)
        self.retryButton.clicked.connect(self.retryRequested)
        layout.addStretch()
        layout.addWidget(self.label)
        layout.addWidget(self.retryButton, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        self.retranslateUi()

    def retranslateUi(self):
        self.label.setText(tr('加载失败') if self.failed else tr('正在加载...'))
        self.retryButton.setText(tr('重试'))
        self.retryButton.setVisible(self.failed)

    def setFailed(self, failed):
        self.failed = failed
        self.retranslateUi()


@dataclass
class PageJob:
    factory: object
    placeholder: PendingPage
    page: QWidget | None = None
    iterator: object = None
    complete: bool = False
    callbacks: list = field(default_factory=list)


class PageLoader(QObject):
    """One cancellable queue, shared by preload and foreground navigation."""
    pageReady = Signal(str)
    allReady = Signal()

    def __init__(self, parent, publish, can_publish, context, budget_ms=6, interval_ms=10):
        super().__init__(parent)
        self.jobs = OrderedDict()
        self.publish = publish
        self.can_publish = can_publish
        self.context = context
        self.snapshot = deepcopy(context())
        self.budget_ms = budget_ms
        self.interval_ms = interval_ms
        self.stopped = False
        self.started = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._step)
        QApplication.instance().aboutToQuit.connect(self.stop)

    @property
    def is_idle(self):
        return not self.jobs

    def add(self, route, factory, placeholder):
        self.jobs[route] = PageJob(factory, placeholder)
        placeholder.retryRequested.connect(lambda: self.request(route, retry=True))

    def start(self, delay=250):
        if self.stopped or self.started:
            return
        self.started = True
        self.timer.start(delay)

    def request(self, route, callback=None, retry=False):
        if self.stopped or route not in self.jobs:
            return
        job = self.jobs[route]
        if callback is not None:
            job.callbacks.append(callback)
        if retry:
            job.placeholder.setFailed(False)
        self.jobs.move_to_end(route, last=False)
        self.started = True
        self.timer.start(0)

    def _discard(self, job):
        try:
            if job.iterator is not None and hasattr(job.iterator, 'close'):
                job.iterator.close()
        except Exception:
            log.error(f'Page builder cancellation failed\n{traceback.format_exc()}')
        finally:
            job.iterator = None
            if job.page is not None:
                try:
                    if hasattr(job.page, 'dispose_incomplete'):
                        job.page.dispose_incomplete()
                    job.page.hide()
                    job.page.deleteLater()
                except RuntimeError:
                    pass  # The owner may already have destroyed its Qt children.
            job.page = None
            job.complete = False

    def invalidate(self):
        """Keep navigation/callbacks, but discard every unpublished old generation."""
        for job in self.jobs.values():
            self._discard(job)
            job.placeholder.retranslateUi()
        self.snapshot = deepcopy(self.context())
        if self.started and not self.stopped:
            self.timer.start(self.interval_ms)

    def stop(self):
        if self.stopped:
            return
        self.stopped = True
        self.timer.stop()
        for job in self.jobs.values():
            self._discard(job)
            job.callbacks.clear()
        self.jobs.clear()

    def _step(self):
        assert QThread.currentThread() is QApplication.instance().thread()
        if self.stopped:
            return
        # Config edits made by any foreground page, localization and theme changes
        # must not produce a page with a mixture of old and new values.
        if self.context() != self.snapshot:
            self.invalidate()
        if not self.can_publish():
            self.timer.start(50)
            return
        available = [(key, job) for key, job in self.jobs.items() if not job.placeholder.failed]
        if not available:
            return  # Failed pages retry only when explicitly requested.
        route, job = available[0]
        try:
            deadline = perf_counter() + self.budget_ms / 1000
            if job.page is None:
                job.page = job.factory()
                job.page.hide()
                job.iterator = iter(job.page.iter_build()) if hasattr(job.page, 'iter_build') else iter(())
            while not job.complete and perf_counter() < deadline:
                try:
                    next(job.iterator)
                except StopIteration:
                    job.complete = True
            if job.complete:
                # The final yield can itself normalize configuration. Restart before
                # publishing if any constructor changed the context.
                if self.context() != self.snapshot:
                    self.invalidate()
                    return
                self.publish(route, job.page)
                del self.jobs[route]
                self.pageReady.emit(route)
                for callback in job.callbacks:
                    if self.stopped:
                        break
                    try:
                        callback(job.page)
                    except Exception:
                        log.error(f'Deferred page action failed: {route}\n{traceback.format_exc()}')
                if not self.jobs and not self.stopped:
                    self.allReady.emit()
                    return
        except Exception:
            log.error(f'Deferred page construction failed: {route}\n{traceback.format_exc()}')
            self._discard(job)
            job.placeholder.setFailed(True)
            job.callbacks.clear()
        if not self.stopped:
            self.timer.start(self.interval_ms)
