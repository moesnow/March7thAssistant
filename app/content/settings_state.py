"""Configuration events and default actions for page decorations."""
from copy import deepcopy
from functools import lru_cache

from PySide6.QtCore import QObject, QSignalBlocker, Signal
from ruamel.yaml import YAML

from app.common.signal_bus import signalBus
from module.config import cfg
from module.config.config import _get_env_override
from module.localization import tr
from module.settings_registry import Scope, find_setting
from .base import card_for


class ConfigEvents(QObject):
    changed = Signal(object)   # frozenset[str], never values
    reloaded = Signal()

    def __init__(self, config):
        super().__init__()
        config.subscribe(self._receive)

    def _receive(self, keys, external):
        registered = frozenset(k for k in keys if find_setting(k))
        if registered:
            self.changed.emit(registered)
        if external:
            self.reloaded.emit()


@lru_cache
def config_events(config=cfg):
    return ConfigEvents(config)


@lru_cache
def _defaults(path):
    with open(path, encoding="utf-8") as source:
        return YAML(typ="safe").load(source)


def defaults_for(item, config=cfg):
    defaults = _defaults(config.example_path)
    return {key: deepcopy(defaults[key]) for key in item.keys if item.key_scope(key) != Scope.STATE}


def doc_link(item):
    if not item.doc:
        return None
    from module.docs.reader import localized_anchor
    name, _, anchor = item.doc[4:].partition("#")
    if not anchor:
        return item.doc
    translated = localized_anchor(name, anchor)
    return f"doc:{name}#{translated}" if translated else None


def is_modified(item, config=cfg):
    # Defaults apply to the plan currently visible in the page.
    value = config.get_value if hasattr(config, "get_value") else config.config.get
    return any(value(k) != v for k, v in defaults_for(item, config).items())


MANUAL = {
    "ui_language": "语言切换需要重建界面",
    "ui_theme": "主题切换由主窗口管理",
    "game_path": "清空路径可能使任务无法启动",
    "launcher_path": "清空路径可能使任务无法启动",
    "script_path": "清空路径会影响完成后操作",
    "control_backend": "运行方式需要检查任务状态",
    "update_source": "切换更新源会检查更新",
    "autostart_open_gui": "需要同步系统计划任务",
    "adb_path": "设备连接由运行方式页面管理",
    "adb_serial": "设备连接由运行方式页面管理",
    "scheduled_tasks": "定时计划由运行页管理",
}


def reset_reason(item, config=cfg):
    if getattr(config, "_readonly", False) or getattr(config, "writes_suspended", False):
        return tr("配置写入已暂停，请恢复后再保存。")
    if not item.keys or all(item.key_scope(k) == Scope.STATE for k in item.keys):
        return tr("操作或进度没有可恢复的设置")
    if any(item.key_scope(k) == Scope.SECRET for k in item.keys):
        return tr("密钥由编辑表单管理")
    if item.role == "channel":
        return tr("渠道字段需要一起校验")
    if item.id in MANUAL:
        return tr(MANUAL[item.id])
    if any(_get_env_override(k)[0] for k in item.keys):
        return tr("当前值由运行环境指定")
    return ""


def _sync_combo(combo, value):
    with QSignalBlocker(combo):
        combo.setCurrentIndex(combo.findData(value))


