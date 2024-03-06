import os
from .notifier import Notifier
from winotify import Notification, audio


class WinotifyNotifier(Notifier):
    def send(self, title: str, content: str):
        message = title if not content else f'{title}\n{content}'
        toast = Notification(app_id="March7thAssistant",
                             title="",
                             msg=message,
                             icon=os.path.join(os.getcwd(), "assets", "app", "images", "March7th.jpg"))
        toast.set_audio(audio.Mail, loop=False)
        toast.show()
