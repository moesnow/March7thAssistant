"""设置卡上的「已修改」「恢复默认」「说明 ↗」。判断和操作来自 app.content.settings_state。"""
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QBoxLayout, QHBoxLayout
from qfluentwidgets import InfoBar, qconfig

from app.content.base import card_for
from app.content.settings_state import config_events, doc_link, is_modified, reset_reason, restore_default
from app.overview.widgets import LinkButton, Pill
from module.localization import tr
from module.logger import log
from module.settings_registry import SETTINGS
from .common import header_of, is_evernight


def _layout_of(layout, widget):
    if layout is None:
        return None
    if layout.indexOf(widget) >= 0:
        return layout
    for index in range(layout.count()):
        found = _layout_of(layout.itemAt(index).layout(), widget)
        if found is not None:
            return found
    return None


class _Badge(QObject):
    def __init__(self, item, card, owner):
        super().__init__(owner)
        self.item, self.owner = item, owner
        self.target = header_of(card)
        title = self.target.titleLabel
        layout = _layout_of(self.target.layout(), title)
        if not isinstance(layout, QBoxLayout):
            raise LookupError(item.id)
        index = layout.indexOf(title)
        alignment = layout.itemAt(index).alignment()
        layout.removeWidget(title)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(title)
        self.pill = Pill(self.target, dot=True, height=18)
        self.resetButton = LinkButton(tr("恢复默认"), self.target, size=12)
        self.docButton = LinkButton(tr("说明") + " ↗", self.target, size=12)
        for widget in (self.pill, self.resetButton, self.docButton):
            row.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addStretch(1)
        layout.insertLayout(index, row)
        if alignment:
            layout.setAlignment(row, alignment)
        self.link = doc_link(item)
        self.docButton.setVisible(bool(self.link))
        self.docButton.setToolTip(tr("在帮助中查看这项设置的说明"))
        self.docButton.clicked.connect(self._openDoc)
        self.resetButton.clicked.connect(self._reset)
        self.resetButton.hide()
        self._hover = False
        self._modified = False
        self._reason = ""
        self.target.installEventFilter(self)
        self.restyle()
        self.refresh()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Enter:
            self._hover = True
            self._updateReset()
        elif event.type() == QEvent.Type.Leave:
            self._hover = False
            self._updateReset()
        return False

    def _updateReset(self):
        self.resetButton.setVisible(self._hover and self._modified and not self._reason)

    def refresh(self):
        try:
            self._modified = bool(self.item.keys) and is_modified(self.item)
            self._reason = reset_reason(self.item) if self._modified else ""
        except Exception as exc:
            log.debug(f"读取设置状态失败：{self.item.id} {type(exc).__name__}")
            self._modified, self._reason = False, ""
        self.pill.setVisible(self._modified)
        self.pill.setToolTip(self._reason or tr("和默认值不同，悬停卡片可以恢复默认"))
        self._updateReset()

    def restyle(self):
        evernight = is_evernight()
        self.pill.setPill(tr("已修改"), "accent", evernight=evernight)
        self.resetButton.setEvernight(evernight)
        self.docButton.setEvernight(evernight)

    def _openDoc(self):
        window = self.owner.window
        if self.link and window is not None:
            window.navigate(self.link)

    def _reset(self):
        try:
            done = restore_default(self.item, self.owner.host)
        except Exception as exc:
            log.error(f"恢复默认失败：{self.item.id} {type(exc).__name__}: {exc}")
            done = False
        if not done:
            InfoBar.warning(tr("没有恢复默认"), reset_reason(self.item) or tr("请在这张卡片上手动修改"),
                            duration=3000, parent=self.owner.window)
        self.refresh()


class CardDecorations(QObject):
    """为一页里登记过的设置卡加上状态标记。"""

    def __init__(self, host, window):
        super().__init__(host)
        self.host, self.window = host, window
        self.badges = {}
        for item in SETTINGS:
            if item.page != host.page_id or item.role != "card" or not (item.keys or item.doc):
                continue
            card = card_for(item, host)
            if card is None or getattr(header_of(card), "titleLabel", None) is None:
                continue
            try:
                self.badges[item.id] = _Badge(item, card, self)
            except LookupError:
                continue
        config_events().changed.connect(self._changed)
        qconfig.themeChanged.connect(self._restyle)
        qconfig.themeColorChanged.connect(self._restyle)

    def _changed(self, keys):
        for badge in self.badges.values():
            if keys.intersection(badge.item.keys):
                badge.refresh()

    def _restyle(self, *_):
        for badge in self.badges.values():
            badge.restyle()
