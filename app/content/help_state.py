"""Create in HelpInterface.__init__ so first launch records the installed version."""
from PySide6.QtCore import QObject, Signal

from module.docs.state import changelog_is_new, mark_changelog_seen


class ChangelogBadge(QObject):
    changed = Signal(bool)

    def __init__(self, parent=None, *, version=None, path=None):
        super().__init__(parent)
        self.version, self.path = version, path
        self.is_new = changelog_is_new(version, path)

    def refresh(self):
        self._set(changelog_is_new(self.version, self.path))

    def mark_seen(self):
        if mark_changelog_seen(self.version, self.path):
            self._set(False)
            return True
        return False

    def _set(self, value):
        if self.is_new != value:
            self.is_new = value
            self.changed.emit(value)


def open_link(window, link):
    """Open an already classified inline Link on the GUI thread."""
    if link.kind == "external":
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        return QDesktopServices.openUrl(QUrl(link.target))
    from app.navigation import navigate
    return navigate(window, link.target)
