import json
import requests
import base64
from io import BytesIO
from .notifier import Notifier


class OnebotNotifier(Notifier):
    def _get_supports_image(self):
        return True

    def send(self, title: str, content: str, image_io: BytesIO = None):
        endpoint = self.params.get("endpoint", "").rstrip("/")
        message_type = self.params.get("message_type", "private")
        token = self.params.get("token", "")
        user_id = self.params.get("user_id", "")
        group_id = self.params.get("group_id", "")

        # 确保endpoint正确格式化，末尾无斜杠，正确添加“/send_msg”
        if not endpoint.endswith("/send_msg"):
            endpoint += "/send_msg"

        # 构建请求头部，如果提供了token，则添加到头部
        headers = {
            'Content-Type': "application/json",
            'Authorization': f"Bearer {token}" if token else ""
        }

        # 构建消息内容
        message_content = title if not content else f'{title}\n{content}' if title else content

        # 构建消息负载，包括文本和可选的图片
        message = [{
            "type": "text",
            "data": {
                "text": message_content
            }
        }]

        # 如果有图片，则添加到消息中
        if image_io:
            image_base64 = base64.b64encode(image_io.getvalue()).decode('utf-8')
            message.append({
                "type": "image",
                "data": {
                    "file": f'base64://{image_base64}'
                }
            })

        payload = {
            "message_type": message_type,
            "message": message
        }
        
        # 根据消息类型给载荷添加对应的ID字段
        if message_type == "private":
            payload["user_id"] = user_id
        elif message_type == "group":
            payload["group_id"] = group_id

        # 发送POST请求
        response = requests.post(endpoint, data=json.dumps(payload), headers=headers)
        response.raise_for_status()
