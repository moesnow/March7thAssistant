"""Keep the worker independent of the lifetime of the warp page."""
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from module.gacha.store import GachaStore
from module.gacha.update import unavailable_reason, update_records
from module.localization import tr


class _Signals(QObject):
    progress = Signal(str, object)
    done = Signal(object)


class _Fetch(QRunnable):
    def __init__(self, store, mode):
        super().__init__()
        self.store = store
        self.mode = mode
        self.signals = _Signals()

    def run(self):
        result = update_records(self.store, self.mode, self.signals.progress.emit)
        self.signals.done.emit(result)


class GachaUpdater(QObject):
    progress = Signal(str, object)
    finished = Signal(object)
    _last_successful_link = None

    def __init__(self, parent=None, *, store=None):
        super().__init__(parent)
        self.store = store or GachaStore()
        self._task = None

    @property
    def last_link(self):
        return GachaUpdater._last_successful_link

    @property
    def running(self):
        return self._task is not None

    @property
    def unavailable_reason(self):
        return unavailable_reason()

    @property
    def available(self):
        return not self.unavailable_reason

    def start(self, mode="normal"):
        if self.running or not self.available:
            return False
        self._task = _Fetch(self.store, mode)
        self._task.signals.progress.connect(self.progress)
        self._task.signals.done.connect(self._finished)
        QThreadPool.globalInstance().start(self._task)
        return True

    @Slot(object)
    def _finished(self, result):
        self._task = None
        if result.success:
            GachaUpdater._last_successful_link = result.link
        self.finished.emit(result)

    def copy_link(self):
        from utils import clipboard
        if not self.last_link:
            raise ValueError(tr("还没有成功更新过抽卡记录。"))
        clipboard.copy(self.last_link)
