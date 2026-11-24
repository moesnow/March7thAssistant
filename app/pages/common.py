"""新页面共用的配色、图标和小控件。"""
from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, CaptionLabel, CardWidget, ExpandSettingCard, FluentIcon, IconWidget,
                            InfoBarIcon, StrongBodyLabel, SwitchButton, isDarkTheme, qconfig)

from app.common import design_tokens as tokens
from app.common.icon import BrandIcon, UiIcon
from app.overview.style import accent, text_color, tone, with_alpha
from app.overview.widgets import ElidedLabel, LinkButton, MeterBar
from module.localization import tr

STATUS_TONES = {"running": "accent", "pending": "accent", "claim_only": "accent", "done_day": "success",
                "done_week": "success", "done_month": "success", "unknown": "warning"}
SECONDARY = (QColor(96, 96, 96), QColor(206, 206, 206))


def is_evernight():
    return qconfig.get(qconfig.themeColor).name() == tokens.EVERNIGHT_RED


def icon_of(name, default=FluentIcon.APPLICATION):
    """把 "FIF.X" / "UiIcon.X" / "BrandIcon.X" 换成图标枚举。"""
    prefix, _, member = str(name or "").partition(".")
    enum = {"UiIcon": UiIcon, "FluentIcon": FluentIcon, "FIF": FluentIcon, "BrandIcon": BrandIcon}.get(prefix)
    try:
        return enum[member] if enum else default
    except KeyError:
        return default


def header_of(card):
    """可展开卡片的标题和悬停区域在它的头部卡片上。"""
    inner = getattr(card, "card", None)
    return inner if isinstance(card, ExpandSettingCard) and isinstance(inner, QWidget) else card


def card_title(card):
    label = getattr(header_of(card), "titleLabel", None)
    return label.text() if label is not None else ""


def secondary(label):
    label.setTextColor(*SECONDARY)
    return label


def bare_switch(parent=None):
    """只有开关本体、不带 On/Off 文字的开关。"""
    switch = SwitchButton(parent)
    switch.setOnText("")
    switch.setOffText("")
    switch.label.hide()
    switch.hBox.setSpacing(0)
    return switch


def style_primary(button, evernight=False):
    """主按钮用深粉配白字（深色主题亮粉配深色字），和总览一致；分体按钮的两半都要改。"""
    from qfluentwidgets import PrimaryPushButton, setCustomStyleSheet
    from app.overview.style import primary_button_qss
    light, dark = primary_button_qss(evernight)
    if isinstance(button, PrimaryPushButton):
        targets = [(button, "PrimaryPushButton")]
    else:
        targets = [(getattr(button, "button", None), "PrimaryPushButton"),
                   (getattr(button, "dropButton", None), "PrimaryToolButton")]
    for widget, selector in targets:
        if widget is not None:
            setCustomStyleSheet(widget, light.replace("PrimaryPushButton", selector),
                                dark.replace("PrimaryPushButton", selector))


def shared(window, name, factory):
    """主窗口上共享一份的模型；页面重建时复用。"""
    value = getattr(window, name, None)
    if value is None:
        value = factory()
        if window is not None:
            setattr(window, name, value)
    return value


class _RestoreFilter(QObject):
    def __init__(self, widget, callback):
        super().__init__(widget)
        self.widget, self.callback = widget, callback

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.WindowStateChange and not watched.isMinimized():
            QTimer.singleShot(0, self, self._run)
        return False

    def _run(self):
        if self.widget.isVisible() and not self.widget.window().isMinimized():
            self.callback()


def refresh_on_restore(widget, window, callback):
    """窗口最小化期间页面不刷新，恢复时补一次；这时子控件不一定收到显示事件。"""
    if window is not None:
        window.installEventFilter(_RestoreFilter(widget, callback))


def popup_menu(owner, menu, position, **options):
    """弹出一次性菜单，同时删掉 owner 上次弹出的那个。

    不能在菜单关闭时就删：这时 Qt 还在处理列表的鼠标事件，动作打开的对话框会让删除提前生效，
    对话框关掉后回到已经删除的列表，程序直接崩溃。
    """
    previous = getattr(owner, "_popupMenu", None)
    owner._popupMenu = menu
    if previous is not None:
        previous.deleteLater()
    menu.exec(position, **options)


