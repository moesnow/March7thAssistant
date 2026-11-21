from module.config import cfg
from module.screen import screen
from module.automation import auto
import time


class HimekoTry:
    @staticmethod
    def technique():
        if cfg.daily_himeko_try_enable:
            screen.change_to("himeko_prepare")
            technique_key = cfg.get_game_hotkey("hotkey_technique", "e")
            auto.press_key(technique_key)
            time.sleep(2)
            auto.press_key(technique_key)
            time.sleep(2)
            screen.change_to("himeko_try")
            return True

    @staticmethod
    def item():
        if cfg.daily_himeko_try_enable:
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
