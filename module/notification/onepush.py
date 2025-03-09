from typing import Dict, Any
from .notifier import Notifier
from onepush import get_notifier
from utils.logger.logger import Logger


class OnepushNotifier(Notifier):
    def __init__(self, name: str, params: Dict[str, Any], logger: Logger, require_content: bool = False):
        """
        初始化OnePush通知器。

        :param name: 通知器的名称。
        :param params: 发送通知所需的参数字典。
        :param logger: 日志记录器实例。
        :param require_content: 是否要求通知内容非空，默认为False。
        """
        super().__init__(params, logger)
        self.notifier_name = name  # 通知器名称
        self.require_content = require_content  # 是否要求内容非空

    def send(self, title: str, content: str):
        """
        发送通知。

        :param title: 通知标题。
        :param content: 通知内容。如果require_content为True且内容为空，则将内容设置为默认值'.'。
        """
        # 确保内容非空的逻辑处理
        if self.require_content and (content is None or content == ''):
            content = '.'
        # 获取对应的通知器实例并发送通知
        notifier_instance = get_notifier(self.notifier_name)
        # if self.notifier_name in ['gotify']:
        #     notifier_instance.notify(**self.params, title=title, message=content)
        # else:
        notifier_instance.notify(**self.params, title=title, content=content)
