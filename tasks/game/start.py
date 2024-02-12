from managers.logger_manager import logger
from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.translate_manager import _
from managers.config_manager import config
from managers.ocr_manager import ocr
from tasks.base.windowswitcher import WindowSwitcher
from .stop import Stop
from .resolution import Resolution
from .registry import Registry
import pyautogui
import winreg
import psutil
import json
import time
import sys
import os


class Start:
    @staticmethod
    def check_path(game_path):
        # 检测路径是否存在
        if not os.path.exists(game_path):
            logger.error(_("游戏路径不存在: {path}").format(path=game_path))
            logger.info(_("第一次使用请手动启动游戏进入主界面后重新运行，程序会自动保存游戏路径"))
            logger.info(_("注意：程序只支持PC端运行，不支持任何模拟器"))
            input(_("按回车键关闭窗口. . ."))
            sys.exit(1)

    @staticmethod
    def get_process_path(name):
        # 通过进程名获取运行路径
        for proc in psutil.process_iter(attrs=['pid', 'name']):
            if name in proc.info['name']:
                process = psutil.Process(proc.info['pid'])
                return process.exe()
        return None

    @staticmethod
    def check_and_click_enter():
        # 点击进入
        if auto.click_element("./assets/images/screen/click_enter.png", "image", 0.9):
            return True
        # 游戏热更新，需要确认重启
        auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9)
        # 网络异常等问题，需要重新启动
        auto.click_element("./assets/images/zh_CN/base/restart.png", "image", 0.9)
        # 适配国际服，需要点击“开始游戏”
        auto.click_element("./assets/images/screen/start_game.png", "image", 0.9)
        return False

    @staticmethod
    def launch_process():
        logger.info(_("🖥️启动游戏中..."))
        Start.check_path(config.game_path)

        # 指定注册表项路径
        registry_key_path = r"SOFTWARE\miHoYo\崩坏：星穹铁道"
        # 指定要获取的值的名称
        value_name = "GraphicsSettings_PCResolution_h431323223"
        # 读取注册表中指定路径的值
        value = Registry.read_registry_value(winreg.HKEY_CURRENT_USER, registry_key_path, value_name)

        if value:
            # 去除末尾的\x00字符并尝试解析JSON
            data_dict = json.loads(value.decode('utf-8').strip('\x00'))
            data_dict['width'] = 1920
            data_dict['height'] = 1080
            # 获取屏幕的宽度和高度
            screen_width, screen_height = pyautogui.size()
            if screen_width <= 1920 and screen_height <= 1080:
                data_dict['isFullScreen'] = True
            elif screen_width > 1920 and screen_height > 1080:
                data_dict['isFullScreen'] = False

            # 修改数据并添加\x00字符
            modified_data = (json.dumps(data_dict) + '\x00').encode('utf-8')

            # 写入注册表
            Registry.write_registry_value(winreg.HKEY_CURRENT_USER, registry_key_path, value_name, modified_data)

        logger.debug(_("运行命令: cmd /C start \"\" \"{path}\"").format(path=config.game_path))
        if os.system(f"cmd /C start \"\" \"{config.game_path}\""):
            return False
        logger.debug(_("游戏启动成功: {path}").format(path=config.game_path))

        time.sleep(10)
        if not auto.retry_with_timeout(lambda: WindowSwitcher.check_and_switch(config.game_title_name), 60, 1):
            if value:
                Registry.write_registry_value(winreg.HKEY_CURRENT_USER, registry_key_path, value_name, value)
            logger.error(_("无法切换游戏到前台"))
            return False

        if value:
            Registry.write_registry_value(winreg.HKEY_CURRENT_USER, registry_key_path, value_name, value)

        Resolution.check(config.game_title_name, 1920, 1080)

        if not auto.retry_with_timeout(lambda: Start.check_and_click_enter(), 600, 1):
            logger.error(_("无法找到点击进入按钮"))
            return False

        time.sleep(10)
        if not auto.retry_with_timeout(lambda: screen.get_current_screen(), 180, 1):
            logger.error(_("无法进入主界面"))
            return False

        return True

    @staticmethod
    def start_game():
        # 判断是否已经启动
        if not WindowSwitcher.check_and_switch(config.game_title_name):
            if not Start.launch_process():
                logger.error(_("游戏启动失败，退出游戏进程"))
                Stop.stop_game()
                return False
            else:
                logger.info(_("游戏启动成功"))
        else:
            logger.info(_("游戏已经启动了"))

            program_path = Start.get_process_path(config.game_process_name)
            if program_path is not None and program_path != config.game_path:
                config.set_value("game_path", program_path)
                logger.info(_("游戏路径更新成功：{path}").format(path=program_path))

            Resolution.check(config.game_title_name, 1920, 1080)
        return True
