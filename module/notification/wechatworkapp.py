import json
import requests
from .notifier import Notifier


class WeChatworkappNotifier(Notifier):
    def _get_supports_image(self):
        return True

    def _get_access_token(self) -> str:
        """
        获取访问令牌。

        :return: 返回访问令牌字符串。
        """
        access_token_api = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={self.corpid}&corpsecret={self.corpsecret}"
        response = requests.get(access_token_api)
        response.raise_for_status()
        response = response.json()
        if response['errcode'] == 0:
            return response['access_token']
        else:
            raise Exception(response['errmsg'])

    def _upload_file(self, upload_file, type="file") -> str:
        """
        上传文件到微信服务器。

        :param upload_file: 要上传的文件，为BytesIO对象。
        :param type: 上传文件的类型，默认为"file"。
        :return: 返回上传文件的media_id。
        """
        headers = {"Content-Type": "multipart/form-data"}
        upload_api = f"https://qyapi.weixin.qq.com/cgi-bin/media/upload?access_token={self.access_token}&type={type}"
        response = requests.post(upload_api, headers=headers, files={"media": upload_file})
        response.raise_for_status()
        response = response.json()
        if response['errcode'] == 0:
            return response['media_id']
        else:
            raise Exception(response['errmsg'])

    def send_image(self, image):
        """
        发送图片消息。

        :param image: 要发送的图片，为BytesIO对象。
        """
        media_id = self._upload_file(image, "image")
        headers = {"Content-Type": "application/json"}
        message = {
            "touser": self.touser,
            "msgtype": "image",
            "agentid": self.agentid,
            "image": {"media_id": media_id},
            "safe": 0,
        }
        send_api = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={self.access_token}"
        response = requests.post(send_api, headers=headers, data=json.dumps(message))
        response.raise_for_status()
        response = response.json()
        if response['errcode'] != 0:
            raise Exception(response['errmsg'])

    def send_text(self, text: str):
        """
        发送文本消息。

        :param text: 要发送的文本内容。
        """
        headers = {"Content-Type": "application/json"}
        message = {
            "touser": self.touser,
            "msgtype": "text",
            "agentid": self.agentid,
            "text": {"content": text},
            "safe": 0,
        }
        send_api = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={self.access_token}"
        response = requests.post(send_api, headers=headers, data=json.dumps(message))
        response.raise_for_status()
        response = response.json()
        if response['errcode'] != 0:
            raise Exception(response['errmsg'])

    def send(self, title: str, content: str, image_io=None):
        """
        发送通知。

        :param title: 通知的标题（微信消息不使用标题，此参数将被忽略）。
        :param content: 通知的文本内容。
        :param image_io: 可选，发送的图片，为BytesIO对象。
        """
        self.corpid = self.params["corpid"]
        self.corpsecret = self.params["corpsecret"]
        self.agentid = self.params["agentid"]
        self.touser = self.params["touser"]
        self.access_token = self._get_access_token()

        # 构建消息文本
        message = title if not content else f'{title}\n{content}' if title else content

        self.send_text(message)
        if image_io:
            self.send_image(image_io)
