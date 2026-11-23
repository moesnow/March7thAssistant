"""Last per-channel delivery. Only fixed reason codes and numeric HTTP status reach disk."""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import logging
import sqlite3

from module.channel_catalog import CHANNEL_BY_ID
from module.localization import tr
from utils import paths

REASONS = {
    "rejected": "服务未接受消息，请检查渠道配置",
    "timeout": "连接超时，请检查网络或代理",
    "connection": "无法连接推送服务",
    "config": "推送参数无效，请检查渠道配置",
    "auth": "推送服务拒绝了身份验证。请打开此渠道的编辑窗口，核对机器人密钥和收件人，再发送一条测试消息。",
    "failed": "发送失败，请检查渠道配置",
}


@dataclass(frozen=True)
class SendFailure:
    code: str

    def __bool__(self):
        return False


@dataclass(frozen=True)
class Delivery:
    at: str
    success: bool
    code: str = ""

    @property
    def reason(self):
        if self.success:
            return tr("发送成功")
        if self.code.startswith("http_") and self.code[5:].isdigit():
            return tr("服务返回 HTTP {status}").format(status=self.code[5:])
        return tr(REASONS.get(self.code, REASONS["failed"]))


def failure_code(error):
    from requests import exceptions
    from smtplib import SMTPAuthenticationError
    status = getattr(getattr(error, "response", None), "status_code", None)
    if type(status) is int and 100 <= status <= 599:
        return f"http_{status}"
    if isinstance(error, (TimeoutError, exceptions.Timeout)):
        return "timeout"
    if isinstance(error, (exceptions.ConnectionError, ConnectionError)):
        return "connection"
    if isinstance(error, SMTPAuthenticationError):
        return "auth"
    if isinstance(error, (KeyError, TypeError, ValueError)):
        return "config"
    return "failed"


def send_one(notifier, title, content, image=None):
    try:
        result = notifier.send(title, content) if image is None else notifier.send(title, content, image)
        if isinstance(result, SendFailure):
            code = result.code
        else:
            code = "rejected" if result is False else ""
    except Exception as exc:
        code = failure_code(exc)
    return Delivery(datetime.now(timezone.utc).isoformat(), not code, code)


def database_path():
    return paths.layout().storage / "state" / "notifications.sqlite3"


def record(channel_id, result, path=None):
    if channel_id not in CHANNEL_BY_ID:
        return
    try:
        path = Path(path) if path is not None else database_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        code = result.code
        if code not in REASONS and not (code.startswith("http_") and len(code) == 8 and code[5:].isascii() and code[5:].isdigit()):
            code = "" if result.success else "failed"
        db = sqlite3.connect(path, timeout=0.05)
        try:
            with db:
                db.execute("CREATE TABLE IF NOT EXISTS last_send (channel TEXT PRIMARY KEY, at TEXT, ok INTEGER, code TEXT)")
                db.execute("INSERT INTO last_send VALUES (?, ?, ?, ?) ON CONFLICT(channel) DO UPDATE SET "
                           "at=excluded.at, ok=excluded.ok, code=excluded.code WHERE excluded.at >= last_send.at",
                           (channel_id, result.at, int(result.success), code))
        finally:
            db.close()
    except Exception as exc:
        logging.getLogger(__name__).warning("推送结果未保存（%s）", type(exc).__name__)


def read_results(path=None):
    try:
        path = Path(path) if path is not None else database_path()
        if not path.is_file():
            return {}
        db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.05)
        try:
            return {channel: Delivery(at, bool(ok), code) for channel, at, ok, code in
                    db.execute("SELECT channel, at, ok, code FROM last_send") if channel in CHANNEL_BY_ID}
        finally:
            db.close()
    except (OSError, sqlite3.Error):
        return {}
