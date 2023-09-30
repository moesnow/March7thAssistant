from managers.translate_manager import _
from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.notify_manager import notify
from managers.screen_manager import screen
from io import BytesIO
import time

from .windowswitcher import WindowSwitcher


class Base:
    @staticmethod
    def send_notification_with_screenshot(message):
        # 日志显示的同时推送消息
        logger.info(message)
        image_io = BytesIO()
        auto.take_screenshot()
        auto.screenshot.save(image_io, format='JPEG')
        notify.notify(message, "", image_io)

    @staticmethod
    def change_team(team):
        team_name = f"0{str(team)}"
        logger.info(_("准备切换到队伍{team}").format(team=team_name))
        screen.change_to("configure_team")
        if auto.click_element(team_name, "text", max_retries=10, crop=(311.0 / 1920, 15.0 / 1080, 1376.0 / 1920, 100.0 / 1080)):
            # 等待界面切换
            time.sleep(1)
            result = auto.find_element(("已启用", "启用队伍"), "text", max_retries=10, crop=(1507.0 / 1920, 955.0 / 1080, 336.0 / 1920, 58.0 / 1080))
            if result:
                if auto.matched_text == "已启用":
                    logger.info(_("已经是队伍{team}了").format(team=team_name))
                    screen.change_to("main")
                    return True
                elif auto.matched_text == "启用队伍":
                    auto.click_element_with_pos(result)
                    if auto.find_element("已启用", "text", max_retries=10, crop=(1507.0 / 1920, 955.0 / 1080, 336.0 / 1920, 58.0 / 1080)):
                        logger.info(_("切换到队伍{team}成功").format(team=team_name))
                        return True
        return False
