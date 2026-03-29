from module.automation import auto
from module.logger import log
from module.screen import screen
import time


class Team:
    @staticmethod
    def change_to(team):
        team_name = str(team).zfill(2)
        log.info(f"准备切换到队伍{team_name}")

        screen.change_to("configure_team")

        crop = (311.0 / 1920, 15.0 / 1080, 1376.0 / 1920, 100.0 / 1080)
        if not auto.click_element(team_name, "text", max_retries=10, crop=crop, include=True):
            if not auto.click_element("07", "text", max_retries=10, crop=crop, include=True):
                return False
            direction = -1 if int(team) > 7 else 1
            auto.mouse_scroll(20, direction)
            if not auto.click_element(team_name, "text", max_retries=10, crop=crop, include=True):
                return False

        # 等待界面切换
        time.sleep(4)

        result = auto.find_element(("已启用", "启用队伍"), "text", max_retries=10, crop=(1507.0 / 1920, 955.0 / 1080, 336.0 / 1920, 58.0 / 1080))
        if result:
            if auto.matched_text == "已启用":
                log.info(f"当前已经是队伍{team_name}了")
                return True

            elif auto.matched_text == "启用队伍":
                auto.click_element_with_pos(result)
                if auto.find_element("已启用", "text", max_retries=10, crop=(1507.0 / 1920, 955.0 / 1080, 336.0 / 1920, 58.0 / 1080)):
                    log.info(f"切换到队伍{team_name}成功")
                    return True

        return False
