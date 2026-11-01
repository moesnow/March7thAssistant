import os
from .notifier import Notifier
from winotify import Notification, audio
import time


class WinotifyNotifier(Notifier):
    def send(self, title: str, content: str):
        toast = Notification(app_id="March7thAssistant",
                             title=title,
                             msg=content,
                             icon=os.path.join(os.getcwd(), "assets", "screenshot", "March7th.png"),
                             duration="short")
        toast.set_audio(audio.Mail, loop=False)
        toast.show()
        time.sleep(7)
