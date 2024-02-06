from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.config_manager import config
from managers.translate_manager import _
import time


class Character:
    @staticmethod
    def borrow():
        if not config.borrow_enable:
            return True
        if not (("使用支援角色并获得战斗胜利1次" in config.daily_tasks and config.daily_tasks["使用支援角色并获得战斗胜利1次"]) or config.borrow_character_enable):
            return True
        if not auto.click_element("支援", "text", max_retries=10, crop=(1670 / 1920, 700 / 1080, 225 / 1920, 74 / 1080)):
            logger.error(_("找不到支援按钮"))
            return False
        # 等待界面加载
        time.sleep(0.5)
        if not auto.find_element("支援列表", "text", max_retries=10, crop=(234 / 1920, 78 / 1080, 133 / 1920, 57 / 1080)):
            logger.error(_("未进入支援列表"))
            return False

        try:
            # 尝试优先使用指定用户名的支援角色
            if config.borrow_character_from:
                auto.click_element("等级", "text", max_retries=10, crop=(
                    18.0 / 1920, 15.0 / 1080, 572.0 / 1920, 414.0 / 1080), include=True)
                time.sleep(0.5)
                for i in range(3):
                    if auto.click_element(config.borrow_character_from, "text", crop=(196 / 1920, 167 / 1080, 427 / 1920, 754 / 1080), include=True):
                        # 找到角色的对应处理
                        if not auto.click_element("入队", "text", max_retries=10, crop=(1518 / 1920, 960 / 1080, 334 / 1920, 61 / 1080)):
                            logger.error(_("找不到入队按钮"))
                            return False
                        # 等待界面加载
                        time.sleep(0.5)
                        result = auto.find_element(
                            ("解除支援", "取消"), "text", max_retries=10, include=True)
                        if result:
                            if auto.matched_text == "解除支援":
                                if "使用支援角色并获得战斗胜利1次" in config.daily_tasks:
                                    config.daily_tasks["使用支援角色并获得战斗胜利1次"] = False
                                config.save_config()
                                return True
                            elif auto.matched_text == "取消":
                                auto.click_element_with_pos(result)
                                auto.find_element("支援列表", "text", max_retries=10, crop=(
                                    234 / 1920, 78 / 1080, 133 / 1920, 57 / 1080))
                                continue
                        else:
                            return False
                    auto.mouse_scroll(27, -1)
                    # 等待界面完全停止
                    time.sleep(0.5)

                logger.info(_("找不到指定用户名的支援角色，尝试按照优先级选择"))
                # 重新打开支援页面，防止上一次的滚动位置影响
                auto.press_key("esc")
                time.sleep(0.5)
                if not auto.click_element("支援", "text", max_retries=10, crop=(1670 / 1920, 700 / 1080, 225 / 1920, 74 / 1080)):
                    logger.error(_("找不到支援按钮"))
                    return False
                # 等待界面加载
                time.sleep(0.5)
                if not auto.find_element("支援列表", "text", max_retries=10, crop=(234 / 1920, 78 / 1080, 133 / 1920, 57 / 1080)):
                    logger.error(_("未进入支援列表"))
                    return False

            for name in config.borrow_character:
                if auto.click_element("./assets/images/share/character/" + name + ".png", "image", 0.8, max_retries=1, scale_range=(0.9, 0.9), crop=(57 / 1920, 143 / 1080, 140 / 1920, 814 / 1080)):
                    if not auto.click_element("入队", "text", max_retries=10, crop=(1518 / 1920, 960 / 1080, 334 / 1920, 61 / 1080)):
                        logger.error(_("找不到入队按钮"))
                        return False
                    # 等待界面加载
                    time.sleep(0.5)
                    result = auto.find_element(("解除支援", "取消"), "text", max_retries=10, include=True)
                    if result:
                        if auto.matched_text == "解除支援":
                            config.daily_tasks["使用支援角色并获得战斗胜利1次"] = False
                            config.save_config()
                            return True
                        elif auto.matched_text == "取消":
                            auto.click_element_with_pos(result)
                            auto.find_element("支援列表", "text", max_retries=10, crop=(
                                234 / 1920, 78 / 1080, 133 / 1920, 57 / 1080))
                            continue
                    else:
                        return False
        except Exception as e:
            logger.warning(_("选择支援角色出错： {e}").format(e=e))

        auto.press_key("esc")
        if auto.find_element("解除支援", "text", max_retries=2, crop=(1670 / 1920, 700 / 1080, 225 / 1920, 74 / 1080)):
            return True
        else:
            return False
