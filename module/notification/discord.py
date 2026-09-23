import io
from typing import Dict, Any, Optional
import requests
from utils.logger.logger import Logger
from .notifier import Notifier


class DiscordNotifier(Notifier):
    """Discord Webhook 通知器。"""

    DEFAULT_COLOR = 16478873

    def __init__(self, params: Dict[str, Any], logger: Logger):
        """
        初始化 Discord 通知器。

        :param params: 发送通知所需的参数字典。
        :param logger: 日志记录器实例。
        """
        super().__init__(params, logger)
        self.webhook = params.get("webhook")
        if not self.webhook:
            raise ValueError("Webhook is required for DiscordNotifier")

    @staticmethod
    def parse_color(value) -> int:
        """
        解析嵌入消息颜色，支持十进制或十六进制（如 0x3498db）表示。

        :param value: 颜色值，为空或无法解析时返回默认颜色。
        :return: 颜色的整数表示。
        """
        if value in (None, ""):
            return DiscordNotifier.DEFAULT_COLOR
        try:
            return int(str(value).strip(), 0)
        except ValueError:
            return DiscordNotifier.DEFAULT_COLOR

    def send(self, title: str, content: str, image_io: Optional[io.BytesIO] = None):
        """
        发送 Discord 通知。

        :param title: 通知标题。
        :param content: 通知内容。
        :param image_io: 可选，发送的图片，为 io.BytesIO 对象。（Discord Webhook 不支持直接发送图片）
        """
        data = {
            "embeds": [{
                "title": title,
                "description": content,
                "color": self.parse_color(self.params.get("color")),
            }]
        }
        if self.params.get("username"):
            data["username"] = self.params["username"]
        if self.params.get("avatar_url"):
            data["avatar_url"] = self.params["avatar_url"]

        try:
            response = requests.post(self.webhook, json=data, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            self.logger.error(f"Discord 通知发送失败: {e}")
