from qfluentwidgets import FluentIcon as FIF

from app.card.pushsettingcard1 import PushSettingCardKey
from app.card.switchsettingcard1 import SwitchSettingCard1
from app.common.icon import UiIcon
from app.common.signal_bus import signalBus
from module.config import cfg
from module.config.game_hotkeys import AUTO_DETECT_GAME_HOTKEYS, detect_game_hotkeys
from module.localization import tr
from module.settings_registry import SETTINGS
from utils.game_key_templates import PROMPT_KEY_DEFAULTS

KEY_ICONS = {
    "hotkey_interact": FIF.GAME, "hotkey_character_details": FIF.PEOPLE,
    "hotkey_technique": UiIcon.WAND, "hotkey_map": UiIcon.MAP, "hotkey_warp": UiIcon.STAR,
    "hotkey_message": FIF.CHAT, "hotkey_auto_battle": FIF.GAME, "hotkey_stop_task": FIF.CLOSE,
    "hotkey_pause_task": FIF.PAUSE, "hotkey_toggle_autoplot": FIF.CHAT,
}


def build_keys(host, page_id):
    cards = {}
    for item in SETTINGS:
        if item.page != page_id or item.section != "keys":
            continue
        if item.id == AUTO_DETECT_GAME_HOTKEYS:
            card = SwitchSettingCard1(FIF.SYNC, tr(item.title), "", item.id, parent=host.card_parent)
        else:
            card = PushSettingCardKey(tr("按住以修改"), KEY_ICONS[item.id], tr(item.title), item.id,
                                      parent=host.card_parent, requires_key_template=item.id in PROMPT_KEY_DEFAULTS)
            card.keyChanged.connect(signalBus.hotkeyChangedSignal.emit)
            cards[item.id] = card
        setattr(host, item.widget, card)
    if page_id == "game":
        def refresh(enabled):
            detected = detect_game_hotkeys(cfg) if enabled else {}
            for key, card in cards.items():
                card.set_detected_key(detected.get(key))

        host.refresh_detected_keys = refresh
        switch = getattr(host, AUTO_DETECT_GAME_HOTKEYS + "Card").switchButton
        switch.checkedChanged.connect(refresh)
        refresh(switch.isChecked())
