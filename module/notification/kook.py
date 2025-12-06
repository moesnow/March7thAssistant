import io
import requests
from typing import Optional
from .notifier import Notifier


class KOOKNotifier(Notifier):
    """
    KOOK机器人通知发送器
    支持通过HTTP请求发送消息到私聊或频道
    官方文档: https://developer.kookapp.cn/doc/intro
    """

    def _get_supports_image(self) -> bool:
        """
        KOOK支持发送图片
        """
        return True

    def _upload_image(self, image_io: io.BytesIO, headers: dict) -> str:
        """
        上传图片到KOOK并获取图片URL

        :param image_io: 图片的BytesIO对象
        :param headers: 请求头
        :return: 图片URL，如果上传失败返回空字符串
        """
        # KOOK图片上传API
        upload_url = "https://www.kookapp.cn/api/v3/asset/create"

        # 准备文件 - 使用通用的 image/png 格式
        files = {
            'file': ('image.png', image_io.getvalue(), 'image/png')
        }

        # 上传图片时不需要Content-Type: application/json
        upload_headers = {
            "Authorization": headers["Authorization"]
        }

        try:
            response = requests.post(upload_url, headers=upload_headers, files=files)
            response.raise_for_status()
            response_data = response.json()

            # 检查API响应
            if response_data.get("code") != 0:
                raise Exception(f"KOOK图片上传失败: {response_data.get('message', '未知错误')}")

            # 返回图片URL，确保URL有效
            image_url = response_data.get("data", {}).get("url", "")
            if not image_url:
                raise Exception("KOOK图片上传成功但未返回图片URL")
            
            return image_url

        except requests.RequestException as e:
            raise Exception(f"KOOK图片上传失败: {str(e)}")

    def send(self, title: str, content: str, image_io: Optional[io.BytesIO] = None):
        """
        发送KOOK通知

        :param title: 通知的标题
        :param content: 通知的内容
        :param image_io: 可选，发送的图片，为io.BytesIO对象
        """
        # 获取必需的token参数
        token = self.params.get("token", "")
        if not token:
            raise ValueError("KOOK token 未配置")

        # 获取目标ID（用户ID或频道ID）
        target_id = self.params.get("target_id", "")
        if not target_id:
            raise ValueError("KOOK target_id 未配置")

        # 获取消息类型，默认为私聊(1)
        # 1 = 私聊, 9 = 频道聊天
        chat_type = self.params.get("chat_type", "1")
        
        # 验证消息类型
        if chat_type not in ["1", "9"]:
            if self.logger:
                self.logger.warning(f"无效的 chat_type: {chat_type}，使用默认值 '1'")
            chat_type = "1"

        # 构建消息文本
        if title and content:
            message = f'**{title}**\n{content}'
        elif title:
            message = title
        else:
            message = content

        # 设置请求头
        headers = {
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json"
        }

        # API端点
        api_url = "https://www.kookapp.cn/api/v3/message/create"

        try:
            # 先发送文本消息
            payload = {
                "type": chat_type,
                "target_id": target_id,
                "content": message
            }

            response = requests.post(api_url, json=payload, headers=headers)
            response.raise_for_status()
            response_data = response.json()

            # 检查API响应
            if response_data.get("code") != 0:
                raise Exception(f"KOOK消息发送失败: {response_data.get('message', '未知错误')}")

            # 如果有图片，上传并发送图片消息
            if image_io:
                try:
                    # 上传图片获取URL
                    image_url = self._upload_image(image_io, headers)

                    # 发送图片消息
                    image_payload = {
                        "type": chat_type,
                        "target_id": target_id,
                        "content": image_url
                    }

                    image_response = requests.post(api_url, json=image_payload, headers=headers)
                    image_response.raise_for_status()
                    image_response_data = image_response.json()

                    if image_response_data.get("code") != 0:
                        # 图片发送失败不抛出异常，仅记录日志
                        if self.logger:
                            self.logger.warning(f"KOOK图片发送失败: {image_response_data.get('message', '未知错误')}")
                except Exception as e:
                    # 图片发送失败不影响整体通知，仅记录日志
                    if self.logger:
                        self.logger.warning(f"KOOK图片处理失败: {str(e)}")

        except requests.RequestException as e:
            raise Exception(f"KOOK通知发送失败: {str(e)}")

