from module.notify.notify import Notify
from managers.config_manager import config

notify = Notify()

for key, value in config.config.items():
    if key.startswith("notify_") and key.endswith("_enable") and value:
        notifier_name = key[len("notify_"):-len("_enable")]
        params = {}
        for param_key, param_value in config.config.items():
            if param_key.startswith("notify_" + notifier_name + "_") and param_key != f"notify_{notifier_name}_enable" and param_value != "":
                params[param_key[len("notify_" + notifier_name + "_"):]] = param_value

        notify.set_notifier(notifier_name, True, params)
