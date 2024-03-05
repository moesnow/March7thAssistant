import io
from typing import Optional
from module.logger import Logger
from utils.singleton import SingletonMeta
from .notifier import Notifier


class Notify(metaclass=SingletonMeta):
    """
    通知管理类，负责管理和发送不同类型的通知。
    """

    def __init__(self, title: str, logger: Optional[Logger] = None):
        """
        初始化通知管理类。

        :param title: 通知标题。
        :param logger: 用于记录日志的Logger对象，可选。
        """
        self.title = title
        self.logger = logger
        self.notifiers = {}  # 存储不同类型的通知发送者实例

    def set_notifier(self, notifier_name: str, notifier: Notifier):
        """
        设置或更新一个通知发送者实例。

        :param notifier_name: 通知发送者的名称。
        :param notifier: 通知发送者的实例，应当实现Notifier接口。
        """
        self.notifiers[notifier_name] = notifier

    def _process_image(self, image: Optional[io.BytesIO | str]) -> Optional[io.BytesIO]:
        """
        根据image的类型处理图片，以确保它是io.BytesIO对象。

        :param image: 可以是io.BytesIO对象或文件路径字符串，可选。
        :return: io.BytesIO对象或None（如果image为None或处理失败）。
        """
        if isinstance(image, str):
            try:
                with open(image, 'rb') as file:
                    return io.BytesIO(file.read())
            except Exception as e:
                if self.logger:
                    self.logger.error(f"图片读取失败: {e}")
                return None
        elif isinstance(image, io.BytesIO):
            return image
        else:
            return None

    def notify(self, content: str = "", image: Optional[io.BytesIO | str] = None):
        """
        遍历所有设置的通知发送者，发送通知。

        :param content: 通知的内容。
        :param image: 通知的图片，可以是io.BytesIO对象或文件路径字符串，可选。
        """
        for notifier_name, notifier in self.notifiers.items():
            processed_image = self._process_image(image)  # 根据image的类型进行处理
            try:
                if processed_image and notifier.supports_image:
                    notifier.send(self.title, content, processed_image)
                else:
                    notifier.send(self.title, content)
                if self.logger:
                    self.logger.info(f"{notifier_name} 通知发送完成")
            except Exception as e:
                if self.logger:
                    self.logger.error(f"{notifier_name} 通知发送失败: {e}")
