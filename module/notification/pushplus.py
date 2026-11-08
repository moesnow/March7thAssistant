import io
from typing import Dict, Any, Optional
import requests
from utils.logger.logger import Logger
from .notifier import Notifier


class PushPlusNotifier(Notifier):
    """Pushplus 推送加通知器。"""

    BASE_URL = "https://www.pushplus.plus/send"

    def __init__(self, params: Dict[str, Any], logger: Logger):
        """
        初始化 Pushplus 通知器。

        :param params: 发送通知所需的参数字典。
        :param logger: 日志记录器实例。
        """
        super().__init__(params, logger)
        self.token = params.get("token")
        if not self.token:
            raise ValueError("Token is required for PushPlusNotifier")

    def send(self, title: str, content: str, image_io: Optional[io.BytesIO] = None):
        """
        发送 Pushplus 通知。

        :param title: 通知标题。
        :param content: 通知内容。
        :param image_io: 可选，发送的图片，为 io.BytesIO 对象。（Pushplus 不支持直接发送图片）
        """
        # Pushplus 要求消息内容非空
        if not content:
            content = "."
        data = {
            "token": self.token,
            "title": title,
            "content": content,
            "template": "markdown" if self.params.get("markdown") else "html",
            "topic": self.params.get("topic"),
            "channel": self.params.get("channel"),
            "webhook": self.params.get("webhook"),
            "callbackUrl": self.params.get("callbackUrl"),
        }

        try:
            response = requests.post(self.BASE_URL, json=data, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            self.logger.error(f"Pushplus 通知发送失败: {e}")
