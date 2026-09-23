import hashlib
import hmac
import json
import platform
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

_URL_AUTH_RE = re.compile(r"://[^@]+:[^@]+@")
_WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:\\(?:[^\\\s]+\\)*[^\\\s]*")
_UNIX_PATH_RE = re.compile(r"/(?:Users|home|root|var|tmp|opt|etc)(?:/[^/\s]+)+")
_HEX_TOKEN_RE = re.compile(r"\b[a-f0-9]{8,}\b", re.IGNORECASE)
_NUMBER_TOKEN_RE = re.compile(r"\b\d{3,}\b")
_WHITESPACE_RE = re.compile(r"\s+")
_MAX_STRING_LEN = 80
_MAX_ERROR_TEXT_LEN = 200
GAME_RUNTIME_LOCAL = "local_game"
GAME_RUNTIME_CLOUD = "cloud_game"
_VALID_GAME_RUNTIMES = {GAME_RUNTIME_LOCAL, GAME_RUNTIME_CLOUD}
STARTUP_FEATURE_CODES = (
    "cloud_game",
    "power",
    "build_target",
    "echo_of_war",
    "borrow",
    "reward",
    "daily",
    "activity",
    "asset_manager",
    "currencywars",
    "weekly_divergent",
    "universe",
    "fight",
    "forgottenhall",
    "purefiction",
    "apocalyptic",
)
STARTUP_ACTIVITY_FEATURE_CODES = (
    "journey_highlights_notification",
)
STARTUP_NOTIFICATION_CHANNEL_CODES = (
    "winotify",
    "telegram",
    "matrix",
    "serverchanturbo",
    "serverchan3",
    "bark",
    "smtp",
    "onebot",
    "gocqhttp",
    "dingtalk",
    "pushplus",
    "qmsg",
    "wechatworkapp",
    "wechatworkbot",
    "gotify",
    "discord",
    "pushdeer",
    "lark",
    "kook",
    "webhook",
    "custom",
    "meow",
)
NOTIFICATION_LEVEL_ALL = "all"
NOTIFICATION_LEVEL_ERROR = "error"
_VALID_STARTUP_FEATURE_CODES = set(STARTUP_FEATURE_CODES)
_VALID_STARTUP_ACTIVITY_FEATURE_CODES = set(STARTUP_ACTIVITY_FEATURE_CODES)
_VALID_STARTUP_NOTIFICATION_CHANNEL_CODES = set(STARTUP_NOTIFICATION_CHANNEL_CODES)
_VALID_NOTIFICATION_LEVELS = {NOTIFICATION_LEVEL_ALL, NOTIFICATION_LEVEL_ERROR}


class EventName(str, Enum):
    APP_STARTUP = "app_startup"
    APP_SHUTDOWN = "app_shutdown"
    TASK_START = "task_start"
    TASK_COMPLETE = "task_complete"
    ERROR = "error"
    FEATURE_USAGE = "feature_usage"


VALID_EVENT_NAMES = {e.value for e in EventName}


def _sanitize_string(value: str, max_len: int = _MAX_STRING_LEN) -> str:
    value = str(value).strip()
    value = _WINDOWS_PATH_RE.sub("[PATH]", value)
    value = _UNIX_PATH_RE.sub("[PATH]", value)
    value = _URL_AUTH_RE.sub("://[REDACTED]@", value)
    if len(value) > max_len:
        value = value[:max_len]
    return value


