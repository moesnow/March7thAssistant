"""Notification channel form operations. A form uses full configuration keys."""
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
from urllib.parse import urlsplit

from module.channel_catalog import CHANNELS, CHANNEL_BY_ID
from module.localization import tr
from utils.data_files import data_lock
from . import results

ADDED = "notification_added_channels"


def available():
    return tuple(c for c in CHANNELS if c.id != "winotify" or sys.platform == "win32")


def form(config, channel_id):
    return {f.key: config.get_value(f.key) for f in CHANNEL_BY_ID[channel_id].fields}


@dataclass(frozen=True)
class AddedChannel:
    channel: object
    enabled: bool
    summary: str
    last: results.Delivery | None


def added(config, history=None):
    history = results.read_results() if history is None else history
    explicit = config.get_value(ADDED) or ()
    rows = []
    for channel in available():
        enabled = bool(config.get_value(channel.enable_key))
        filled = any(config.get_value(f.key) for f in channel.fields if f.required)
        if channel.id == "wechatworkbot":
            filled = any(form(config, channel.id).values())
        if enabled or filled or channel.id in explicit:
            # User-entered strings, URLs and IDs can all contain credentials. Only expose counts.
            count = sum(bool(config.get_value(f.key)) for f in channel.fields if f.kind not in ("switch", "choice"))
            summary = tr("已填写 {count} 个字段").format(count=count) if channel.fields else tr(channel.description)
            rows.append(AddedChannel(channel, enabled, summary, history.get(channel.id)))
    return tuple(rows)


def _coerce(field, value):
    if value is None or value == "":
        if field.required:
            raise ValueError(tr("请填写此项"))
        return ""
    if field.kind == "switch":
        if type(value) != bool:
            raise ValueError(tr("请选择开或关"))
        return value
    if field.kind == "number":
        if isinstance(value, bool) or not str(value).lstrip("-").isdecimal():
            raise ValueError(tr("请输入整数"))
        value = int(value)
        if field.key == "notify_smtp_port" and not 1 <= value <= 65535:
            raise ValueError(tr("端口应在 1 到 65535 之间"))
        return value
    if field.choices:
        match = next((option for option in field.choices if option.casefold() == str(value).strip().casefold()), None)
        if match is None:
            raise ValueError(tr("请选择列表中的选项"))
        return match
    if field.key in ("notify_custom_data", "notify_custom_image", "notify_webhook_headers", "notify_webhook_body"):
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except ValueError:
                if field.key == "notify_webhook_body":
                    return value
                raise ValueError(tr("请输入有效的 JSON")) from None
        else:
            parsed = deepcopy(value)
        if field.key == "notify_webhook_headers" and not isinstance(parsed, dict):
            raise ValueError(tr("请求头应为 JSON 对象"))
        return parsed
    if isinstance(value, (dict, list)) and field.key in ("notify_telegram_proxies", "notify_matrix_proxy"):
        return deepcopy(value)
    value = str(value).strip()
    if not value and field.required:
        raise ValueError(tr("请填写此项"))
    if value and field.key in URL_FIELDS:
        if field.key == "notify_gocqhttp_endpoint" and "://" not in value:
            value = "http://" + value
        url = urlsplit(value)
        if url.scheme not in ("http", "https") or not url.hostname:
            raise ValueError(tr("请输入完整的 HTTP 或 HTTPS 地址"))
    return value


URL_FIELDS = {
    "notify_webhook_url", "notify_custom_url", "notify_wechatworkbot_webhook_url", "notify_discord_webhook",
    "notify_onebot_endpoint", "notify_gocqhttp_endpoint", "notify_matrix_homeserver", "notify_gotify_url",
    "notify_lark_webhook", "notify_bark_base_url", "notify_wechatworkapp_base_url", "notify_pushdeer_url",
}