def refresh_card(item, host):
    """Read-only refresh, also used after presets. Never simulate a click on reload."""
    card = card_for(item, host)
    if card is None or not item.keys:
        return
    key = item.id
    value = cfg.get_value(key)
    if key == "game_launch_method":
        _sync_combo(host.gamePathCard.comboBox, value)
        host.gamePathCard._updateDescription()
        return
    if item.widget.startswith("adbAdvancedCard."):
        panel = host.adbAdvancedCard
        if key == "adb_device_type":
            _sync_combo(panel.typeComboBox, value or "auto")
        elif key == "adb_tap_ms":
            with QSignalBlocker(panel.tapSpinBox):
                panel.tapSpinBox.setValue(value)
        elif key == "adb_path":
            card.setContent(panel._pathText())
        elif key == "adb_serial":
            panel.refreshSerial()
            host.adbDeviceCard.setSelectedSerial()
        return
    if key in ("ui_theme", "ui_language", "autostart_open_gui", "mirrorchyan_cdk"):
        return
    if key in ("game_path", "launcher_path", "script_path", "banner_path"):
        card.setContent(value or (tr("星轨背景") if key == "banner_path" else ""))
        return
    if hasattr(card, "switchButton"):
        with QSignalBlocker(card.switchButton):
            card.setValue(bool(value))
            if hasattr(card, "_acceptedValue"):
                card._acceptedValue = bool(value)
    if hasattr(card, "comboBox"):
        combo_key = item.keys[1] if hasattr(card, "switchButton") and len(item.keys) > 1 else key
        _sync_combo(card.comboBox, cfg.get_value(combo_key))
        if hasattr(card, "_acceptedIndex"):
            card._acceptedIndex = card.comboBox.currentIndex()
        if hasattr(card, "secondaryComboBox"):
            _sync_combo(card.secondaryComboBox, cfg.get_value(item.keys[1]))
    if hasattr(card, "slider"):
        with QSignalBlocker(card.slider):
            card.slider.setValue(value)
            card.valueLabel.setNum(card.slider.value())
            card.valueLabel.adjustSize()
    if hasattr(card, "spinBox"):
        with QSignalBlocker(card.spinBox):
            card.spinBox.setValue(value)
    if hasattr(card, "set_detected_key"):
        from module.config.game_hotkeys import detect_game_hotkeys
        detected = detect_game_hotkeys(cfg, (key,)) if cfg.auto_detect_game_hotkeys_enable else {}
        card.set_detected_key(detected.get(key))
    elif hasattr(card, "configvalue"):
        card.configvalue = deepcopy(value)
        if hasattr(card, "_display_value"):
            card.configvalue = str(value or "")
            card.contentLabel.setText(card._display_value(card.configvalue))
        elif hasattr(card, "translate_to_chinese"):
            card.contentLabel.setText(card.translate_to_chinese(value))
        elif hasattr(card, "_get_display_text"):
            card.contentLabel.setText(card._get_display_text())
        elif key == "browser_launch_argument":
            card.configvalue = str(value)
            card.contentLabel.setText(card.configvalue)
    if hasattr(card, "_update_content_text"):
        card._update_content_text()
    if hasattr(card, "refreshTimestampContent"):
        card.refreshTimestampContent()
    if key in ("forgottenhall_level", "purefiction_level", "apocalyptic_level"):
        card.refresh()


def restore_default(item, host):
    if item.page != host.page_id or reset_reason(item):
        return False
    values = defaults_for(item)
    if not is_modified(item):
        return True
    card = card_for(item, host)
    if item.role == "card" and card is None:
        return False
    # Single-switch changes pass through the original confirmation and side effects.
    if card is not None and hasattr(card, "switchButton") and len(values) == 1:
        card.switchButton.setChecked(bool(values[item.id]))
    else:
        cfg.set_values(values)
        if item.id.startswith("hotkey_"):
            signalBus.hotkeyChangedSignal.emit()
    refresh_card(item, host)
    return not is_modified(item)


def account_override(item, config=cfg):
    from module.accounts.differences import Difference, value_text
    layer = getattr(config, "_account_layer", None)
    if not layer or layer.row["plan"] != "independent":
        return None
    for key in item.keys:
        if key in layer.plan:
            shared = config.shared_value(key)
            parts = layer.plan[key]
            if isinstance(shared, dict) and isinstance(parts, dict):
                text = "、".join(f"{tr(str(k))} · {value_text(key, shared.get(k), k)}" for k in parts)
            else:
                text = value_text(key, shared)
            return Difference(key, None, tr(item.title), item.page, "", item.link, "", text)
    return None


def restore_shared(item, host):
    if item.page != host.page_id or not account_override(item):
        return False
    for key in item.keys:
        if key in cfg.account_overrides():
            cfg.restore_shared(key)
    refresh_card(item, host)
    return not account_override(item)