def surface_color(hover=False):
    if isDarkTheme():
        return QColor(255, 255, 255, 21 if hover else 13)
    return QColor(255, 255, 255, 230 if hover else 178)


def border_color():
    return QColor(255, 255, 255, 18) if isDarkTheme() else QColor(0, 0, 0, 20)


class Divider(QWidget):
    def __init__(self, parent=None, inset=0):
        super().__init__(parent)
        self.setFixedHeight(1)
        self._inset = inset

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect().adjusted(self._inset, 0, 0, 0), border_color())


class Chevron(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self._up = False

    def setUp(self, up):
        self._up = bool(up)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(text_color(secondary=True), 1.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        top, bottom = (10.0, 6.0) if self._up else (6.0, 10.0)
        painter.drawPolyline(QPolygonF([QPointF(4, top), QPointF(8, bottom), QPointF(12, top)]))


class NoticeStrip(QWidget):
    """浅色提示条：估算、过时提醒和页内说明。"""
    actionClicked = Signal()

    ICONS = {"info": InfoBarIcon.INFORMATION, "warning": InfoBarIcon.WARNING, "error": InfoBarIcon.ERROR,
             "success": InfoBarIcon.SUCCESS}

    def __init__(self, parent=None, *, kind="info", stacked=False):
        super().__init__(parent)
        self._kind = kind
        self._evernight = False
        self.iconWidget = IconWidget(self)
        self.iconWidget.setFixedSize(16, 16)
        self.textLabel = BodyLabel(self)
        self.textLabel.setWordWrap(True)
        self.meter = MeterBar(self, height=4)
        self.meter.hide()
        self.actionButton = LinkButton("", self, size=13)
        self.actionButton.hide()
        self.actionButton.clicked.connect(self.actionClicked)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)
        layout.addWidget(self.iconWidget, 0, Qt.AlignmentFlag.AlignTop)
        column = QVBoxLayout()
        column.setSpacing(8)
        column.addWidget(self.textLabel)
        column.addWidget(self.meter)
        layout.addLayout(column, 1)
        if stacked:
            column.addWidget(self.actionButton, 0, Qt.AlignmentFlag.AlignLeft)
        else:
            layout.addWidget(self.actionButton, 0, Qt.AlignmentFlag.AlignVCenter)
        self.setKind(kind)

    def setKind(self, kind, evernight=None):
        self._kind = kind
        if evernight is not None:
            self._evernight = evernight
        self.iconWidget.setIcon(self.ICONS.get(kind, InfoBarIcon.INFORMATION))
        self.actionButton.setEvernight(self._evernight)
        self.update()

    def setText(self, text):
        self.textLabel.setText(text)

    def setRatio(self, ratio):
        self.meter.setVisible(ratio is not None)
        if ratio is not None:
            self.meter.setFraction(ratio, accent(self._evernight))

    def setAction(self, text):
        self.actionButton.setText(text)
        self.actionButton.setVisible(bool(text))

    def paintEvent(self, event):
        background, foreground = tone(self._kind, self._evernight)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(with_alpha(foreground, 0.22), 1))
        painter.setBrush(background)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 6, 6)


class CollapseHeader(CardWidget):
    """可折叠分组的开关行：标题、内容摘要和箭头。"""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setFixedHeight(54)
        self.setBorderRadius(6)
        self.iconWidget = IconWidget(FluentIcon.SETTING, self)
        self.iconWidget.setFixedSize(16, 16)
        self.titleLabel = BodyLabel(title, self)
        self.summaryLabel = secondary(ElidedLabel(self, size=12))
        self.chevron = Chevron(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)
        layout.addWidget(self.iconWidget)
        layout.addWidget(self.titleLabel)
        layout.addWidget(self.summaryLabel, 1)
        layout.addWidget(self.chevron)

    def setExpanded(self, expanded):
        self.chevron.setUp(expanded)

    def setSummary(self, text):
        self.summaryLabel.setFullText(text)


