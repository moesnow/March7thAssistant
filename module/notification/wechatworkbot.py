import base64
import hashlib
import requests
from .notifier import Notifier


class WeChatWorkBotNotifier(Notifier):
    def _get_supports_image(self):
        return True
    
    def _get_webhook_url(self):
        """
        获取webhook URL，如果参数中有key则构建完整的URL
        如果直接提供了webhook_url则使用它
        """
        if "key" in self.params:
            # 使用key参数构建完整的webhook URL
            return f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={self.params['key']}"
        elif "webhook_url" in self.params:
            # 如果直接提供了完整的webhook_url，则使用它
            return self.params["webhook_url"]
        else:
            raise Exception("企业微信机器人配置缺少必要参数: key 或 webhook_url")
    
    def send_image(self, image_io):
        """
        通过企业微信机器人发送图片
        
        :param image_io: 图片的BytesIO对象
        """
        # 获取webhook URL
        webhook_url = self._get_webhook_url()
        
        # 计算图片的base64编码和md5值
        image_data = image_io.getvalue()
        base64_str = base64.b64encode(image_data).decode('utf-8')
        md5_str = hashlib.md5(image_data).hexdigest()
        
        # 构建请求数据
        payload = {
            "msgtype": "image",
            "image": {
                "base64": base64_str,
                "md5": md5_str
            }
        }
        
        # 发送请求
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        response_data = response.json()
        
        # 检查发送结果
        if response_data.get('errcode') != 0:
            raise Exception(f"企业微信机器人发送图片失败: {response_data.get('errmsg')}")
    
    def send_text(self, text: str):
        """
        通过企业微信机器人发送文本消息
        
        :param text: 要发送的文本内容
        """
        # 获取webhook URL
        webhook_url = self._get_webhook_url()
        
        # 构建请求数据
        payload = {
            "msgtype": "text",
            "text": {
                "content": text
            }
        }
        
        # 发送请求
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        response_data = response.json()
        
        # 检查发送结果
        if response_data.get('errcode') != 0:
            raise Exception(f"企业微信机器人发送文本失败: {response_data.get('errmsg')}")
    
    def send(self, title: str, content: str, image_io=None):
        """
        发送通知
        
        :param title: 通知的标题
        :param content: 通知的文本内容
        :param image_io: 可选，发送的图片，为BytesIO对象
        """
        # 构建消息文本
        message = title if not content else f'{title}\n{content}' if title else content
        
        # 发送文本消息
        self.send_text(message)
        
        # 如果有图片，发送图片
        if image_io:
            self.send_image(image_io)