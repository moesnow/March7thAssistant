from operator import attrgetter

from PySide6.QtCore import QEvent, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget
from qfluentwidgets import ExpandSettingCard, isDarkTheme, qconfig

from app.common import design_tokens as tokens
from module.logger import log
from module.navigation import parse_link


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


def _show_setting(page, setting):
    if setting.widget:
        card = attrgetter(setting.widget)(page)
    else:
        # Channel cards are built from configuration. Keys survive language and order changes.
        card = next((child for child in page.NotifyGroup.findChildren(QWidget)
                     if getattr(child, 'configname', None) in setting.keys), None)
    if card is None:
        return False

    parents = []
    group = card.parentWidget()
    while group is not None and page.stackedWidget.indexOf(group) < 0:
        if isinstance(group, ExpandSettingCard):
            parents.append(group)
        group = group.parentWidget()
    if group is None:
        return False
    tab = page.pivot.items[group.objectName()]
    if tab.isHidden():
        return False
    page.stackedWidget.setCurrentWidget(group)
    page.pivotScrollArea.ensureWidgetVisible(tab)
    # Backend- and strategy-dependent cards must respect the user's current configuration.
    if card.isHidden() or any(parent.isHidden() for parent in parents):
        return False
    for parent in reversed(parents):
        if not parent.isExpand:
            parent.setExpand(True)
        parent.expandAni.setCurrentTime(parent.expandAni.duration())
    group.layout().activate()
    page.stackedWidget.setFixedHeight(group.sizeHint().height())
    page.vBoxLayout.activate()
    page.scrollWidget.adjustSize()
    target = getattr(card, 'card', card)  # An expanded card's header may be far above its bottom.
    # Center the header when possible: the Fluent page slides in from below and
    # can still clip the bottom of its viewport when the highlight starts.
    viewport = page.viewport()
    center_y = target.mapTo(viewport, target.rect().center()).y()
    scrollbar = page.verticalScrollBar()
    scrollbar.setValue(scrollbar.value() + center_y - viewport.rect().center().y())
    for previous in page.findChildren(_CardHighlight):
        previous.hide()
        previous.deleteLater()
    _CardHighlight(target)
    return True


def navigate(window, link: str) -> bool:
    """Dispatch a link on the UI thread. Unavailable destinations never interrupt a task."""
    try:
        route = parse_link(link)
        if route is None:
            log.warning(f'无法识别的界面链接：{link}')
            return False
        kind, name, anchor = route
        if kind == 'task':
            log.info(f'任务页暂不支持深链接：{link}')
            return False
        if kind == 'doc':
            from app.help_interface import DOC_OF_TAB

            attr = next((tab for tab, doc in DOC_OF_TAB.items() if doc.casefold() == name.casefold()), None)
            if attr:
                page = window.helpInterface
                window.switchTo(page)
                page.showDocument(attr, anchor)
                return True
        else:
            from module.settings_registry import find_setting

            setting = find_setting(name)
            if setting:
                page = getattr(window, 'settingInterface', window)
                if page is not window:
                    window.switchTo(page)
                if _show_setting(page, setting):
                    return True
        log.warning(f'界面链接的目标不存在或当前不可用：{link}')
    except Exception as exc:
        log.warning(f'界面链接跳转失败：{link}，{exc}')
    return False
