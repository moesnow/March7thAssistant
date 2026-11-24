"""轮流推送的子运行收件箱。父进程在子进程异常退出时也能读取。"""

import base64
from io import BytesIO
import logging
import os
from pathlib import Path
import threading

from module.localization import tr
from .reasons import reason_text
from utils import runs
from utils.pause import _read_json, _atomic_write_json

_LOCK = threading.Lock()
MAX_IMAGES = 4
IMAGE_BYTES = 512 * 1024
ROUND_IMAGES = 12
RESULT = {
    "success": "成功",
    "partial": "部分完成",
    "failed": "失败",
    "timeout": "超时",
    "skipped": "已跳过",
    "stopped": "已停止",
}


def context():
    session = runs._current_session
    return session.record if session and not session._finished else {}


def _inbox(run_id):
    if not runs.is_valid_run_id(run_id):
        return {}
    path = Path(runs.run_file(run_id, ".notices"))
    try:
        if path.stat().st_size > 6 * 1024 * 1024:
            return {}
    except OSError:
        return {}
    value = _read_json(path)
    return value if isinstance(value, dict) else {}


def collect(notif, record, content, image, level):
    if not record.get("parent_run_id") or os.getenv("M7A_ROTATION_MERGE") != "1":
        return False
    run_id = record["run_id"]
    try:
        with _LOCK:
            data = _inbox(run_id)
            messages = data.setdefault("messages", [])
            if content and len(messages) < 512:
                messages.append(str(content)[:4096])
            images = data.setdefault("images", [])
            if (
                image is not None
                and notif.image_enable
                and notif._has_image_notifier()
                and len(images) < MAX_IMAGES
            ):
                encoded = notif._process_image(image, max_size=(960, 540), quality=75)
                if encoded and encoded.getbuffer().nbytes <= IMAGE_BYTES:
                    images.append(base64.b64encode(encoded.getvalue()).decode("ascii"))
            if level == "error":
                data["error"] = True
            _atomic_write_json(runs.run_file(run_id, ".notices"), data)
    except (OSError, ValueError):
        logging.getLogger(__name__).warning("本账号的部分合并通知未能保存")
    return True


def send_summary(rotation, merge, *, notifier=None):
    if notifier is None:
        from module.notification import notif as notifier
    rows = rotation["accounts"]
    lines = [tr("多账号轮流运行结束")]
    images = []
    any_error = not any(row["status"] == "success" for row in rows)
    for row in rows:
        result = tr(RESULT.get(row["status"], "失败"))
        reason = reason_text(row.get("reason"))
        if reason and reason != result:
            result = tr("{result}（{reason}）").format(result=result, reason=reason)
        lines.append(f"{row['name']} · {result}")
        if merge:
            data = _inbox(row.get("run_id"))
            any_error |= bool(data.get("error"))
            lines.extend(message for message in data.get("messages", []) if isinstance(message, str))
            start = len(images)
            for item in data.get("images", [])[:MAX_IMAGES]:
                if (
                    len(images) >= ROUND_IMAGES
                    or not isinstance(item, str)
                    or len(item) > 4 * ((IMAGE_BYTES + 2) // 3)
                ):
                    continue
                try:
                    from PIL import Image

                    with Image.open(BytesIO(base64.b64decode(item, validate=True))) as source:
                        if source.format != "JPEG" or source.width > 960 or source.height > 540:
                            continue
                        # Equal widths keep the channel's merger from enlarging a narrow image.
                        card = Image.new("RGB", (960, source.height), "white")
                        card.paste(source, (0, 0))
                        images.append(card)
                except (ValueError, OSError, Image.DecompressionBombError):
                    continue
            if len(images) > start:
                lines.append(
                    f"截图 {start + 1}–{len(images)}" if len(images) > start + 1 else f"截图 {start + 1}"
                )
    image = notifier._merge_images(images) if images else None
    notifier.notify(content="\n".join(lines), image=image, level="error" if any_error else "all")


def notify_account_error(session, selector, error, *, notifier=None):
    """AccountError 可发生在选定账号前，通知失败也应保留原退出码。"""
    try:
        if notifier is None:
            from module.notification import notif as notifier
        content = str(error)
        if selector and not session.record.get("account"):
            from .store import AccountStore
            row = next((r for r in AccountStore().index()["accounts"] if r["uid"] == selector), None)
            name = row["name"] if row else selector
            content = f"【{name}】{content}"
        notifier.flush_batch()
        notifier.notify(content=content, level="error")
    except Exception as exc:
        print(f"账号错误通知发送失败（{type(exc).__name__}）", flush=True)
