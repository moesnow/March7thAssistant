from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.translate_manager import _
from managers.config_manager import config
import time


class Synthesis:
    @staticmethod
    def start():
        # if not config.synthesis_enable:
        #     logger.info(_("合成/使用材料/消耗品未开启"))
        #     return False
        Synthesis.consumables()
        Synthesis.material()
        Synthesis.use_consumables()

    @staticmethod
    def consumables():
        try:
            flag = False
            logger.hr(_("准备合成消耗品"), 2)
            screen.change_to('consumables')
            if auto.click_element("./assets/images/synthesis/filter.png", "image", 0.9, max_retries=10):
                # 等待界面弹出
                time.sleep(1)
                result = auto.find_element("防御类消耗品", "text", max_retries=10, crop=(480 / 1920, 400 / 1080, 963 / 1920, 136 / 1080))
                if result:
                    auto.click_element_with_pos(result)
                    if auto.click_element("./assets/images/base/confirm.png", "image", 0.9, max_retries=10):
                        for i in range(10):
                            auto.click_element("./assets/images/synthesis/defensive_medicine.png", "image", 0.9, max_retries=10)
                            if auto.find_element("./assets/images/synthesis/defensive_medicine_selected.png", "image", 0.9, max_retries=10):
                                if auto.click_element("./assets/images/synthesis/synthesis_button.png", "image", 0.9, max_retries=10):
                                    if auto.click_element("./assets/images/base/confirm.png", "image", 0.9, max_retries=10):
                                        if auto.click_element("./assets/images/base/click_close.png", "image", 0.9, max_retries=10):
                                            flag = True
                                break
            logger.info(_("合成消耗品完成"))
            return flag
        except Exception as e:
            logger.error(_("合成消耗品失败: {error}").format(error=e))
            return False

    def material():
        try:
            flag = False
            logger.hr(_("准备合成材料"), 2)
            screen.change_to('material')
            if auto.click_element("./assets/images/synthesis/filter.png", "image", 0.9, max_retries=10):
                # 等待界面弹出
                time.sleep(1)
                result = auto.find_element("通用培养材料", "text", max_retries=10, crop=(480 / 1920, 400 / 1080, 963 / 1920, 136 / 1080))
                if result:
                    auto.click_element_with_pos(result)
                    if auto.click_element("./assets/images/base/confirm.png", "image", 0.9, max_retries=10):
                        for i in range(10):
                            auto.click_element("./assets/images/synthesis/nuclear.png", "image", 0.9, max_retries=10)
                            if auto.find_element("./assets/images/synthesis/nuclear_selected.png", "image", 0.9, max_retries=10):
                                if auto.click_element("./assets/images/synthesis/synthesis_button.png", "image", 0.9, max_retries=10):
                                    if auto.click_element("./assets/images/base/confirm.png", "image", 0.9, max_retries=10):
                                        if auto.click_element("./assets/images/base/click_close.png", "image", 0.9, max_retries=10):
                                            flag = True
                                break
            logger.info(_("合成材料完成"))
            return flag
        except Exception as e:
            logger.error(_("合成材料失败: {error}").format(error=e))
            return False

    def use_consumables(recursion=True):
        try:
            flag = False
            logger.hr(_("准备使用消耗品"), 2)
            screen.change_to('bag_consumables')
            result = auto.click_element("./assets/images/synthesis/defensive_medicine.png", "image", 0.8, max_retries=10)
            if result:
                if auto.find_element("./assets/images/bag/defensive_medicine_selected.png", "image", 0.8, max_retries=10):
                    # if auto.click_element("使用", "text", max_retries=10):
                    if auto.click_element("./assets/images/base/use.png", "image", 0.9, max_retries=10):
                        if auto.click_element("./assets/images/base/confirm.png", "image", 0.9, max_retries=10):
                            auto.click_element("./assets/images/base/confirm.png", "image", 0.9, max_retries=2)
                            if auto.find_element("./assets/images/screen/bag/bag_consumables.png", "image", 0.9, max_retries=10):
                                flag = True
            elif recursion:
                logger.info(_("没有可用的消耗品，尝试合成"))
                Synthesis.consumables()
                flag = Synthesis.use_consumables(False)
            logger.info(_("使用消耗品完成"))
            return flag
        except Exception as e:
            logger.error(_("使用消耗品失败: {error}").format(error=e))
            return False
