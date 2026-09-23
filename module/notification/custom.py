import base64
import copy
import io
from typing import Optional
import requests
from .notifier import Notifier
from ruamel.yaml import comments


class CustomNotifier(Notifier):
    """自定义通知器，按配置的请求模板发送通知。"""

    def _get_supports_image(self):
        # 判断是否支持图片
        return True

    def comment_init(self, d):
        # 初始化评论，将ruamel.yaml的特定数据结构转换为普通的dict或list
        if isinstance(d, comments.CommentedMap):
            return {k: self.comment_init(v) for k, v in dict(d).items()}
        elif isinstance(d, comments.CommentedSeq):
            return [self.comment_init(i) for i in list(d)]
        else:
            return d

    def comment_format(self, d, *args, **kwargs):
        # 格式化评论，替换指定的占位符
        if isinstance(d, dict):
            return {k: self.comment_format(v, *args, **kwargs) if k not in args else v.format(**kwargs) for k, v in d.items()}
        elif isinstance(d, list):
            return [self.comment_format(i, *args, **kwargs) for i in d]
        else:
            return d

    def send(self, title: str, content: str, image_io: Optional[io.BytesIO] = None):
        """
        发送自定义通知。

        :param title: 通知标题。
        :param content: 通知内容。
        :param image_io: 可选，发送的图片，为 io.BytesIO 对象。
        """
        url = self.params.get("url")
        if not url:
            raise ValueError("URL is required for CustomNotifier")
        method = self.params.get("method") or "post"
        datatype = self.params.get("datatype") or "data"

        # 每次发送都基于原始模板重新构建，避免多次发送时消息内容被固定
        raw_data = self.comment_init(copy.deepcopy(self.params.get("data") or {}))
        message = "\n".join(filter(None, [title, content]))
        base64_str = base64.b64encode(image_io.getvalue()).decode() if image_io else ""

        # onebot 等接口通过 message 列表追加图片消息段
        if base64_str and datatype == "json" and isinstance(raw_data, dict) and isinstance(raw_data.get("message"), list):
            raw_data["message"].append(self.comment_init(copy.deepcopy(self.params.get("image", ""))))

        data = self.comment_format(raw_data, "text", "file", message=message, image=base64_str)

        try:
            if str(method).upper() == "GET":
                response = requests.request(method, url, params=data, timeout=30)
            elif str(datatype).lower() == "json":
                response = requests.request(method, url, json=data, timeout=30)
            else:
                response = requests.request(method, url, data=data, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            self.logger.error(f"自定义通知发送失败: {e}")
