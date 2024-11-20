import requests
import re
import io
from typing import Dict, Any, Optional
from utils.logger.logger import Logger
from .notifier import Notifier


class ServerChanNotifier(Notifier):
    def __init__(self, params: Dict[str, Any], logger: Logger):
        """
        初始化 ServerChan 通知器。

        :param params: 初始化通知发送者所需的参数字典。
        :param logger: 用于记录日志的 Logger 实例。
        """
        super().__init__(params, logger)
        self.sendkey = params.get('sendkey')

        if not self.sendkey:
            raise ValueError("Sendkey is required for ServerChanNotifier")

    def send(self, title: str, content: str, image_io: Optional[io.BytesIO] = None):
        """
        使用 ServerChan 发送通知。
        兼容 ServerChan·Turbo 和 ServerChan·3。

        :param title: 通知标题。
        :param content: 通知内容。
        :param image_io: 可选，发送的图片，为 io.BytesIO 对象。（ServerChan 暂时不支持直接发送图片。但支持 markdown 格式的图片链接）
        """
        # 根据 sendkey 决定 URL（兼容server酱Turbo）
        if self.sendkey.startswith('sctp'):
            match = re.match(r'sctp(\d+)t', self.sendkey)
            if match:
                num = match.group(1)
                url = f'https://{num}.push.ft07.com/send/{self.sendkey}.send'
            else:
                raise ValueError('Invalid sendkey format for Server酱3')
        else:
            url = f'https://sctapi.ftqq.com/{self.sendkey}.send'

        params = {
            'title': title,
            'desp': content,
        }
        headers = {
            'Content-Type': 'application/json;charset=utf-8'
        }

        # 发送请求
        try:
            response = requests.post(url, json=params, headers=headers)
            response.raise_for_status()  # 检查请求是否成功
            result = response.json()
            if result.get("code") != 0:
                self.logger.error(f"ServerChan3 通知发送失败: {result.get('message')}")
        except requests.RequestException as e:
            self.logger.error(f"ServerChan3 通知发送失败: {e}")
