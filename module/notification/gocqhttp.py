import base64
import io
from typing import Optional
import requests
from .notifier import Notifier


class GocqhttpNotifier(Notifier):
    """Go-cqhttp 通知器。"""

    def _get_supports_image(self):
        return True

    def send(self, title: str, content: str, image_io: Optional[io.BytesIO] = None):
        """
        发送 Go-cqhttp 通知，支持通过 CQ 码发送图片。

        :param title: 通知标题。
        :param content: 通知内容。
        :param image_io: 可选，发送的图片，为 io.BytesIO 对象。
        """
        endpoint = self.params.get("endpoint")
        if not endpoint:
            raise ValueError("Endpoint is required for GocqhttpNotifier")
        if "//" not in endpoint:
            endpoint = f"http://{endpoint}"
        path = self.params.get("path") or "/send_msg"
        url = f"{endpoint.rstrip('/')}{path}"

        if image_io:
            base64_str = base64.b64encode(image_io.getvalue()).decode()
            cq_code = f"[CQ:image,file=base64://{base64_str}]"
            content = content + cq_code if content else cq_code

        data = {
            "access_token": self.params.get("token"),
            "message_type": self.params.get("message_type"),
            "user_id": self.params.get("user_id"),
            "group_id": self.params.get("group_id"),
            "message": self.merge_message(title, content),
            "auto_escape": self.params.get("auto_escape", False),
        }

        try:
            response = requests.get(url, params=data, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            self.logger.error(f"Go-cqhttp 通知发送失败: {e}")
