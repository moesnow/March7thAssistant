import base64
import io
import json
import secrets
from typing import Dict, Any, Optional
import requests
from utils.logger.logger import Logger
from .notifier import Notifier


class BarkNotifier(Notifier):
    """
    Bark 通知器。

    支持官方服务器与自建服务器，以及可选的端到端加密推送（cipherkey + ciphermethod）。
    """

    DEFAULT_BASE_URL = "https://api.day.app/push"

    # 配置参数名 -> Bark 接口字段名
    FIELD_MAPPING = {
        "group": "group",
        "icon": "icon",
        "isarchive": "isArchive",
        "sound": "sound",
        "url": "url",
        "copy": "copy",
        "autocopy": "autoCopy",
    }

    def __init__(self, params: Dict[str, Any], logger: Logger):
        """
        初始化 Bark 通知器。

        :param params: 发送通知所需的参数字典。
        :param logger: 日志记录器实例。
        """
        super().__init__(params, logger)
        self.key = params.get("key") or params.get("device_key")
        if not self.key:
            raise ValueError("Key is required for BarkNotifier")
        self.base_url = params.get("base_url") or self.DEFAULT_BASE_URL

    def send(self, title: str, content: str, image_io: Optional[io.BytesIO] = None):
        """
        发送 Bark 通知。

        :param title: 通知标题。
        :param content: 通知内容。
        :param image_io: 可选，发送的图片，为 io.BytesIO 对象。（Bark 仅支持图片 URL，不支持直接发送图片）
        """
        url = self.base_url if self.base_url.endswith("/push") else f"{self.base_url}/push"

        data = {"device_key": self.key, "title": title, "body": content}
        for param_name, field_name in self.FIELD_MAPPING.items():
            value = self.params.get(param_name)
            if value not in (None, ""):
                data[field_name] = value

        cipherkey = self.params.get("cipherkey")
        ciphermethod = self.params.get("ciphermethod")
        if cipherkey and ciphermethod:
            data = self._encrypt_data(data, cipherkey, ciphermethod)

        try:
            response = requests.post(url, json=data, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            self.logger.error(f"Bark 通知发送失败: {e}")

    def _encrypt_data(self, data: Dict[str, Any], key: str, method: str) -> Dict[str, Any]:
        """
        使用 AES 加密推送数据。需先在 Bark APP 中配置相同的密钥与算法。

        :param data: 待加密的推送数据。
        :param key: 加密密钥。
        :param method: 加密算法，可选值：cbc、ecb。
        :return: 加密后的推送数据。
        """
        # 加密推送依赖 pycryptodome（随 matrix-nio 一同安装），仅在使用加密时导入
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import pad
        except ImportError:
            raise ValueError("Bark 加密推送需要 pycryptodome 依赖")

        body = json.dumps(data)
        method = method.lower()
        if method == "cbc":
            iv = base64.b64encode(secrets.token_bytes(int(AES.block_size / 4 * 3)))
            cipher = AES.new(key.encode(), AES.MODE_CBC, iv=iv)
            cipher_bytes = cipher.encrypt(pad(body.encode(), AES.block_size))
            ciphertext = base64.b64encode(cipher_bytes).decode("ascii")
            return {"ciphertext": ciphertext, "iv": iv.decode("ascii")}
        elif method == "ecb":
            cipher = AES.new(key.encode(), AES.MODE_ECB)
            cipher_bytes = cipher.encrypt(pad(body.encode(), AES.block_size))
            ciphertext = base64.b64encode(cipher_bytes).decode("ascii")
            return {"ciphertext": ciphertext}
        else:
            raise ValueError(f"不支持的 Bark 加密算法: {method}，可选值：cbc、ecb")
