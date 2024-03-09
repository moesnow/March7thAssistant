import os
from .notifier import Notifier
from winotify import Notification, audio


class WinotifyNotifier(Notifier):
    def send(self, title: str, content: str):
        toast = Notification(app_id="March7thAssistant",
                             title=title,
                             msg=content,
                             icon=os.path.join(os.getcwd(), "assets", "app", "images", "March7th.jpg"))
        toast.set_audio(audio.Mail, loop=False)
        toast.show()
