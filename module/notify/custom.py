import base64
from .notifier import Notifier
from onepush import get_notifier
from ruamel.yaml import comments


class CustomNotifier(Notifier):
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

    def send(self, title: str, content: str, image_io=None):
        # 发送通知
        n = get_notifier("custom")
        if self.params["datatype"] == "json":
            raw_data = self.comment_init(self.params["data"])
            message = "\n".join(filter(None, [title, content]))
            base64_str = base64.b64encode(image_io.getvalue()).decode() if image_io else ""

            if base64_str:
                raw_data["message"].append(self.comment_init(self.params.get("image", "")))

            data = self.comment_format(raw_data, "text", "file", message=message, image=base64_str)
            self.params["data"] = data
            response = n.notify(**self.params)
