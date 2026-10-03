import atexit
import json
import threading
import time
import uuid
from collections import deque
from typing import Any

import requests

from module.telemetry.events import (
    EventName,
    GAME_RUNTIME_CLOUD,
    GAME_RUNTIME_LOCAL,
    NOTIFICATION_LEVEL_ALL,
    NOTIFICATION_LEVEL_ERROR,
    STARTUP_NOTIFICATION_CHANNEL_CODES,
    build_event,
    fingerprint_error,
    get_system_context,
    serialize_batch_payload,
    sign_payload,
)
from utils.singleton import SingletonMeta

_ENDPOINT = "https://api.m7a.top/telemetry"
_REGISTER_ENDPOINT = "https://api.m7a.top/telemetry/register"
_BATCH_SIZE = 50
_FLUSH_INTERVAL = 30
_QUEUE_MAX = 200
_MAX_SEND_RETRIES = 2
_REQUEST_TIMEOUT = 5


class _TelemetryNoopLogger:
    def debug(self, *_args, **_kwargs):
        return None

    info = debug
    warning = debug
    error = debug


_FEATURE_FLAG_MAP = (
    ("cloud_game_enable", "cloud_game"),
    ("power_enable", "power"),
    ("build_target_enable", "build_target"),
    ("echo_of_war_enable", "echo_of_war"),
    ("borrow_enable", "borrow"),
    ("reward_enable", "reward"),
    ("daily_enable", "daily"),
    ("activity_enable", "activity"),
    ("asset_manager_enable", "asset_manager"),
    ("currencywars_enable", "currencywars"),
    ("weekly_divergent_enable", "weekly_divergent"),
    ("universe_enable", "universe"),
    ("fight_enable", "fight"),
    ("forgottenhall_enable", "forgottenhall"),
    ("purefiction_enable", "purefiction"),
    ("apocalyptic_enable", "apocalyptic"),
)
_ACTIVITY_FEATURE_FLAG_MAP = (
    ("activity_journey_highlights_notification_enable", "journey_highlights_notification"),
)
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _resolve_effective_ocr_mode() -> str:
    configured_mode = ""
    try:
        from module.ocr.ocr import OCR, OCR_MODE_AUTO

        resolver = OCR(logger=_TelemetryNoopLogger(), replacements=None)
        configured_mode = str(resolver._get_selected_mode() or OCR_MODE_AUTO).strip()
        _, _, resolved_mode = resolver._resolve_engine(configured_mode)
        resolved_mode = str(resolved_mode or "").strip()
        if resolved_mode:
            return resolved_mode
    except Exception:
        pass

    try:
        from module.config import cfg

        raw_mode = None
        if hasattr(cfg, "get_value"):
            raw_mode = cfg.get_value("ocr_gpu_acceleration", None)
        if raw_mode is None and hasattr(cfg, "ocr_gpu_acceleration"):
            raw_mode = cfg.ocr_gpu_acceleration
        if raw_mode is None and hasattr(cfg, "ocr_mode"):
            raw_mode = cfg.ocr_mode

        if isinstance(raw_mode, bool):
            return "cpu" if not raw_mode else "unknown"

        configured_mode = str(raw_mode or configured_mode).strip()
    except Exception:
        pass

    if configured_mode and configured_mode != "auto":
        return configured_mode
    return "unknown"


def _resolve_effective_language() -> str:
    configured_language = ""
    try:
        from module.config import cfg

        current_language = str(getattr(cfg, "ui_language_now", "") or "").strip()
        if current_language and current_language != "auto":
            return current_language

        if hasattr(cfg, "get_value"):
            configured_language = str(cfg.get_value("ui_language", getattr(cfg, "ui_language", "zh_CN")) or "").strip()
        else:
            configured_language = str(getattr(cfg, "ui_language", "zh_CN") or "").strip()

        if configured_language and configured_language != "auto":
            return configured_language
    except Exception:
        pass

    try:
        from module.localization import detect_lang

        detected_language = str(detect_lang() or "").strip()
        if detected_language:
            return detected_language
    except Exception:
        pass

    return configured_language if configured_language and configured_language != "auto" else "zh_CN"