def validate(config, channel_id, draft):
    channel = CHANNEL_BY_ID[channel_id]
    values = form(config, channel_id)
    errors = {key: tr("未知字段") for key in draft if key not in values}
    for field in channel.fields:
        try:
            values[field.key] = _coerce(field, draft.get(field.key, values[field.key]))
        except (TypeError, ValueError) as error:
            errors[field.key] = str(error)
    def require_one(*suffixes):
        keys = [f"notify_{channel_id}_{s}" for s in suffixes]
        if not any(values.get(key) for key in keys):
            errors.update(dict.fromkeys(keys, tr("请至少填写其中一项")))
    if channel_id == "wechatworkbot":
        require_one("key", "webhook_url")
    elif channel_id == "qqbot":
        require_one("openid", "group_openid")
    elif channel_id in ("onebot", "gocqhttp"):
        require_one("user_id", "group_id")
        mode = values.get("notify_gocqhttp_message_type")
        if mode and channel_id == "gocqhttp":
            require_one("group_id" if mode == "group" else "user_id")
    elif channel_id == "smtp":
        require_one("user", "From")
        require_one("user", "To")
    elif channel_id == "lark" and values["notify_lark_imageenable"]:
        for key in ("notify_lark_appid", "notify_lark_secret"):
            if not values[key]:
                errors[key] = tr("启用图片时请填写此项")
    return values, errors


def _change(config, channel_id, update):
    if getattr(config, "writes_suspended", False) or getattr(config, "_readonly", False):
        return {"": tr("配置写入已暂停，请恢复后再保存。")}
    path = getattr(config, "config_path", None)
    lock = data_lock(Path(path).absolute().parent, name=".notify-channels.lock", timeout=0.5) if path else nullcontext()
    try:
        with lock:
            if path:
                config._load_config(save=False)
            values, errors, keep = update()
            if errors:
                return errors
            members = list(config.get_value(ADDED) or ())
            if keep and channel_id not in members:
                members.append(channel_id)
            if not keep:
                members = [name for name in members if name != channel_id]
            config.set_values({**values, ADDED: members})
    except (OSError, ValueError):
        return {"": tr("保存失败，请稍后重试")}
    return {}


def save(config, channel_id, draft):
    def update():
        values, errors = validate(config, channel_id, draft)
        return {**values, CHANNEL_BY_ID[channel_id].enable_key: True}, errors, True
    return _change(config, channel_id, update)


def set_enabled(config, channel_id, enabled):
    if enabled:
        return save(config, channel_id, {})
    return _change(config, channel_id, lambda: ({CHANNEL_BY_ID[channel_id].enable_key: False}, {}, True))


def remove(config, channel_id):
    from ruamel.yaml import YAML
    def update():
        with open(config.example_path, encoding="utf-8") as source:
            defaults = YAML(typ="safe").load(source)
        channel = CHANNEL_BY_ID[channel_id]
        values = {f.key: defaults[f.key] for f in channel.fields}
        return {**values, channel.enable_key: False}, {}, False
    return _change(config, channel_id, update)


def send_test(config, channel_id, draft):
    from . import NotifierFactory
    channel = CHANNEL_BY_ID[channel_id]
    values, errors = validate(config, channel_id, draft)
    if errors:
        return results.Delivery(datetime.now(timezone.utc).isoformat(), False, "config")
    prefix = f"notify_{channel_id}_"
    params = {key.removeprefix(prefix): value for key, value in values.items() if value != ""}
    try:
        # Provider libraries may log raw response bodies or credential-bearing URLs.
        logger = logging.Logger("channel-test")
        logger.disabled = True
        notifier = NotifierFactory.create_notifier(channel.id, params, logger)
        if notifier is None:
            raise ValueError("unknown channel")
        template = config.get_value("notify_template")
        return results.send_one(notifier, template["Title"], template["TestMessage"])
    except Exception as exc:
        return results.Delivery(datetime.now(timezone.utc).isoformat(), False, results.failure_code(exc))