def _normalize_screen_resolution(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return "unknown"
    return f"{int(width // 160 * 160)}x{int(height // 90 * 90)}"


def _sanitize_bool(value: Any) -> bool:
    return bool(value)


def _sanitize_float(value: Any) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    return round(float(value), 1)


def _sanitize_small_text(value: Any, max_len: int = _MAX_STRING_LEN) -> str | None:
    if value is None:
        return None
    text = _sanitize_string(str(value), max_len=max_len)
    return text or None


def _sanitize_task_id(value: Any) -> str | None:
    return _sanitize_small_text(value, max_len=40)


def _sanitize_language(value: Any) -> str | None:
    return _sanitize_small_text(value, max_len=24)


def _sanitize_ocr_mode(value: Any) -> str | None:
    return _sanitize_small_text(value, max_len=24)


def _sanitize_game_runtime(value: Any) -> str | None:
    value = _sanitize_small_text(value, max_len=24)
    if value in _VALID_GAME_RUNTIMES:
        return value
    return None


def _sanitize_code_list(value: Any, *, allowed_values: set[str], max_items: int = 32) -> list[str] | None:
    if not isinstance(value, (list, tuple, set)):
        return None

    sanitized: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _sanitize_small_text(item, max_len=32)
        if not text or text not in allowed_values or text in seen:
            continue
        seen.add(text)
        sanitized.append(text)
        if len(sanitized) >= max_items:
            break
    return sanitized or None


def _sanitize_startup_features(value: Any) -> list[str] | None:
    return _sanitize_code_list(value, allowed_values=_VALID_STARTUP_FEATURE_CODES, max_items=24)


def _sanitize_startup_activity_features(value: Any) -> list[str] | None:
    return _sanitize_code_list(value, allowed_values=_VALID_STARTUP_ACTIVITY_FEATURE_CODES, max_items=12)


def _sanitize_notification_channels(value: Any) -> list[str] | None:
    return _sanitize_code_list(value, allowed_values=_VALID_STARTUP_NOTIFICATION_CHANNEL_CODES, max_items=24)


def _sanitize_notification_level(value: Any) -> str | None:
    value = _sanitize_small_text(value, max_len=16)
    if value in _VALID_NOTIFICATION_LEVELS:
        return value
    return None


def _sanitize_feature_name(value: Any) -> str | None:
    return _sanitize_small_text(value, max_len=32)


def _sanitize_feature_value(value: Any) -> str | None:
    return _sanitize_small_text(value, max_len=48)


def _sanitize_error_type(value: Any) -> str | None:
    return _sanitize_small_text(value, max_len=64)


def _normalize_error_text(value: str) -> str:
    value = _sanitize_string(value, max_len=_MAX_ERROR_TEXT_LEN)
    value = _WINDOWS_PATH_RE.sub("[PATH]", value)
    value = _UNIX_PATH_RE.sub("[PATH]", value)
    value = _HEX_TOKEN_RE.sub("[HEX]", value)
    value = _NUMBER_TOKEN_RE.sub("[N]", value)
    value = _WHITESPACE_RE.sub(" ", value)
    return value.strip()


def fingerprint_error(value: str) -> str:
    normalized = _normalize_error_text(value)
    if not normalized:
        normalized = "empty"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _sanitize_error_fingerprint(value: Any) -> str | None:
    return _sanitize_small_text(value, max_len=16)


def _sanitize_os_version(value: Any) -> str | None:
    return _sanitize_small_text(value, max_len=32)


def _sanitize_cpu_arch(value: Any) -> str | None:
    return _sanitize_small_text(value, max_len=16)


EVENT_PROPERTY_SCHEMAS: dict[str, dict[str, Callable[[Any], Any]]] = {
    EventName.APP_STARTUP.value: {
        "os_version": _sanitize_os_version,
        "cpu_arch": _sanitize_cpu_arch,
        "screen_resolution": _sanitize_small_text,
        "is_frozen": _sanitize_bool,
        "game_runtime": _sanitize_game_runtime,
        "enabled_features": _sanitize_startup_features,
        "enabled_activity_features": _sanitize_startup_activity_features,
        "notification_master_enabled": _sanitize_bool,
        "enabled_notification_channels": _sanitize_notification_channels,
        "notification_level": _sanitize_notification_level,
        "notification_merge": _sanitize_bool,
        "notification_send_images": _sanitize_bool,
        "ocr_mode": _sanitize_ocr_mode,
        "language": _sanitize_language,
    },
    EventName.APP_SHUTDOWN.value: {
        "session_duration_seconds": _sanitize_float,
    },
    EventName.TASK_START.value: {
        "task_id": _sanitize_task_id,
    },
    EventName.TASK_COMPLETE.value: {
        "task_id": _sanitize_task_id,
        "success": _sanitize_bool,
        "duration_seconds": _sanitize_float,
    },
    EventName.ERROR.value: {
        "error_type": _sanitize_error_type,
        "error_fingerprint": _sanitize_error_fingerprint,
    },
    EventName.FEATURE_USAGE.value: {
        "feature": _sanitize_feature_name,
        "value": _sanitize_feature_value,
    },
}


def _sanitize_properties(event_name: str, properties: dict[str, Any]) -> dict[str, Any]:
    schema = EVENT_PROPERTY_SCHEMAS.get(event_name, {})
    sanitized: dict[str, Any] = {}
    for key, sanitizer in schema.items():
        if key not in properties:
            continue
        sanitized_value = sanitizer(properties[key])
        if sanitized_value is None:
            continue
        sanitized[key] = sanitized_value
    return sanitized


def build_event(
    event_name: str,
    uuid: str,
    version: str,
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event": event_name,
        "uuid": uuid,
        "event_id": uuid4_hex(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": version,
        "properties": _sanitize_properties(event_name, properties or {}),
    }


def uuid4_hex() -> str:
    return uuid.uuid4().hex


def serialize_batch_payload(events: list[dict[str, Any]], batch_id: str | None = None) -> bytes:
    payload: dict[str, Any] = {"events": events}
    if batch_id:
        payload["batch_id"] = batch_id
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def get_system_context() -> dict[str, Any]:
    try:
        import ctypes
        user32 = ctypes.windll.user32
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
    except Exception:
        screen_w, screen_h = 0, 0

    release = platform.release().split(".")[0] if platform.release() else "unknown"
    machine = platform.machine().lower() if platform.machine() else "unknown"
    return {
        "os_version": f"{platform.system()} {release}".strip(),
        "cpu_arch": machine,
        "screen_resolution": _normalize_screen_resolution(screen_w, screen_h),
        "is_frozen": getattr(__import__("sys"), "frozen", False),
    }


def sign_payload(payload_bytes: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
