import requests
import io
from typing import Dict, Any, Optional
from utils.logger.logger import Logger
from .notifier import Notifier


class MeoWNotifier(Notifier):
    def __init__(self, params: Dict[str, Any], logger: Logger):
        """
        初始化 MeoW 通知器。

        :param params: 初始化通知发送者所需的参数字典。
        :param logger: 用于记录日志的 Logger 实例。
        """
        super().__init__(params, logger)
        self.nickname = params.get('nickname')

        if not self.nickname:
            raise ValueError("Nickname is required for MeoWNotifier")

    def send(self, title: str, content: str, image_io: Optional[io.BytesIO] = None):
        """
        使用 MeoW 发送通知。

        :param title: 通知标题。
        :param content: 通知内容。
        :param image_io: 可选，发送的图片，为 io.BytesIO 对象。（MeoW 暂时不支持直接发送图片。）
        """
        # 根据 nickname 决定 URL
        url = f"https://api.chuckfang.com/{self.nickname}/"

        params = {
            'title': title,
            'msg': content,
        }
        headers = {
            'Content-Type': 'application/json;charset=utf-8'
        }

        # 发送请求
        try:
            response = requests.post(url, json=params, headers=headers)
            response.raise_for_status()  # 检查请求是否成功
            result = response.json()
            if result.get("status") != 200:
                self.logger.error(f"MeoW3 通知发送失败: {result.get('message')}")
        except requests.RequestException as e:
            self.logger.error(f"MeoW3 通知发送失败: {e}")
