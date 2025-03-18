# 导入所需的模块和类
import io
from typing import Dict, Any, Optional
from utils.logger.logger import Logger
from .notifier import Notifier
import requests
from requests_toolbelt import MultipartEncoder
import hashlib
import base64
import hmac
import time
from module.logger import log

# 定义一个通知发送器类，用于发送飞书（Lark）通知
class LarkNotifier(Notifier):
    # 生成签名的方法，用于验证通知的合法性和时间戳
    def gen_sign(self, timestamp, secret):
        string_to_sign = '{}\n{}'.format(timestamp, secret)
        hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
        sign = base64.b64encode(hmac_code).decode('utf-8')
        return sign
    
    # 确定是否支持发送图片的方法
    def _get_supports_image(self) -> bool:
        """
        确定该通知发送者是否支持发送图片。

        :return: 默认返回False，表示不支持发送图片。
        """
        return True

    # 发送通知的方法，支持发送图片
    def send(self, title: str, content: str, image_io: Optional[io.BytesIO] = None):
        """
        发送通知的方法，需要在子类中实现。
        :param title: 通知的标题。
        :param content: 通知的内容。
        :param image_io: 可选，发送的图片，为io.BytesIO对象。
        :raises NotImplementedError: 如果子类没有实现这个方法，则抛出异常。
        """
        # 获取通知所需的参数
        if content and (content is None or content == ''):
            content = '.'
        webhook = self.params["webhook"]

        imageenable = self.params["imageenable"]
        # 图片功能已启用，且需要发送图片
        if imageenable and image_io is not None:
            # 获取飞书的认证令牌
            auth_endpoint = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            auth_headers = {
                "Content-Type": "application/json; charset=utf-8"
            }
            auth_response = requests.post(auth_endpoint, headers=auth_headers, json={
                "app_id": self.params["appid"],
                "app_secret": self.params["secret"]
            })
            auth_response.raise_for_status()
            tenant_access_token = auth_response.json()["tenant_access_token"]

            # 上传图片并获取图片的image_key
            image_endpoint = "https://open.feishu.cn/open-apis/im/v1/images"
            image_headers = {
                "Content-Type": "multipart/form-data; boundary=---7MA4YWxkTrZu0gW",
                "Authorization": f"Bearer {tenant_access_token}"
            }
            form = {'image_type': 'message', 'image': (image_io)}
            multi_form = MultipartEncoder(form)
            image_headers['Content-Type'] = multi_form.content_type
            image_response = requests.post(image_endpoint , headers=image_headers, data=multi_form)
            if (image_response.status_code % 100 != 2):
                log.error(image_response.text)
                image_response.raise_for_status()
            image_key = image_response.json()["data"]["image_key"]

            # 构造发送的消息内容
            if self.params.get("keyword", None) is not None:
                if self.params["keyword"] != '':
                    content = content + '\n' + self.params["keyword"]

            send_message = {
                "msg_type": "post",
                "content": {
                    "post": {
                        "zh_cn": {
                            "title": title,
                            "content": [
                                [{
                                    "tag": "text",
                                    "text": content
                                }, {
                                    "tag": "img",
                                    "image_key": image_key
                                }]
                            ]
                        }
                    }
                }
            }

        # 不需要发送图片 或图片功能未启用
        else:
            send_message = {
                "msg_type": "post",
                "content": {
                    "post": {
                        "zh_cn": {
                            "title": title,
                            "content": [
                                [{
                                    "tag": "text",
                                    "text": content
                                }]
                            ]
                        }
                    }
                }
            }
        # 如果需要签名
        if self.params.get("sign", None) is not None and self.params["sign"] != '':
            sign = self.params["sign"]
            timestamp = str(int(time.time()))
            send_message.update({
                "timestamp": timestamp,
                "sign": self.gen_sign(timestamp, sign)
            })
        # 发送通知
        send_response = requests.post(webhook, json=send_message)
        send_response.raise_for_status()