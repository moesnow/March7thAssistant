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
            "message": message
        }

        def post(message_type: str):
            if message_type == 'private':
                payload_private = payload.copy()
                payload_private["user_id"] = user_id
                payload_private["message_type"] = message_type
                response = requests.post(endpoint, data=json.dumps(payload_private), headers=headers)
                response.raise_for_status()
            elif message_type == 'group':
                payload_group = payload.copy()
                payload_group["group_id"] = group_id
                payload_group["message_type"] = message_type
                response = requests.post(endpoint, data=json.dumps(payload_group), headers=headers)
                response.raise_for_status()
            else:
                raise ValueError("必须提供 user_id 与 group_id 其中之一")
        
        # 根据消息类型发送消息
        if user_id:
            post('private')
        if group_id:
            post('group')
        if not user_id and not group_id:
            post('error')
