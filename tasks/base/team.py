from managers.translate_manager import _
from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.screen_manager import screen
import time


class Team:
    @staticmethod
    def change_to(team):
        team_name = f"0{str(team)}"
        logger.info(_("准备切换到队伍{team}").format(team=team_name))

        screen.change_to("configure_team")

        if not auto.click_element(team_name, "text", max_retries=10, crop=(311.0 / 1920, 15.0 / 1080, 1376.0 / 1920, 100.0 / 1080)):
            return False

        # 等待界面切换
        time.sleep(1)

        result = auto.find_element(("已启用", "启用队伍"), "text", max_retries=10, crop=(
            1507.0 / 1920, 955.0 / 1080, 336.0 / 1920, 58.0 / 1080))
        if result:
            if auto.matched_text == "已启用":
                logger.info(_("当前已经是队伍{team}了").format(team=team_name))
                return True

            elif auto.matched_text == "启用队伍":
                auto.click_element_with_pos(result)
                if auto.find_element("已启用", "text", max_retries=10, crop=(1507.0 / 1920, 955.0 / 1080, 336.0 / 1920, 58.0 / 1080)):
                    logger.info(_("切换到队伍{team}成功").format(team=team_name))
                    return True

        return False
