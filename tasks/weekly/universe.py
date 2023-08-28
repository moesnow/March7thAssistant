from managers.screen_manager import screen
from managers.config_manager import config
from managers.logger_manager import logger
from managers.automation_manager import auto
from managers.translate_manager import _
import subprocess
from threading import Thread
from tasks.base.base import Base


class Universe:
    @staticmethod
    def run_subprocess_with_timeout(command, timeout):
        process = None
        try:
            process = subprocess.Popen(command, shell=True)
            process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            if process is not None:
                process.terminate()
                process.wait()

    @staticmethod
    def start():
        logger.hr(_("准备模拟宇宙"), 2)

        screen.change_to('universe_main')
        screen.change_to('main')

        subprocess_thread = Thread(target=Universe.run_subprocess_with_timeout, args=(config.universe_command, config.universe_timeout * 3600))
        subprocess_thread.start()
        subprocess_thread.join()

        screen.change_to('universe_main')

        if auto.click_element("./assets/images/universe/universe_reward.png", "image", 0.9):
            if auto.click_element("./assets/images/universe/one_key_receive.png", "image", 0.9, max_retries=10):
                Base.send_notification_with_screenshot(_("🎉模拟宇宙奖励已领取🎉"))
                auto.click_element("./assets/images/base/click_close.png", "image", 0.9, max_retries=10)

        logger.info(_("模拟宇宙完成"))
        config.save_timestamp("universe_timestamp")
