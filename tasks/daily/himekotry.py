from managers.config_manager import config
from managers.screen_manager import screen
from managers.automation_manager import auto
import time


class HimekoTry:
    @staticmethod
    def technique():
        if config.daily_himeko_try_enable:
            screen.change_to("himeko_prepare")
            auto.press_key(config.get_value("hotkey_technique"))
            time.sleep(2)
            auto.press_key(config.get_value("hotkey_technique"))
            time.sleep(2)
            screen.change_to("himeko_try")
            return True

    @staticmethod
    def item():
        if config.daily_himeko_try_enable:
            screen.change_to("himeko_prepare")
            auto.press_key("w", 6)
            auto.press_mouse()
            time.sleep(1)
            auto.press_key("d", 2)
            auto.press_key("s", 2)
            auto.press_mouse()
            time.sleep(1)
            auto.press_key("w", 0.5)
            auto.press_key("d", 2)
            auto.press_mouse()
            time.sleep(1)
            screen.change_to("himeko_try")
            return True