class SectionView(QWidget):
    """一组设置：标题、可选说明和纵向排列的卡片。可折叠的组由一行开关控制。"""
    toggled = Signal(bool)

    def __init__(self, section, parent=None, *, showTitle=True):
        super().__init__(parent)
        self.section = section
        self._extras = []
        self._expanded = True
        self.header = None
        self.titleLabel = None
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setSpacing(8)
        if section.collapsible:
            self.header = CollapseHeader(section.title, self)
            self.header.clicked.connect(self.toggle)
            self.vBoxLayout.addWidget(self.header)
        elif section.title and showTitle:
            self.titleLabel = StrongBodyLabel(section.title, self)
            self.vBoxLayout.addWidget(self.titleLabel)
        if section.description:
            description = secondary(CaptionLabel(section.description, self))
            description.setWordWrap(True)
            self.vBoxLayout.addWidget(description)
        self.body = QWidget(self)
        self.bodyLayout = QVBoxLayout(self.body)
        self.bodyLayout.setContentsMargins(0, 0, 0, 0)
        self.bodyLayout.setSpacing(3)
        for card in section.cards:
            self.bodyLayout.addWidget(card)
            elide_descriptions(card)
        self.vBoxLayout.addWidget(self.body)
        if self.header is not None:
            self.setExpanded(not section.collapsed)

    def addExtra(self, widget, index=-1):
        self._extras.append(widget)
        if index < 0:
            self.bodyLayout.addWidget(widget)
        else:
            self.bodyLayout.insertWidget(index, widget)
        self.refresh()

    def isExpanded(self):
        return self._expanded

    def setExpanded(self, expanded):
        self._expanded = bool(expanded) or self.header is None
        self.body.setVisible(self._expanded)
        if self.header is not None:
            self.header.setExpanded(self._expanded)

    def toggle(self):
        self.setExpanded(not self._expanded)
        self.toggled.emit(self._expanded)

    def visibleCards(self):
        return [card for card in self.section.cards if not card.isHidden()]

    def refresh(self):
        cards = self.visibleCards()
        self.setVisible(bool(cards) or any(not widget.isHidden() for widget in self._extras))
        if self.header is not None:
            names = [name for name in (card_title_safe(card) for card in cards) if name]
            text = " · ".join(names[:4])
            if len(names) > 4:
                text += " " + tr("等 {count} 项").format(count=len(names))
            self.header.setSummary(text)


class _ElideDescription(QObject):
    """说明放不下时画成省略号，完整内容放进提示。

    不改 QLabel 的文字，首选宽度仍按全文计算：窗口够宽时照常完整显示，
    窄的时候只压缩说明，不会把右侧的按钮挤出窗口。
    """

    def __init__(self, label):
        super().__init__(label)
        self.label = label
        self._tip = False
        label.setMinimumWidth(1)
        label.installEventFilter(self)

    def _shown(self):
        full = self.label.text()
        width = self.label.contentsRect().width()
        metrics = self.label.fontMetrics()
        shown = "\n".join(metrics.elidedText(line, Qt.TextElideMode.ElideRight, width) for line in full.split("\n"))
        return full, shown

    def eventFilter(self, watched, event):
        kind = event.type()
        if kind == QEvent.Type.Paint and self.label.textFormat() != Qt.TextFormat.RichText:
            full, shown = self._shown()
            if shown == full:
                return False
            painter = QPainter(self.label)
            try:
                flags = int(self.label.alignment())
            except TypeError:
                flags = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.label.style().drawItemText(painter, self.label.contentsRect(), flags, self.label.palette(),
                                            self.label.isEnabled(), shown, self.label.foregroundRole())
            painter.end()
            return True
        if kind in (QEvent.Type.Resize, QEvent.Type.Show):
            full, shown = self._shown()
            elided = shown != full
            if elided or self._tip:
                self.label.setToolTip(full if elided else "")
                self._tip = elided
        return False


def elide_descriptions(card):
    """卡片（含可展开卡片里的子卡）的说明文字放不下时省略，避免按钮溢出窗口。"""
    labels = card.findChildren(QLabel, "contentLabel")
    own = getattr(card, "contentLabel", None)
    if isinstance(own, QLabel) and own not in labels:
        labels.append(own)
    for label in labels:
        if label.property("m7aElide"):
            continue
        label.setProperty("m7aElide", True)
        _ElideDescription(label)


def card_title_safe(card):
    try:
        return card_title(card)
    except RuntimeError:
        return ""
