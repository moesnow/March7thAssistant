import io
from typing import Dict, Any, Optional
import requests
from utils.logger.logger import Logger
from .notifier import Notifier


class ServerChanTurboNotifier(Notifier):
    """Server酱·Turbo 版通知器。"""

    BASE_URL = "https://sctapi.ftqq.com/{}.send"

    def __init__(self, params: Dict[str, Any], logger: Logger):
        """
        初始化 Server酱·Turbo 通知器。

        :param params: 发送通知所需的参数字典。
        :param logger: 日志记录器实例。
        """
        super().__init__(params, logger)
        self.sctkey = params.get("sctkey")
        if not self.sctkey:
            raise ValueError("Sctkey is required for ServerChanTurboNotifier")

    def send(self, title: str, content: str, image_io: Optional[io.BytesIO] = None):
        """
        发送 Server酱·Turbo 通知。

        :param title: 通知标题。
        :param content: 通知内容。
        :param image_io: 可选，发送的图片，为 io.BytesIO 对象。（Server酱 暂时不支持直接发送图片）
        """
        url = self.BASE_URL.format(self.sctkey)
        data = {"text": title, "desp": content}
        for param_name in ("channel", "openid"):
            value = self.params.get(param_name)
            if value not in (None, ""):
                data[param_name] = value

        try:
            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            if result.get("code") != 0:
                self.logger.error(f"Server酱·Turbo 通知发送失败: {result.get('message')}")
        except requests.RequestException as e:
            self.logger.error(f"Server酱·Turbo 通知发送失败: {e}")
