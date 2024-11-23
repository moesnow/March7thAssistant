from module.screen import screen
from module.automation import auto
from module.config import cfg
from module.logger import log
from utils.color import red, green, yellow
import tasks.reward as reward
import pyperclip
import time


class Redemption:
    @staticmethod
    def start():
        log.hr("准备使用兑换码", 0)

        if cfg.redemption_code == []:
            log.error("兑换码列表为空, 跳过任务")
            return False

        for code in cfg.redemption_code:
            log.info(f"开始使用兑换码: {green(code)} ({cfg.redemption_code.index(code) + 1}/{len(cfg.redemption_code)})")
            screen.change_to('redemption')
            pyperclip.copy(code)
            if auto.click_element("./assets/images/share/redemption/paste.png", "image", 0.9):
                time.sleep(0.5)
                if auto.find_element("./assets/images/share/redemption/clear.png", "image", 0.9):
                    time.sleep(0.5)
                    auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9)
                    time.sleep(1)
                    if auto.find_element("兑换成功", "text"):
                        log.info(f"兑换码使用成功: {green(code)} ({cfg.redemption_code.index(code) + 1}/{len(cfg.redemption_code)})")
                        auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9)
                        screen.wait_for_screen_change('menu')
                        time.sleep(3)
                        continue
            log.error(f"兑换码使用失败: {red(code)} ({cfg.redemption_code.index(code) + 1}/{len(cfg.redemption_code)})")
            return False

        reward.start_specific("mail")
        return True
