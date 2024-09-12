from module.automation import auto
from module.logger import log
from module.config import cfg
import time
from module.automation.screenshot import Screenshot


class Character:
    @staticmethod
    def borrow(type="standard"):
        # 检测是否可以执行借助支援角色
        if Character.is_borrow_disabled():
            return True

        # 点击支援按钮并进入支援列表
        if not Character.click_support_button(type):
            return False

        # 开始查找支援角色
        return Character.find_and_select_support(type)

    @staticmethod
    def is_borrow_disabled():
        """检测是否需要使用支援角色"""
        if not cfg.borrow_enable:
            return True
        if not (("使用支援角色并获得战斗胜利1次" in cfg.daily_tasks and cfg.daily_tasks["使用支援角色并获得战斗胜利1次"])
                or cfg.borrow_character_enable):
            return True
        return False

    @staticmethod
    def click_support_button(type):
        """点击支援按钮，进入支援列表"""
        if type == "standard":
            if not auto.click_element("支援", "text", max_retries=10, crop=(1670 / 1920, 700 / 1080, 225 / 1920, 74 / 1080)):
                log.error("找不到支援按钮")
                return False
        elif type == "ornament":
            if not auto.click_element("支援", "text", max_retries=10, crop=(994.0 / 1920, 765.0 / 1080, 160.0 / 1920, 116.0 / 1080)):
                log.error("找不到支援按钮")
                return False
        time.sleep(1)
        return auto.find_element("支援列表", "text", max_retries=10, crop=(157.0 / 1920, 22.0 / 1080, 276.0 / 1920, 81.0 / 1080))

    @staticmethod
    def find_and_select_support(type):
        """查找并选择支援角色"""
        window = Screenshot.get_window(cfg.game_title_name)
        _, _, width, height = Screenshot.get_window_region(window)

        for i in range(cfg.borrow_scroll_times):
            for key, value in cfg.borrow_friends:
                if key == "None":
                    continue
                if Character.find_character_and_click(key, value, width, height):
                    if Character.confirm_selection(type):
                        return True

            # 若未找到角色，尝试滚动页面
            if i < cfg.borrow_scroll_times - 1:
                Character.scroll_support_list()

        # 未找到支援角色，退出
        Character.exit_support_list(type)
        return False

    @staticmethod
    def find_character_and_click(key, value, width, height):
        """查找支援角色并点击"""
        crop = (40.0 / 1920, 152.0 / 1080, 531.0 / 1920, 809.0 / 1080)
        matchs = auto.find_element("./assets/images/share/character/" + key + ".png", "image_with_multiple_targets", 0.8,
                                   max_retries=1, scale_range=0.9, crop=crop, relative=True)
        for match in matchs:
            top_right = (match[1][0] + width * crop[0], match[0][1] + height * crop[1])
            crop_new = (top_right[0] / width, top_right[1] / height, 402.0 / 1920, 43.0 / 1080)
            if value == "" or auto.click_element(value, "text", crop=crop_new, include=True):
                time.sleep(1)
                return True
        return False

    @staticmethod
    def confirm_selection(type):
        """确认选择的支援角色并入队"""
        if type == "standard":
            if not auto.click_element("入队", "text", max_retries=10, crop=(1518 / 1920, 960 / 1080, 334 / 1920, 61 / 1080)):
                log.error("找不到入队按钮")
                return False
            time.sleep(1)
            result = auto.find_element(("解除支援", "取消"), "text", max_retries=10, include=True)
            return Character.process_support_selection_result(result)
        elif type == "ornament":
            Character.complete_ornament_borrow()
            return True

    @staticmethod
    def process_support_selection_result(result):
        """处理支援选择的结果"""
        if result:
            if auto.matched_text == "解除支援":
                Character.complete_daily_task()
                return True
            elif auto.matched_text == "取消":
                auto.click_element_with_pos(result)
                time.sleep(1)
                auto.find_element("支援列表", "text", max_retries=10, crop=(157.0 / 1920, 22.0 / 1080, 276.0 / 1920, 81.0 / 1080))
                return False
        return False

    @staticmethod
    def complete_ornament_borrow():
        """完成饰品提取的后续操作"""
        Character.complete_daily_task()
        auto.press_key("esc")
        time.sleep(1)
        auto.find_element("解除支援", "text", max_retries=10, crop=(994.0 / 1920, 765.0 / 1080, 160.0 / 1920, 116.0 / 1080))

    @staticmethod
    def complete_daily_task():
        """标记日常任务已完成"""
        if "使用支援角色并获得战斗胜利1次" in cfg.daily_tasks:
            cfg.daily_tasks["使用支援角色并获得战斗胜利1次"] = False
            cfg.save_config()

    @staticmethod
    def scroll_support_list():
        """滚动支援列表"""
        auto.click_element("等级", "text", max_retries=1, crop=(40.0 / 1920, 152.0 / 1080, 531.0 / 1920, 809.0 / 1080), include=True, action="move")
        auto.mouse_scroll(23, -1, False)
        time.sleep(0.5)

    @staticmethod
    def exit_support_list(type):
        """退出支援列表"""
        auto.press_key("esc")
        time.sleep(1)
        if type == "standard":
            auto.find_element("支援", "text", max_retries=10, crop=(1670 / 1920, 700 / 1080, 225 / 1920, 74 / 1080))
        elif type == "ornament":
            auto.find_element("支援", "text", max_retries=10, crop=(994.0 / 1920, 765.0 / 1080, 160.0 / 1920, 116.0 / 1080))
