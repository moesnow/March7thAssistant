import io
from typing import Dict, Any, Optional
import requests
from utils.logger.logger import Logger
from .notifier import Notifier


class QmsgNotifier(Notifier):
    """Qmsg 酱 QQ 推送通知器。"""

    BASE_URL = "https://qmsg.zendee.cn/{}/{}"

    def __init__(self, params: Dict[str, Any], logger: Logger):
        """
        初始化 Qmsg 通知器。

        :param params: 发送通知所需的参数字典。
        :param logger: 日志记录器实例。
        """
        super().__init__(params, logger)
        self.key = params.get("key")
        if not self.key:
            raise ValueError("Key is required for QmsgNotifier")

    def send(self, title: str, content: str, image_io: Optional[io.BytesIO] = None):
        """
        发送 Qmsg 通知。

        :param title: 通知标题。
        :param content: 通知内容。
        :param image_io: 可选，发送的图片，为 io.BytesIO 对象。（Qmsg 不支持直接发送图片）
        """
        mode = self.params.get("mode") or "send"
        url = self.BASE_URL.format(mode, self.key)
        data = {"msg": self.merge_message(title, content), "qq": self.params.get("qq")}

        try:
            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            self.logger.error(f"Qmsg 通知发送失败: {e}")
