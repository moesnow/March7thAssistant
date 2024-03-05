from typing import Optional
from module.logger import Logger
from utils.singleton import SingletonMeta
from .notifier import Notifier


class Notify(metaclass=SingletonMeta):
    """
    通知管理类，负责管理和发送不同类型的通知。
    """

    def __init__(self, title: str, logger: Optional[Logger] = None):
        self.title = title
        self.logger = logger
        self.notifiers = {}  # 存储不同类型的通知发送者实例

    def set_notifier(self, notifier_name: str, notifier: Notifier):
        """
        设置或更新一个通知发送者。
        """
        self.notifiers[notifier_name] = notifier

    def notify(self, content: str = "", image=None):
        """
        遍历所有设置的通知发送者，发送通知。
        """
        for notifier_name, notifier in self.notifiers.items():
            try:
                if image and notifier.supports_image:
                    notifier.send(self.title, content, image)
                else:
                    notifier.send(self.title, content)
                self.logger.info(f"{notifier_name} 通知发送完成")
            except Exception as e:
                self.logger.error(f"{notifier_name} 通知发送失败: {e}")
