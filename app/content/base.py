from dataclasses import dataclass, field
from operator import attrgetter

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget
from qfluentwidgets import ExpandSettingCard

from module.content_pages import PAGE_BY_ID
from module.localization import tr
from module.settings_registry import SETTINGS, find_setting
from module.content_visibility import Visibility
from module.config import cfg


@dataclass(frozen=True)
class CheckItem:
    key: str
    name: str


@dataclass
class Section:
    id: str
    title: str
    cards: list[QWidget] = field(default_factory=list)
    collapsible: bool = False
    collapsed: bool = False
    description: str = ""
    checks: tuple[CheckItem, ...] = ()


def setting_for(card):
    key = card.property("settingId")
    return find_setting(key) if key else None


def card_for(item, host):
    if isinstance(item, str):
        item = find_setting(item)
    if item and item.widget and item.page == host.page_id:
        return attrgetter(item.widget)(host) if hasattr(host, item.widget.split(".")[0]) else None


class PageHost(QObject):
    visibilityChanged = Signal()

    def __init__(self, window, card_parent):
        super().__init__(card_parent)
        self.window = window
        self.card_parent = card_parent
        self.page_id = None
        self.sections = []
        self._items = ()
        self._visible = None

    def finish(self, page_id, nested=()):
        self.page_id = page_id
        page = PAGE_BY_ID[page_id]
        self._items = tuple(item for item in SETTINGS if item.page == page_id)
        sections = {g.id: Section(g.id, tr(g.title), collapsible=g.collapsed, collapsed=g.collapsed)
                    for g in page.groups}
        children = {name for parent, names in nested for name in names}
        for item in self._items:
            card = card_for(item, self)
            section = sections[item.section]
            if card is not None:
                card.setProperty("settingId", item.id)
                if "." not in item.widget and item.widget not in children:
                    card.setParent(self.card_parent)
                    section.cards.append(card)
            elif item.role == "check":
                section.checks += (CheckItem(item.id, tr(item.title)),)
        for parent, names in nested:
            container = getattr(self, parent)
            container.addSettingCards([getattr(self, name) for name in names])
        self.sections = list(sections.values())
        from .settings_state import config_events
        config_events().changed.connect(self._config_changed)
        self.refresh_visibility()
        return self.sections

    def _config_changed(self, keys):
        from .settings_state import refresh_card
        for item in self._items:
            if keys.intersection(item.keys):
                refresh_card(item, self)
        if keys.intersection({"control_backend", "cloud_game_enable", "ui_profile", "currencywars_strategy"}):
            self.refresh_visibility()
            if self.page_id == "run_mode":
                self.adbStatusCard.refresh()
        if self.page_id == "game" and keys.intersection({"game_optimization_enable", "auto_detect_game_hotkeys_enable"}):
            self.refresh_options()
        if self.page_id == "run_mode" and "local_control_mode" in keys:
            self.refresh_mouse_option()

    def refresh_visibility(self):
        visibility = Visibility.read(cfg)
        visible = frozenset(item.id for item in self._items if visibility.setting(item))
        if self._visible != visible:
            for item in self._items:
                card = card_for(item, self)
                if card is not None:
                    card.setVisible(item.id in visible)
            self._visible = visible
            self.visibilityChanged.emit()

    def capture_card_state(self):
        expanded = {item.id: card.isExpand for item in self._items
                    if isinstance(card := card_for(item, self), ExpandSettingCard)}
        language = card_for("ui_language", self)
        return {"expanded": expanded, "language_focus": bool(language and language.comboBox.hasFocus())}

    def restore_card_state(self, state):
        for key, value in state.get("expanded", {}).items():
            card = card_for(key, self)
            if isinstance(card, ExpandSettingCard):
                card.setExpand(bool(value))
                card.expandAni.setCurrentTime(card.expandAni.duration())
        language = card_for("ui_language", self)
        if language and state.get("language_focus"):
            language.comboBox.setFocus()
