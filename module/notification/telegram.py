import requests

from .pac import match_proxy
from .notifier import Notifier

class TelegramNotifier(Notifier):
    def _get_supports_image(self):
        return True

    def send(self, title: str, content: str, image_io=None):
        token = self.params["token"]
        chat_id = self.params["userid"]
        api_url = self.params.get("api_url", "api.telegram.org")
        proxies = match_proxy(self.params.get("proxies", None), f"https://{api_url}/")

        # 构建消息文本
        message = title if not content else f'{title}\n{content}' if title else content

        if image_io:
            # 发送带图片的消息
            tgurl = f"https://{api_url}/bot{token}/sendPhoto"
            files = {
                'photo': ('image.jpg', image_io.getvalue(), 'image/jpeg'),
                'chat_id': (None, chat_id),
                'caption': (None, message)
            }
            response = requests.post(tgurl, files=files, proxies=proxies)
            response.raise_for_status()
        else:
            # 只发送文本消息
            tgurl = f"https://{api_url}/bot{token}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': message
            }
            response = requests.post(tgurl, data=data, proxies=proxies)
            response.raise_for_status()