def _resolve_game_runtime() -> str:
    try:
        from module.config import cfg

        if hasattr(cfg, "get_value"):
            raw_value = cfg.get_value("cloud_game_enable", getattr(cfg, "cloud_game_enable", False))
        else:
            raw_value = getattr(cfg, "cloud_game_enable", False)

        if isinstance(raw_value, str):
            return GAME_RUNTIME_CLOUD if raw_value.strip().lower() in {"1", "true", "yes", "on"} else GAME_RUNTIME_LOCAL
        return GAME_RUNTIME_CLOUD if bool(raw_value) else GAME_RUNTIME_LOCAL
    except Exception:
        return GAME_RUNTIME_LOCAL


def _read_config_value(key: str, default: Any = None) -> Any:
    try:
        from module.config import cfg

        fallback = getattr(cfg, key, default)
        if hasattr(cfg, "get_value"):
            return cfg.get_value(key, fallback)
        return fallback
    except Exception:
        return default


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE_VALUES:
            return True
        if normalized in _FALSE_VALUES:
            return False
    return bool(value)


def _collect_enabled_codes(flag_map: tuple[tuple[str, str], ...]) -> list[str]:
    enabled_codes: list[str] = []
    for config_key, code in flag_map:
        if _as_bool(_read_config_value(config_key, False), False):
            enabled_codes.append(code)
    return enabled_codes


def _resolve_notification_level() -> str:
    level = str(_read_config_value("notify_level", NOTIFICATION_LEVEL_ALL) or "").strip().lower()
    if level in {NOTIFICATION_LEVEL_ALL, NOTIFICATION_LEVEL_ERROR}:
        return level
    return NOTIFICATION_LEVEL_ALL


def _collect_notification_snapshot() -> dict[str, Any]:
    master_enabled = _as_bool(_read_config_value("notification_enable", True), True)
    snapshot: dict[str, Any] = {
        "notification_master_enabled": master_enabled,
    }
    if not master_enabled:
        return snapshot

    enabled_channels: list[str] = []
    for channel in STARTUP_NOTIFICATION_CHANNEL_CODES:
        if _as_bool(_read_config_value(f"notify_{channel}_enable", False), False):
            enabled_channels.append(channel)

    snapshot.update(
        {
            "enabled_notification_channels": enabled_channels,
            "notification_level": _resolve_notification_level(),
            "notification_merge": _as_bool(_read_config_value("notify_merge", False), False),
            "notification_send_images": _as_bool(_read_config_value("notify_send_images", True), True),
        }
    )
    return snapshot


def _collect_startup_configuration_snapshot() -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "enabled_features": _collect_enabled_codes(_FEATURE_FLAG_MAP),
    }

    if _as_bool(_read_config_value("activity_enable", False), False):
        snapshot["enabled_activity_features"] = _collect_enabled_codes(_ACTIVITY_FEATURE_FLAG_MAP)

    snapshot.update(_collect_notification_snapshot())
    return snapshot


