import requests
from onepush import get_notifier
from managers.logger_manager import logger
from managers.translate_manager import _


class Notify:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.notifiers = {
                "winotify": False,
                "bark": False,
                "custom": False,
                "gocqhttp": False,
                "dingtalk": False,
                "discord": False,
                "pushplus": False,
                "pushdeer": False,
                "qmsg": False,
                "serverchan": False,
                "serverchanturbo": False,
                "smtp": False,
                "telegram": False,
                "wechatworkapp": False,
                "wechatworkbot": False,
                "lark": False
            }
        return cls._instance

    def set_notifier(self, notifier_name, enable, params=None):
        self.notifiers[notifier_name] = enable

        if params:
            setattr(self, notifier_name, params)

    def _send_notification(self, notifier_name, title, content):
        if self.notifiers.get(notifier_name, False):

            if notifier_name == "winotify":
                self._send_notification_by_winotify(title, content)
                return

            if notifier_name == "pushplus":
                content = "." if content is None else content

            notifier_params = getattr(self, notifier_name, None)
            if notifier_params:
                n = get_notifier(notifier_name)
                try:
                    response = n.notify(**notifier_params,
                                        title=title, content=content)
                    logger.info(_("{notifier_name} 通知发送完成").format(
                        notifier_name=notifier_name.capitalize()))
                except Exception as e:
                    logger.error(_("{notifier_name} 通知发送失败").format(
                        notifier_name=notifier_name.capitalize()))
                    logger.error(f"{e}")

    def _send_notification_with_image(self, notifier_name, title, content, image_io):
        if self.notifiers.get(notifier_name, False) and notifier_name == "telegram":
            notifier_params = getattr(self, notifier_name, None)
            if notifier_params:
                token = notifier_params["token"]
                chat_id = notifier_params["userid"]
                api_url = notifier_params["api_url"] if "api_url" in notifier_params else "api.telegram.org"
                tgurl = f"https://{api_url}/bot{token}/sendPhoto"
                message = content
                if title and content:
                    message = '{}\n\n{}'.format(title, content)
                if title and not content:
                    message = title
                files = {
                    'photo': ('merged_image.jpg', image_io.getvalue(), 'image/jpeg'),
                    'chat_id': (None, chat_id),
                    'caption': (None, message)
                    # 'text': (None, " ")
                }
                try:
                    response = requests.post(tgurl, files=files)
                    logger.info(_("{notifier_name} 通知发送完成").format(notifier_name=notifier_name.capitalize()))
                except Exception as e:
                    logger.error(_("{notifier_name} 通知发送失败").format(notifier_name=notifier_name.capitalize()))
                    logger.error(f"{e}")

    def _send_notification_by_winotify(self, title, content):
        import os
        from winotify import Notification, audio

        message = content
        if title and content:
            message = '{}\n{}'.format(title, content)
        if title and not content:
            message = title

        toast = Notification(app_id="March7thAssistant",
                             title="三月七小助手|･ω･)",
                             msg=message,
                             icon=os.getcwd() + "\\assets\\app\\images\\March7th.jpg")
        toast.set_audio(audio.Mail, loop=False)
        toast.show()
        logger.info(_("{notifier_name} 通知发送完成").format(notifier_name="winotify"))

    def notify(self, title="", content="", image_io=None):
        for notifier_name in self.notifiers:
            if image_io and notifier_name == "telegram":
                self._send_notification_with_image(notifier_name, title, content, image_io)
            else:
                self._send_notification(notifier_name, title, content)
