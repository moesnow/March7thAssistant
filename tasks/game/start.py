from managers.logger_manager import logger
from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.translate_manager import _
from managers.config_manager import config
from managers.ocr_manager import ocr
from tasks.base.base import Base
from tasks.game.stop import Stop
from tasks.base.resolution import Resolution
import psutil
import time
import sys
import os


class Start:
    @staticmethod
    def check_game_path(game_path):
        if not os.path.exists(game_path):
            logger.error(_("游戏路径不存在: {path}").format(path=game_path))
            logger.info(_("首次使用请启动游戏进入主界面后重试，程序会自动检测并保存游戏路径"))
            input(_("按任意键关闭窗口. . ."))
            sys.exit(1)

    @staticmethod
    def check_and_click_enter():
        if auto.click_element("./assets/images/screen/click_enter.png", "image", 0.9):
            return True
        auto.click_element("./assets/images/base/confirm.png", "image", 0.9)
        return False

    @staticmethod
    def check_and_click_monthly_card():
        # if auto.find_element("./assets/images/screen/main.png", "image", 0.9):
        if screen.get_current_screen():
            return True
        auto.click_element("./assets/images/screen/monthly_card.png", "image", 0.9)
        return False

    @staticmethod
    def launch_process():
        logger.info(_("🖥️启动游戏中..."))
        Start.check_game_path(config.game_path)

        logger.debug(f"运行命令: cmd /C start \"\" \"{config.game_path}\"")
        if os.system(f"cmd /C start \"\" \"{config.game_path}\""):
            return False
        logger.debug(_("游戏启动成功: {path}").format(path=config.game_path))

        time.sleep(10)
        if not auto.retry_with_timeout(Base.check_and_switch, 30, 1, config.game_title_name):
            logger.error(_("无法切换游戏到前台"))
            return False

        Resolution.check(config.game_title_name)
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
            Start.update_game_path(config.game_process_name)
            Resolution.check(config.game_title_name)
        return True

    @staticmethod
    def update_game_path(name):
        for proc in psutil.process_iter(attrs=['pid', 'name']):
            if name in proc.info['name']:
                process = psutil.Process(proc.info['pid'])
                program_path = process.exe()
                if config.game_path != program_path:
                    config.set_value("game_path", program_path)
                    logger.debug(_("游戏路径更新成功：{path}").format(path=program_path))
                return True
        return False