class Telemetry(metaclass=SingletonMeta):
    def __init__(self):
        self._enabled = False
        self._uuid = ""
        self._secret = ""
        self._version = ""
        self._session: requests.Session | None = None
        self._queue: deque[dict[str, Any]] = deque(maxlen=_QUEUE_MAX)
        self._lock = threading.Lock()
        self._flush_event = threading.Event()
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._system_context: dict[str, Any] = {}
        self._registered = False
        self._startup_time = 0.0
        self._save_id = False
        self._save_secret = False

    def init(self, enabled: bool, telemetry_id: str, telemetry_secret: str, version: str):
        self._enabled = enabled
        self._version = version
        self._system_context = get_system_context()

        if not self._enabled:
            return

        if not telemetry_id:
            self._uuid = uuid.uuid4().hex
            self._save_id = True
        else:
            self._uuid = telemetry_id
            self._save_id = False

        if not telemetry_secret:
            self._secret = uuid.uuid4().hex + uuid.uuid4().hex
            self._save_secret = True
        else:
            self._secret = telemetry_secret
            self._save_secret = False

        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

        try:
            from module.update.download_proxy import get_update_download_requests_proxies
            proxies = get_update_download_requests_proxies()
            if proxies:
                self._session.proxies.update(proxies)
        except Exception:
            pass

        self._worker_thread = threading.Thread(target=self._flush_worker, daemon=True, name="telemetry")
        self._worker_thread.start()
        atexit.register(self.shutdown)

        if self._save_id or self._save_secret:
            self._persist_ids()

        self._startup_time = time.time()

    def _persist_ids(self):
        try:
            from module.config import cfg
            if self._save_id:
                cfg.set_value("telemetry_id", self._uuid)
                self._save_id = False
            if self._save_secret:
                cfg.set_value("telemetry_secret", self._secret)
                self._save_secret = False
        except Exception:
            pass

    def _register(self) -> bool:
        if self._registered:
            return True
        if self._session is None:
            return False
        try:
            resp = self._session.post(
                _REGISTER_ENDPOINT,
                json={"uuid": self._uuid, "secret": self._secret},
                timeout=_REQUEST_TIMEOUT,
            )
            if resp.status_code in (200, 201, 409):
                self._registered = True
                return True
        except Exception:
            return False
        return False

    def _flush_worker(self):
        while not self._stop_event.is_set():
            self._flush_event.wait(timeout=_FLUSH_INTERVAL)
            self._flush_event.clear()
            self._drain_queue()

    def _drain_queue(self):
        if not self._queue:
            return

        batch: list[dict[str, Any]] = []
        with self._lock:
            while self._queue and len(batch) < _BATCH_SIZE:
                batch.append(self._queue.popleft())

        if not batch:
            return

        if not self._register():
            self._requeue_batch(batch)
            return

        if not self._send_batch(batch):
            self._requeue_batch(batch)

    @staticmethod
    def _strip_internal_fields(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in event.items() if not k.startswith("__")}
            for event in events
        ]

    def _requeue_batch(self, events: list[dict[str, Any]]):
        with self._lock:
            for event in reversed(events):
                retry_count = int(event.get("__retry_count", 0)) + 1
                if retry_count > _MAX_SEND_RETRIES:
                    continue
                event["__retry_count"] = retry_count
                self._queue.appendleft(event)

    def _send_batch(self, events: list[dict[str, Any]]) -> bool:
        if self._session is None:
            return False
        try:
            payload_events = self._strip_internal_fields(events)
            batch_id = uuid.uuid4().hex
            signed_payload = serialize_batch_payload(payload_events, batch_id)
            signature = sign_payload(signed_payload, self._secret)
            body = json.dumps(
                {"batch_id": batch_id, "events": payload_events, "signature": signature},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            resp = self._session.post(_ENDPOINT, data=body.encode("utf-8"), timeout=_REQUEST_TIMEOUT)
            if resp.status_code == 204:
                return True
            if 400 <= resp.status_code < 500 and resp.status_code != 429:
                # 服务端明确拒绝（载荷/签名/版本等永久性问题）：重试只会再次失败，
                # 还会放大服务端压力并触发风控计罚，直接丢弃该批。
                return True
            # 5xx / 429（限流）/ 网络异常：可重试，由上层 __retry_count 控制上限
            return False
        except Exception:
            return False

    def track(self, event_name: str, properties: dict[str, Any] | None = None):
        if not self._enabled:
            return
        try:
            event = build_event(event_name, self._uuid, self._version, properties)
            with self._lock:
                self._queue.append(event)
            if len(self._queue) >= _BATCH_SIZE:
                self._flush_event.set()
        except Exception:
            pass

    def track_startup(self):
        props = dict(self._system_context)
        try:
            props["game_runtime"] = _resolve_game_runtime()
            props.update(_collect_startup_configuration_snapshot())
            props["ocr_mode"] = _resolve_effective_ocr_mode()
            props["language"] = _resolve_effective_language()
        except Exception:
            pass
        self.track(EventName.APP_STARTUP, props)

    def track_shutdown(self):
        duration = time.time() - self._startup_time if self._startup_time else 0
        self.track(EventName.APP_SHUTDOWN, {"session_duration_seconds": round(duration, 1)})

    def track_task_start(self, task_id: str):
        self.track(EventName.TASK_START, {"task_id": task_id})

    def track_task_complete(self, task_id: str, success: bool, duration: float):
        self.track(EventName.TASK_COMPLETE, {
            "task_id": task_id,
            "success": success,
            "duration_seconds": round(duration, 1),
        })

    def track_error(self, error_type: str, error_message: str):
        self.track(EventName.ERROR, {
            "error_type": error_type,
            "error_fingerprint": fingerprint_error(error_message[:200]),
        })

    def track_feature(self, feature: str, value: str):
        self.track(EventName.FEATURE_USAGE, {"feature": feature, "value": value})

    def flush(self):
        self._drain_queue()

    def shutdown(self):
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        self._flush_event.set()
        self.track_shutdown()
        self.flush()
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
