from managers.automation import auto
from managers.screen import screen
from managers.logger import logger
import time


class Relicset:
    ENTER_BREAK_IMAGE = "./assets/images/zh_CN/relicset/enter_break.png"
    SCREEN_IMAGE = "./assets/images/zh_CN/relicset/screen.png"
    SELECT_IMAGE = "./assets/images/zh_CN/relicset/select.png"
    LEVEL_FOUR_IMAGE = "./assets/images/zh_CN/relicset/level_four.png"
    CONFIRM_IMAGE = "./assets/images/zh_CN/base/confirm.png"
    BREAK_IMAGE = "./assets/images/zh_CN/relicset/break.png"
    CLICK_CLOSE_IMAGE = "./assets/images/zh_CN/base/click_close.png"

    @staticmethod
    def run():

        logger.hr("准备分解四星及以下遗器", 2)

        # 切换到遗器分解界面
        if not Relicset.change_to_relicset():
            return

        # 筛选并确认
        if not Relicset.prepare_break_down_relicset():
            return

        Relicset.start_break_down_relicset()

    @staticmethod
    def change_to_relicset():
        screen.change_to("bag_relicset")
        auto.click_element(Relicset.ENTER_BREAK_IMAGE, "image", 0.9, max_retries=10)
        if auto.find_element(Relicset.SCREEN_IMAGE, "image", 0.9, max_retries=10):
            return True
        logger.error("切换到遗器分解界面失败")
        return False

    @staticmethod
    def prepare_break_down_relicset():
        if auto.click_element(Relicset.SELECT_IMAGE, "image", 0.9, max_retries=10):
            time.sleep(1)
            if auto.click_element(Relicset.LEVEL_FOUR_IMAGE, "image", 0.9, max_retries=10):
                if auto.click_element(Relicset.CONFIRM_IMAGE, "image", 0.9, max_retries=10):
                    if auto.find_element(Relicset.SCREEN_IMAGE, "image", 0.9, max_retries=10):
                        logger.info("筛选遗器成功")
                        return True
        logger.error("筛选遗器失败")
        return False

    @staticmethod
    def start_break_down_relicset():
        if not auto.click_element(Relicset.BREAK_IMAGE, "image", 0.9, max_retries=5):
            logger.info("不存在可分解的遗器")
            return False

        time.sleep(1)
        if auto.click_element(Relicset.CONFIRM_IMAGE, "image", 0.9, max_retries=10):
            if auto.click_element(Relicset.CLICK_CLOSE_IMAGE, "image", 0.8, max_retries=10):
                if auto.find_element(Relicset.SCREEN_IMAGE, "image", 0.9, max_retries=10):
                    auto.press_key("esc")
                    logger.info("分解遗器成功")
                    return True
        logger.error("分解遗器失败")
        return False
