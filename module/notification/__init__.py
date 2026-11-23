"""Load configured delivery services only when a caller requests them."""
from importlib import import_module

__all__ = ["Notification", "NotificationLevel", "NotifierFactory", "init_notifiers", "notif"]


def __getattr__(name):
    if name in __all__ or name.endswith("Notifier"):
        return getattr(import_module(".manager", __name__), name)
    raise AttributeError(name)
