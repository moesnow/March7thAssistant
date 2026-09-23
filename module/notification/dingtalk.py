import base64
import hashlib
import hmac
import io
import time
import urllib.parse
from typing import Dict, Any, Optional
import requests
from utils.logger.logger import Logger
from .notifier import Notifier


class DingTalkNotifier(Notifier):
    """钉钉自定义机器人通知器。"""

    BASE_URL = "https://oapi.dingtalk.com/robot/send?access_token={}"

    def __init__(self, params: Dict[str, Any], logger: Logger):
        """
        初始化钉钉通知器。

        :param params: 发送通知所需的参数字典。
        :param logger: 日志记录器实例。
        """
        super().__init__(params, logger)
        self.token = params.get("token")
        if not self.token:
            raise ValueError("Token is required for DingTalkNotifier")
        self.secret = params.get("secret")

    @staticmethod
    def gen_sign(secret: str):
        """
        根据加签密钥计算钉钉机器人签名。

        :param secret: 钉钉机器人的加签密钥。
        :return: (timestamp, sign) 元组。
        """
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return timestamp, sign

    def send(self, title: str, content: str, image_io: Optional[io.BytesIO] = None):
        """
        发送钉钉通知。

        :param title: 通知标题。
        :param content: 通知内容。
        :param image_io: 可选，发送的图片，为 io.BytesIO 对象。（钉钉机器人不支持直接发送图片）
        """
        url = self.token if "http" in self.token else self.BASE_URL.format(self.token)
        if self.secret:
            timestamp, sign = self.gen_sign(self.secret)
            url = f"{url}&timestamp={timestamp}&sign={sign}"

        if self.params.get("markdown"):
            data = {"msgtype": "markdown", "markdown": {"title": title, "text": content}}
        else:
            message = self.merge_message(title, content)
            data = {"msgtype": "text", "text": {"content": message}}

        try:
            response = requests.post(url, json=data, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            self.logger.error(f"钉钉通知发送失败: {e}")
