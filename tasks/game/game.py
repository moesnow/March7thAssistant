from managers.logger_manager import logger
from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.translate_manager import _
from managers.config_manager import config
from managers.notify_manager import notify
from tasks.game.start import Start
from tasks.game.stop import Stop
import sys


class Game:
    @staticmethod
    def start():
        logger.hr(_("开始运行"), 0)
        logger.info(_("开始启动游戏"))
        if not auto.retry_with_timeout(lambda: Start.start_game(), 1200, 1):
            notify.notify(_("⚠️启动游戏超时，退出程序⚠️"))
            logger.error(_("⚠️启动游戏超时，退出程序⚠️"))
            input(_("按回车键关闭窗口. . ."))
            sys.exit(1)
        # 判断手机壁纸
        if not screen.check_screen('menu'):
            screen.change_to('menu')
        if not auto.find_element("./assets/images/menu/journey.png", "image", 0.9):
            logger.info(_("检测到未使用无名路途壁纸"))
            screen.change_to('wallpaper')
            auto.click_element("./assets/images/menu/wallpaper/journey.png", "image", 0.9)
            auto.click_element("更换", "text",max_retries=10)
            auto.press_key("esc")
            logger.info(_("更换到无名路途壁纸成功"))
        logger.hr(_("完成"), 2)

    @staticmethod
    def stop(detect_loop=False):
        logger.hr(_("停止运行"), 0)
        Stop.play_audio()
        if detect_loop and config.after_finish == "Loop":
            Stop.after_finish_is_loop()
        else:
            Stop.after_finish_not_loop()
