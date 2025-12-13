import requests
import io
import base64
import json
import copy
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
        self.method = params.get('method', 'POST').upper()
        self.headers = params.get('headers', {})
        self.body_template = params.get('body', None)
        
        if not self.url:
            raise ValueError("URL is required for WebhookNotifier")
        
        # 解析 headers，如果是字符串格式（支持JSON字符串）
        if isinstance(self.headers, str):
            try:
                self.headers = json.loads(self.headers)
            except json.JSONDecodeError:
                self.logger.warning(f"无法解析 headers JSON: {self.headers}，将使用空headers")
                self.headers = {}
        
        # 解析 body_template，如果是字符串格式（支持JSON字符串）
        if isinstance(self.body_template, str):
            try:
                self.body_template = json.loads(self.body_template)
            except json.JSONDecodeError:
                # 保持为字符串模板
                pass

    def _get_supports_image(self) -> bool:
        """
        确定该通知发送者是否支持发送图片。

        :return: 返回 True，表示支持发送图片。
        """
        return True

    def _replace_placeholders(self, obj: Any, title: str, content: str, image_base64: str = "") -> Any:
        """
        递归替换对象中的占位符。

        :param obj: 要处理的对象（可以是字典、列表或字符串）。
        :param title: 通知标题。
        :param content: 通知内容。
        :param image_base64: Base64编码的图片数据。
        :return: 替换占位符后的对象。
        """
        if isinstance(obj, dict):
            return {k: self._replace_placeholders(v, title, content, image_base64) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._replace_placeholders(item, title, content, image_base64) for item in obj]
        elif isinstance(obj, str):
            return obj.replace('{title}', title).replace('{content}', content).replace('{image}', image_base64)
        else:
            return obj

    def send(self, title: str, content: str, image_io: Optional[io.BytesIO] = None):
        """
        使用 Webhook 发送通知。

        :param title: 通知标题。
        :param content: 通知内容。
        :param image_io: 可选，发送的图片，为 io.BytesIO 对象。
        """
        try:
            # 处理图片
            image_base64 = ""
            if image_io:
                image_io.seek(0)
                image_base64 = base64.b64encode(image_io.getvalue()).decode('utf-8')
            
            # 如果有自定义的 body 模板，使用自定义模板
            if self.body_template:
                # 使用深拷贝避免修改原始模板（处理嵌套结构）
                if isinstance(self.body_template, dict):
                    body = self._replace_placeholders(copy.deepcopy(self.body_template), title, content, image_base64)
                elif isinstance(self.body_template, str):
                    body = self._replace_placeholders(self.body_template, title, content, image_base64)
                else:
                    body = self.body_template
                
                # 根据方法和body类型发送请求
                headers = self.headers.copy() if self.headers else {}
                
                if isinstance(body, dict):
                    # 如果body是字典，发送JSON
                    if 'Content-Type' not in headers:
                        headers['Content-Type'] = 'application/json'
                    response = requests.request(
                        method=self.method,
                        url=self.url,
                        json=body,
                        headers=headers,
                        timeout=30
                    )
                else:
                    # 如果body是字符串，发送为文本数据
                    # 注意：如果需要特定的Content-Type，请在headers中明确指定
                    response = requests.request(
                        method=self.method,
                        url=self.url,
                        data=body,
                        headers=headers,
                        timeout=30
                    )
            else:
                # 使用默认格式（保持向后兼容）
                data = {
                    'title': title,
                    'content': content
                }
                
                if image_io:
                    # 如果有图片，使用 multipart/form-data 发送
                    files = {
                        'image': ('image.png', image_io.getvalue(), 'image/png')
                    }
                    response = requests.post(self.url, data=data, files=files, headers=self.headers, timeout=30)
                else:
                    # 只发送文本消息
                    response = requests.post(self.url, json=data, headers=self.headers, timeout=30)
            
            response.raise_for_status()  # 检查请求是否成功
            self.logger.info(f"Webhook 通知发送成功: {self.url}")
        except requests.Timeout:
            self.logger.error(f"Webhook 通知发送超时 ({self.url})")
        except requests.RequestException as e:
            self.logger.error(f"Webhook 通知发送失败 ({self.url}): {e}")
