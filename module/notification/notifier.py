import io
from typing import Dict, Any, Optional
from module.logger.logger import Logger


class Notifier:
    def __init__(self, params: Dict[str, Any], logger: Logger):
        """
        初始化Notifier基类。

        :param params: 初始化通知发送者所需的参数字典。
        :param logger: 用于记录日志的Logger实例。
        """
        self.params = params  # 通知参数
        self.logger = logger  # 日志记录器
        self.supports_image = self._get_supports_image()  # 是否支持发送图片

    def _get_supports_image(self) -> bool:
        """
        确定该通知发送者是否支持发送图片。

        :return: 默认返回False，表示不支持发送图片。
        """
        return False

    def send(self, title: str, content: str, image_io: Optional[io.BytesIO] = None):
        """
        发送通知的方法，需要在子类中实现。

        :param title: 通知的标题。
        :param content: 通知的内容。
        :param image_io: 可选，发送的图片，为io.BytesIO对象。
        :raises NotImplementedError: 如果子类没有实现这个方法，则抛出异常。
        """
        raise NotImplementedError("This method should be implemented by subclasses.")
