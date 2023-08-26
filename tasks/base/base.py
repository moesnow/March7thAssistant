from managers.translate_manager import _
from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.notify_manager import notify
from managers.screen_manager import screen
from io import BytesIO
import time

from .windowswitcher import WindowSwitcher


class Base:
    # 兼容旧代码
    @staticmethod
    def check_and_switch(title):
        return WindowSwitcher.check_and_switch(title)

    @staticmethod
    def send_notification_with_screenshot(message):
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
        if auto.click_element(team_name, "text", max_retries=10):
            time.sleep(1)
            if auto.find_element("已启用", "text", max_retries=2):
                logger.info(_("已经是队伍{team}了").format(team=team_name))
                screen.change_to("main")
                return True
            elif auto.click_element("启用队伍", "text", max_retries=10):
                if auto.find_element("已启用", "text", max_retries=2):
                    logger.info(_("切换到队伍{team}成功").format(team=team_name))
                    screen.change_to("main")
                    return True
        return False
