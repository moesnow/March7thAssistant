import io
from typing import Dict, Any, Optional
import requests
from utils.logger.logger import Logger
from .notifier import Notifier


class GotifyNotifier(Notifier):
    """Gotify 私有通知服务通知器。"""

    def __init__(self, params: Dict[str, Any], logger: Logger):
        """
        初始化 Gotify 通知器。

        :param params: 发送通知所需的参数字典。
        :param logger: 日志记录器实例。
        """
        super().__init__(params, logger)
        self.url = params.get("url")
        self.token = params.get("token")
        if not self.url or not self.token:
            raise ValueError("URL and Token are required for GotifyNotifier")
        try:
            self.priority = int(params.get("priority", 0))
        except (TypeError, ValueError):
            self.priority = 0

    def send(self, title: str, content: str, image_io: Optional[io.BytesIO] = None):
        """
        发送 Gotify 通知。

        :param title: 通知标题。
        :param content: 通知内容。
        :param image_io: 可选，发送的图片，为 io.BytesIO 对象。（Gotify 不支持直接发送图片）
        """
        # Gotify 要求消息内容非空
        if not content:
            content = "."
        url = f"{self.url.rstrip('/')}/message?token={self.token}"
        data = {"title": title, "message": content, "priority": self.priority}

        try:
            response = requests.post(url, json=data, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            self.logger.error(f"Gotify 通知发送失败: {e}")
