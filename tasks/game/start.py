from managers.logger_manager import logger
from managers.automation_manager import auto
from managers.translate_manager import _
from managers.config_manager import config
from managers.ocr_manager import ocr
from tasks.base.base import Base
from tasks.game.stop import Stop
import time
import sys
import os


class Start:
    @staticmethod
    def check_game_path(game_path):
        if not os.path.exists(game_path):
            logger.error(_("游戏路径不存在: {path}\n请修改配置文件 config.yaml，例如系统自带的记事本").format(path=game_path))
            os.system('pause')
            sys.exit(1)

    @staticmethod
    def check_and_click_enter():
        if auto.click_element("./assets/images/screen/click_enter.png", "image", 0.9):
            return True
        auto.click_element("./assets/images/base/confirm.png", "image", 0.9)
        return False

    @staticmethod
    def check_and_click_monthly_card():
        if auto.find_element("./assets/images/screen/main.png", "image", 0.9):
            return True
        auto.click_element("./assets/images/screen/monthly_card.png", "image", 0.9)
        return False

    @staticmethod
    def launch_process():
        logger.info(_("🖥️启动游戏中..."))
        Start.check_game_path(config.game_path)

        if os.system(f"powershell -Command \"start '{config.game_path}'\""):
            return False

        time.sleep(10)
        if not auto.retry_with_timeout(Base.check_and_switch, 30, 1, config.game_title_name):
            logger.error(_("无法切换游戏到前台"))
            return False
        # if not auto.click_element("./assets/images/screen/click_enter.png", "image", 0.9, max_retries=600):
        if not auto.retry_with_timeout(Start.check_and_click_enter, 600, 1):
            logger.error(_("无法找到点击进入按钮"))
            return False
        if not auto.retry_with_timeout(Start.check_and_click_monthly_card, 120, 1):
            logger.error(_("无法进入主界面"))
            return False

        return True

    @staticmethod
    def start_game():
        if not Base.check_and_switch(config.game_title_name):
            if not Start.launch_process():
                logger.error(_("游戏启动失败，退出游戏进程"))
                Stop.stop_game()
                return False
            else:
                logger.info(_("游戏启动成功"))
        else:
            logger.info(_("游戏已经启动了"))
        return True
