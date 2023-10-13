from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.translate_manager import _
import time


class Synthesis:
    @staticmethod
    def consumables():
        try:
            logger.hr(_("准备合成消耗品"), 2)
            screen.change_to('consumables')
            # 筛选规则
            if auto.click_element("./assets/images/synthesis/filter.png", "image", 0.9, max_retries=10):
                # 等待筛选界面弹出
                time.sleep(1)
                if auto.click_element("防御类消耗品", "text", max_retries=10, crop=(480 / 1920, 400 / 1080, 963 / 1920, 136 / 1080)):
                    if auto.click_element("./assets/images/base/confirm.png", "image", 0.9, max_retries=10):
                        # 多次重试避免选中没反应
                        for i in range(10):
                            auto.click_element("./assets/images/synthesis/defensive_medicine.png", "image", 0.9, max_retries=10)
                            if auto.find_element("./assets/images/synthesis/defensive_medicine_selected.png", "image", 0.9, max_retries=10):
                                if auto.click_element("./assets/images/synthesis/synthesis_button.png", "image", 0.9, max_retries=10):
                                    if auto.click_element("./assets/images/base/confirm.png", "image", 0.9, max_retries=10):
                                        if auto.click_element("./assets/images/base/click_close.png", "image", 0.9, max_retries=10):
                                            logger.info(_("合成消耗品完成"))
                                            return True
                                break
            logger.error(_("合成消耗品失败"))
        except Exception as e:
            logger.error(_("合成消耗品失败: {error}").format(error=e))
        return False

    def material():
        try:
            logger.hr(_("准备合成材料"), 2)
            screen.change_to('material')
            # 筛选规则
            if auto.click_element("./assets/images/synthesis/filter.png", "image", 0.9, max_retries=10):
                # 等待筛选界面弹出
                time.sleep(1)
                if auto.click_element("通用培养材料", "text", max_retries=10, crop=(480 / 1920, 400 / 1080, 963 / 1920, 136 / 1080)):
                    if auto.click_element("./assets/images/base/confirm.png", "image", 0.9, max_retries=10):
                        # 多次重试避免选中没反应
                        for i in range(10):
                            auto.click_element("./assets/images/synthesis/nuclear.png", "image", 0.9, max_retries=10)
                            if auto.find_element("./assets/images/synthesis/nuclear_selected.png", "image", 0.9, max_retries=10):
                                if auto.click_element("./assets/images/synthesis/synthesis_button.png", "image", 0.9, max_retries=10):
                                    if auto.click_element("./assets/images/base/confirm.png", "image", 0.9, max_retries=10):
                                        if auto.click_element("./assets/images/base/click_close.png", "image", 0.9, max_retries=10):
                                            logger.info(_("合成材料完成"))
                                            return True
                                break
            logger.error(_("合成材料失败"))
        except Exception as e:
            logger.error(_("合成材料失败: {error}").format(error=e))
        return False

    def use_consumables(recursion=True):
        try:
            logger.hr(_("准备使用消耗品"), 2)
            screen.change_to('bag_consumables')
            # 筛选规则
            if auto.click_element("./assets/images/synthesis/filter.png", "image", 0.9, max_retries=10):
                # 等待筛选界面弹出
                time.sleep(1)
                if auto.click_element("防御类消耗品", "text", max_retries=10, crop=(480 / 1920, 400 / 1080, 963 / 1920, 136 / 1080)):
                    if auto.click_element("./assets/images/base/confirm.png", "image", 0.9, max_retries=10):
                        # 多次重试避免选中没反应
                        for i in range(10):
                            if auto.click_element("./assets/images/synthesis/defensive_medicine.png", "image", 0.8, max_retries=10):
                                if auto.find_element("./assets/images/bag/defensive_medicine_selected.png", "image", 0.8, max_retries=10):
                                    if auto.click_element("./assets/images/base/use.png", "image", 0.9, max_retries=10):
                                        if auto.click_element("./assets/images/base/confirm.png", "image", 0.9, max_retries=10):
                                            auto.click_element("./assets/images/base/confirm.png", "image", 0.9, max_retries=2)
                                            if auto.find_element("./assets/images/screen/bag/bag_consumables.png", "image", 0.9, max_retries=10):
                                                logger.info(_("使用消耗品完成"))
                                                return True
                                break
                            elif recursion:
                                logger.info(_("没有可用的消耗品，尝试合成"))
                                if Synthesis.consumables():
                                    return Synthesis.use_consumables(False)
                                else:
                                    break
                            else:
                                break
            logger.error(_("使用消耗品失败"))
        except Exception as e:
            logger.error(_("使用消耗品失败: {error}").format(error=e))
        return False
