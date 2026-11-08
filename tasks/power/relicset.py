from module.automation import auto
from module.screen import screen
from module.logger import log
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
        """
        执行分解四星及以下遗器操作。
        返回值：
          True  - 成功分解了遗器
          False - 未找到可分解的遗器（背包内无低星遗器）或流程出错
        """
        log.hr("准备分解四星及以下遗器", 2)

        # 切换到遗器分解界面
        if not Relicset.change_to_relicset():
            return False

        # 筛选并确认
        if not Relicset.prepare_break_down_relicset():
            return False

        result = Relicset.start_break_down_relicset()

        auto.press_key("esc")
        screen.wait_for_screen_change('bag_relicset')

        return result

    @staticmethod
    def change_to_relicset():
        screen.change_to("bag_relicset")
        auto.click_element(Relicset.ENTER_BREAK_IMAGE, "image", 0.9, max_retries=10)
        if auto.find_element(Relicset.SCREEN_IMAGE, "image", 0.9, max_retries=10):
            return True
        log.error("切换到遗器分解界面失败")
        return False

    @staticmethod
    def prepare_break_down_relicset():
        if auto.click_element(Relicset.SELECT_IMAGE, "image", 0.9, max_retries=10):
            time.sleep(1)
            if auto.find_element(Relicset.LEVEL_FOUR_IMAGE, "image", 0.9, max_retries=10):
                # 多次判断避免误操作
                if auto.click_element("4星及以下", "text", max_retries=10):
                    if auto.click_element(Relicset.CONFIRM_IMAGE, "image", 0.9, max_retries=10):
                        if auto.find_element(Relicset.SCREEN_IMAGE, "image", 0.9, max_retries=10):
                            log.info("筛选遗器成功")
                            return True
        log.error("筛选遗器失败")
        return False

    @staticmethod
    def start_break_down_relicset(use_ocr=False):
        if use_ocr:
            # The weekly cleanup uses OCR for text controls; legacy callers keep
            # their original image matching behavior.
            break_button = auto.click_element("分解", "text", max_retries=5,
                                              crop=(1430 / 1920, 945 / 1080, 445 / 1920, 80 / 1080), include=True)
        else:
            break_button = auto.click_element(Relicset.BREAK_IMAGE, "image", 0.9, max_retries=5)
        if not break_button:
            log.info("不存在可分解的遗器")
            return False

        time.sleep(1)
        if use_ocr:
            confirmed = auto.click_element("确认", "text", max_retries=10,
                                            crop=(970 / 1920, 695 / 1080, 450 / 1920, 190 / 1080), include=True)
        else:
            confirmed = auto.click_element(Relicset.CONFIRM_IMAGE, "image", 0.9, max_retries=10)
        if confirmed:
            if use_ocr:
                closed = auto.click_element("点击空白处关闭", "text", max_retries=10, include=True)
            else:
                closed = auto.click_element(Relicset.CLICK_CLOSE_IMAGE, "image", 0.8, max_retries=10)
            if closed:
                if (auto.find_element("遗器分解", "text", max_retries=10,
                                      crop=(75 / 1920, 35 / 1080, 225 / 1920, 70 / 1080), include=True)
                        if use_ocr else auto.find_element(Relicset.SCREEN_IMAGE, "image", 0.9, max_retries=10)):
                    log.info("分解遗器成功")
                    return True
        log.error("分解遗器失败")
        return False
