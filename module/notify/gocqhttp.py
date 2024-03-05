import base64
from onepush import get_notifier
from .notifier import Notifier


class GocqhttpNotifier(Notifier):
    def _get_supports_image(self):
        return True

    def send(self, title: str, content: str, image_io=None):
        n = get_notifier("gocqhttp")
        if image_io:
            base64_str = base64.b64encode(image_io.getvalue()).decode()
            cq_code = f"[CQ:image,file=base64://{base64_str}]"
            content = content + cq_code if content else cq_code
        n.notify(**self.params, title=title, content=content)
