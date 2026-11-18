"""Keep Qt and the Windows taskbar group on the same application artwork."""
import hashlib
from pathlib import Path
import subprocess
import sys

from PySide6.QtCore import QEvent, QObject, Slot
from PySide6.QtGui import QIcon, QPlatformSurfaceEvent
from PySide6.QtWidgets import QApplication

from module.logger import log


_ROOT = Path(__file__).resolve().parents[2]
# Separate source checkouts/installations must not inherit a taskbar group from
# the shared Python runtime. Windows 11 caches a group's artwork at creation,
# so each icon below gets a stable visual identity within this installation.
_APP_ID = 'March7thAssistant.' + hashlib.sha256(str(_ROOT).casefold().encode()).hexdigest()[:16]


class _TaskbarProperties(QObject):
    """Release the shell-owned values before the native window is destroyed."""
    def __init__(self, window, store, keys):
        super().__init__(window)
        self.store = store
        self.keys = keys
        window.windowHandle().installEventFilter(self)
        QApplication.instance().aboutToQuit.connect(self.clear)

    @Slot()
    def clear(self):
        from pythoncom import VT_EMPTY
        from pywintypes import com_error
        from win32com.propsys import propsys
        if self.store is not None:
            try:
                for key in self.keys:
                    self.store.SetValue(key, propsys.PROPVARIANTType(None, VT_EMPTY))
            except com_error as error:
                log.debug(f'清理任务栏窗口属性失败：{error}')
            self.store = None

    def eventFilter(self, watched, event):
        if (event.type() == QEvent.Type.PlatformSurface and
                event.surfaceEventType() == QPlatformSurfaceEvent.SurfaceEventType.SurfaceAboutToBeDestroyed):
            self.clear()
        return False


def set_application_icon(window, icon_path, display_name):
    icon = QIcon(icon_path)
    QApplication.setWindowIcon(icon)
    window.setWindowIcon(icon)
    if hasattr(window, 'tray_icon'):
        window.tray_icon.setIcon(icon)

    if sys.platform != 'win32':
        return
    from pywintypes import com_error
    from win32com.propsys import propsys, pscon

    try:
        store = propsys.SHGetPropertyStoreForWindow(int(window.winId()))
        icon_file = Path(icon_path).resolve()
        visual_id = _APP_ID + '.Icon' + hashlib.sha256(icon_file.read_bytes()).hexdigest()[:12]
        command = [sys.executable]
        if not getattr(sys, 'frozen', False):
            command.append(str(_ROOT / 'app.py'))
        properties = (
            (pscon.PKEY_AppUserModel_RelaunchCommand, subprocess.list2cmdline(command)),
            (pscon.PKEY_AppUserModel_RelaunchDisplayNameResource, display_name),
            (pscon.PKEY_AppUserModel_RelaunchIconResource, str(icon_file) + ',0'),
            # A different visual identity makes Explorer create a fresh button;
            # re-stamping the same ID leaves its cached tile unchanged on Win11.
            # Restoring an icon restores its ID; no random IDs accumulate.
            (pscon.PKEY_AppUserModel_ID, visual_id),
        )
        state = getattr(window, '_taskbar_properties', None)
        if state is None:
            window._taskbar_properties = _TaskbarProperties(window, store, [key for key, _ in properties])
        else:
            state.store = store
            window.windowHandle().installEventFilter(state)
        for key, value in properties:
            store.SetValue(key, propsys.PROPVARIANTType(value))
    except com_error as error:
        log.warning(f'同步 Windows 任务栏图标失败：{error}')
