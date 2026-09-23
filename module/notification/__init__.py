import sys
from module.config import cfg
from module.logger import log
from module.notification.notification import Notification, NotificationLevel
# 导入所有通知器类型
from module.notification.serverchan3 import ServerChanNotifier
from module.notification.serverchanturbo import ServerChanTurboNotifier
if sys.platform == 'win32':
    from module.notification.winotify import WinotifyNotifier
from module.notification.telegram import TelegramNotifier
from module.notification.matrix import MatrixNotifier
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
from module.notification.bark import BarkNotifier
from module.notification.dingtalk import DingTalkNotifier
from module.notification.discord import DiscordNotifier
from module.notification.gotify import GotifyNotifier
from module.notification.pushdeer import PushDeerNotifier
from module.notification.pushplus import PushPlusNotifier
from module.notification.qmsg import QmsgNotifier


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
        "serverchanturbo": ServerChanTurboNotifier,
        "kook": KOOKNotifier,
        "webhook": WebhookNotifier,
        "meow": MeoWNotifier,
        "bark": BarkNotifier,
        "dingtalk": DingTalkNotifier,
        "discord": DiscordNotifier,
        "gotify": GotifyNotifier,
        "pushdeer": PushDeerNotifier,
        "pushplus": PushPlusNotifier,
        "qmsg": QmsgNotifier,
    }
    if sys.platform == 'win32':
        notifier_classes["winotify"] = WinotifyNotifier

    @staticmethod
    def create_notifier(notifier_name, params, logger):
        """
        根据提供的notifier_name，从映射字典中找到对应的类并实例化。
        未内置支持的通知方式返回None，并记录警告。
        """
        notifier_class = NotifierFactory.notifier_classes.get(notifier_name)
        if notifier_class is None:
            logger.warning(f"暂不支持的通知方式: {notifier_name}，已跳过")
            return None
        return notifier_class(params, logger)


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

    # 检查消息推送总开关
    if not cfg.get_value('notification_enable', True):
        return

    # 设置通知级别过滤器
    try:
        notify_level = cfg.get_value('notify_level', NotificationLevel.ALL)
        notif.set_level_filter(notify_level)
    except Exception:
        pass

    # 设置是否发送图片
    try:
        notify_send_images = cfg.get_value('notify_send_images', True)
        notif.set_image_enable(notify_send_images)
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
                try:
                    notifier = NotifierFactory.create_notifier(notifier_name, params, log)
                except Exception as e:
                    log.error(f"{notifier_name} 通知初始化失败: {e}")
                    continue
                if notifier is not None:
                    notif.set_notifier(notifier_name, notifier)
    except Exception:
        pass


# 首次初始化
init_notifiers()
