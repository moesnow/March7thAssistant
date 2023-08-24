import pyautogui
from managers.translate_manager import _
from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.translate_manager import _
from managers.notify_manager import notify
from managers.screen_manager import screen
import pygetwindow as gw
from io import BytesIO
import time
import win32gui


class Base:
    @staticmethod
    def send_notification_with_screenshot(message):
        logger.info(message)
        image_io = BytesIO()
        auto.take_screenshot()
        auto.screenshot.save(image_io, format='JPEG')
        notify.notify(message, "", image_io)

    @staticmethod
    def check_and_switch(title):
        def switch_window(title, max_retries):
            for i in range(max_retries):
                window = gw.getWindowsWithTitle(title)
                if not window:
                    continue
                for w in window:
                    if w.title == title:
                        try:
                            w.restore()
                            w.activate()
                        except Exception as e:
                            logger.error(e)
                        time.sleep(2)
                        if w.isActive:
                            try:
                                hwnd = win32gui.FindWindow("UnityWndClass", title)
                                win32gui.GetWindowRect(hwnd)
                            except Exception as e:
                                logger.error(e)
                                logger.debug(_("切换窗口失败，尝试ALT+TAB"))
                                pyautogui.hotkey('alt', 'tab')
                                time.sleep(2)
                                continue
                        else:
                            logger.debug(_("切换窗口失败，尝试ALT+TAB"))
                            pyautogui.hotkey('alt', 'tab')
                            time.sleep(2)
                            continue

                        return w.isActive
            return False
        return switch_window(title, max_retries=4)

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
