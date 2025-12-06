import requests
import io
from typing import Dict, Any, Optional
from utils.logger.logger import Logger
from .notifier import Notifier


class WebhookNotifier(Notifier):
    def __init__(self, params: Dict[str, Any], logger: Logger):
        """
        初始化 Webhook 通知器。

        :param params: 初始化通知发送者所需的参数字典。
        :param logger: 用于记录日志的 Logger 实例。
        """
        super().__init__(params, logger)
        self.url = params.get('url')
        
        if not self.url:
            raise ValueError("URL is required for WebhookNotifier")

    def _get_supports_image(self) -> bool:
        """
        确定该通知发送者是否支持发送图片。

        :return: 返回 True，表示支持发送图片。
        """
        return True

    def send(self, title: str, content: str, image_io: Optional[io.BytesIO] = None):
        """
        使用 Webhook 发送通知。

        :param title: 通知标题。
        :param content: 通知内容。
        :param image_io: 可选，发送的图片，为 io.BytesIO 对象。
        """
        # 构建消息数据
        data = {
            'title': title,
            'content': content
        }

        try:
            if image_io:
                # 如果有图片，使用 multipart/form-data 发送
                image_io.seek(0)  # 确保从头开始读取
                files = {
                    'image': ('image.png', image_io.getvalue(), 'image/png')
                }
                response = requests.post(self.url, data=data, files=files, timeout=30)
            else:
                # 只发送文本消息
                response = requests.post(self.url, json=data, timeout=30)
            
            response.raise_for_status()  # 检查请求是否成功
            self.logger.info(f"Webhook 通知发送成功: {self.url}")
        except requests.Timeout:
            self.logger.error(f"Webhook 通知发送超时 ({self.url})")
        except requests.RequestException as e:
            self.logger.error(f"Webhook 通知发送失败 ({self.url}): {e}")
