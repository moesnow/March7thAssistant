import sys
from module.config import cfg
from module.logger import log
from module.notification.matrix import MatrixNotifier
from module.notification.notification import Notification, NotificationLevel
# 导入所有通知器类型
from module.notification.onepush import OnepushNotifier
from module.notification.serverchan3 import ServerChanNotifier
if sys.platform == 'win32':
    from module.notification.winotify import WinotifyNotifier
from module.notification.telegram import TelegramNotifier
from module.notification.onebot import OnebotNotifier
from module.notification.smtp import SMTPNotifier
from module.notification.gocqhttp import GocqhttpNotifier
from module.notification.wechatworkapp import WeChatworkappNotifier
from module.notification.custom import CustomNotifier
from module.notification.lark import LarkNotifier
from module.notification.wechatworkbot import WeChatWorkBotNotifier
from module.notification.kook import KOOKNotifier
from module.notification.webhook import WebhookNotifier
from module.notification.meow import MeoWNotifier


class NotifierFactory:
    # 创建通知器类型到其类的映射字典
    notifier_classes = {
        "telegram": TelegramNotifier,
        "matrix": MatrixNotifier,
        "onebot": OnebotNotifier,
        "smtp": SMTPNotifier,
        "gocqhttp": GocqhttpNotifier,
        "wechatworkapp": WeChatworkappNotifier,
        "wechatworkbot": WeChatWorkBotNotifier,
        "custom": CustomNotifier,
        "lark": LarkNotifier,
        "serverchan3": ServerChanNotifier,
        "kook": KOOKNotifier,
        "webhook": WebhookNotifier,
        "meow": MeoWNotifier,
    }
    if sys.platform == 'win32':
        notifier_classes["winotify"] = WinotifyNotifier

    @staticmethod
    def create_notifier(notifier_name, params, logger):
        """
        根据提供的notifier_name，从映射字典中找到对应的类并实例化。
        对于特殊处理的通知器，如OnepushNotifier，根据需要传递额外的参数。
        """
        # 特殊处理的通知器类型
        if notifier_name in ["gotify", "pushplus", "pushdeer"]:
            return OnepushNotifier(notifier_name, params, logger, require_content=True)
        elif notifier_name in NotifierFactory.notifier_classes:
            return NotifierFactory.notifier_classes[notifier_name](params, logger)
        else:
            # 默认情况下，如果没有找到匹配的类，则创建OnepushNotifier实例
            return OnepushNotifier(notifier_name, params, logger)


notif = Notification(cfg.notify_template['Title'], log)


def init_notifiers():
    """(Re)initialize notifiers from current configuration.

    This updates the existing global `notif` instance in-place: clears previous notifiers,
    sets the level filter, and (re)creates notifier instances based on `cfg`.
    """
    # 清理已有的notifiers
    try:
        notif.notifiers.clear()
    except Exception:
        pass

    # 设置通知级别过滤器
    try:
        notify_level = cfg.get_value('notify_level', NotificationLevel.ALL)
        notif.set_level_filter(notify_level)
    except Exception:
        pass

    # 创建并注册Notifier实例
    try:
        for key, value in cfg.config.items():
            if key.startswith("notify_") and key.endswith("_enable") and value:
                notifier_name = key[len("notify_"):-len("_enable")]
                params = {param_key[len("notify_" + notifier_name + "_"):]: param_value
                          for param_key, param_value in cfg.config.items()
                          if param_key.startswith(f"notify_{notifier_name}_") and param_key != f"notify_{notifier_name}_enable" and param_value != ""}
                if sys.platform != 'win32' and notifier_name == 'winotify':
                    continue  # 跳过 Windows 专用的通知器
                notifier = NotifierFactory.create_notifier(notifier_name, params, log)
                notif.set_notifier(notifier_name, notifier)
    except Exception:
        pass


# 首次初始化
init_notifiers()
