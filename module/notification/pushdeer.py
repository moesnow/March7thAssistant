import io
from typing import Dict, Any, Optional
import requests
from utils.logger.logger import Logger
from .notifier import Notifier


class PushDeerNotifier(Notifier):
    """Pushdeer 通知器。"""

    DEFAULT_URL = "https://api2.pushdeer.com/message/push"

    def __init__(self, params: Dict[str, Any], logger: Logger):
        """
        初始化 Pushdeer 通知器。

        :param params: 发送通知所需的参数字典。
        :param logger: 日志记录器实例。
        """
        super().__init__(params, logger)
        self.pushkey = params.get("token") or params.get("pushkey")
        if not self.pushkey:
            raise ValueError("Token is required for PushDeerNotifier")
        self.url = params.get("url") or self.DEFAULT_URL

    def send(self, title: str, content: str, image_io: Optional[io.BytesIO] = None):
        """
        发送 Pushdeer 通知。

        :param title: 通知标题。
        :param content: 通知内容。
        :param image_io: 可选，发送的图片，为 io.BytesIO 对象。（Pushdeer 仅支持图片 URL，不支持直接发送图片）
        """
        # Pushdeer 要求消息内容非空
        if not content:
            content = "."
        data = {"pushkey": self.pushkey, "type": self.params.get("type") or "markdown"}
        if title:
            data["text"] = title
            data["desp"] = content
        else:
            data["text"] = content

        try:
            response = requests.post(self.url, json=data, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            self.logger.error(f"Pushdeer 通知发送失败: {e}")
