from PySide6.QtCore import QEvent, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget
from qfluentwidgets import isDarkTheme, qconfig

from app.common import design_tokens as tokens
from module.logger import log
from module.navigation import resolve_link


class _CardHighlight(QWidget):
    """Paint on a transparent child so Fluent keeps ownership of the card style."""

    def __init__(self, card):
        super().__init__(card)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setGeometry(card.rect())
        card.installEventFilter(self)
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(1200)
        self.animation.setStartValue(1.0)
        self.animation.setKeyValueAt(0.35, 0.2)
        self.animation.setKeyValueAt(0.65, 1.0)
        self.animation.setEndValue(0.0)
        self.animation.valueChanged.connect(lambda _: self.update())
        self.animation.finished.connect(self.deleteLater)
        self.show()
        self.raise_()
        self.animation.start()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize:
            self.setGeometry(watched.rect())
        return False

    def paintEvent(self, event):
        palette = tokens.DARK if isDarkTheme() else tokens.LIGHT
        evernight = qconfig.get(qconfig.themeColor).name() == tokens.EVERNIGHT_RED
        color = QColor(palette.evernight_accent if evernight else palette.brand_pink)
        color.setAlphaF(self.animation.currentValue())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(color, 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5),
                                tokens.CARD_RADIUS, tokens.CARD_RADIUS)


def highlight(widget):
    target = getattr(widget, "card", widget)
    for previous in widget.window().findChildren(_CardHighlight):
        previous.hide()
        previous.deleteLater()
    return _CardHighlight(target)


def navigate(window, link: str) -> bool:
    """Dispatch a link on the UI thread. Unavailable destinations never interrupt a task."""
    try:
        target = resolve_link(link)
        if target is None:
            log.warning(f'无法识别的界面链接：{link}')
            return False
        kind, name = target.kind, target.page
        page = getattr(window, target.interface, None)
        if page is None:
            return False
        window.switchTo(page)
        if kind == 'run':
            if name in ("current", "history"):
                return page.showPage(name)
            if name == "schedule":
                return page.showSchedule()
            if page.showRun(name):
                return True
            from qfluentwidgets import InfoBar
            from module.localization import tr
            InfoBar.warning(tr("运行记录"), tr("这条运行记录已清理"), duration=3500, parent=window)
            return False
        if target.item is not None:
            return bool(page.locate(target.item))
        if kind == 'task':
            return page.showTask(name) is not False
        if kind == 'category':
            return page.showCategory(name) is not False
        if kind == 'doc':
            return bool(page.showDocument(name, target.anchor))
        if kind == 'tool':
            return bool(page.locate(name))
        return kind == 'page'
    except Exception as exc:
        log.warning(f'界面链接跳转失败：{link}，{exc}')
    return False
