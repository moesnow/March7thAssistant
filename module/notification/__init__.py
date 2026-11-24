"""Load configured delivery services only when a caller requests them."""

__all__ = ["Notification", "NotificationLevel", "NotifierFactory", "init_notifiers", "notif"]


def __getattr__(name):
    if name in __all__ or name.endswith("Notifier"):
        # 写成 import 语句，PyInstaller 才会把通知模块打进发布包。
        from . import manager
        return getattr(manager, name)
    raise AttributeError(name)
