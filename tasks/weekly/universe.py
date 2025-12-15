from module.screen import screen
from module.config import cfg
from module.logger import log
from module.automation import auto
from module.notification.notification import NotificationLevel
from tasks.base.base import Base
from tasks.power.relicset import Relicset
from tasks.base.pythonchecker import PythonChecker
from utils.command import subprocess_with_timeout
import subprocess
import time
import sys
import os
from module.config import asu_config
from utils.console import pause_on_error, pause_and_retry
from tasks.power.instance import Instance


class Universe:
    @staticmethod
    def update():
        from module.update.update_handler import UpdateHandler
        from tasks.base.fastest_mirror import FastestMirror
        if cfg.universe_operation_mode == "exe":
            import requests
            import json
            if cfg.update_source == "MirrorChyan":
                if cfg.mirrorchyan_cdk == "":
                    log.error("未设置 Mirror酱 CDK")
                    pause_on_error()
                    sys.exit(0)
                # 符合Mirror酱条件
                response = requests.get(
                    f"https://mirrorchyan.com/api/resources/ASU_moe/latest?cdk={cfg.mirrorchyan_cdk}&user_agent=m7a_app",
                    timeout=10,
                    headers=cfg.useragent
                )
                if response.status_code == 200:
                    mirrorchyan_data = response.json()
                    if mirrorchyan_data["code"] == 0 and mirrorchyan_data["msg"] == "success":
                        url = mirrorchyan_data["data"]["url"]
                        update_handler = UpdateHandler(url, cfg.universe_path, "Auto_Simulated_Universe")
                        update_handler.run()
                else:
                    try:
                        mirrorchyan_data = response.json()
                        code = mirrorchyan_data["code"]
                        error_msg = mirrorchyan_data["msg"]

                        cdk_error_messages = {
                            7001: "Mirror酱 CDK 已过期",
                            7002: "Mirror酱 CDK 错误",
                            7003: "Mirror酱 CDK 今日下载次数已达上限",
                            7004: "Mirror酱 CDK 类型和待下载的资源不匹配",
                            7005: "Mirror酱 CDK 已被封禁"
                        }
                        if code in cdk_error_messages:
                            error_msg = cdk_error_messages[code]
                        log.error("Mirror酱 API 请求失败")
                        log.error(error_msg)
                    except:
                        log.error("Mirror酱 API 请求失败")
                    pause_on_error()
                    sys.exit(0)
            else:
                response = requests.get(FastestMirror.get_github_api_mirror("moesnow", "Auto_Simulated_Universe"), timeout=10, headers=cfg.useragent)
                if response.status_code == 200:
                    data = json.loads(response.text)
                    url = None
                    for asset in data["assets"]:
                        url = FastestMirror.get_github_mirror(asset["browser_download_url"])
                        break
                    if url is None:
                        log.error("没有找到可用更新，请稍后再试")
                        pause_on_error()
                        sys.exit(0)
                    update_handler = UpdateHandler(url, cfg.universe_path, "Auto_Simulated_Universe")
                    update_handler.run()
                else:
                    log.error(f"获取更新信息失败：{response.status_code}")
        elif cfg.universe_operation_mode == "source":
            cfg.set_value("universe_requirements", False)
            url = FastestMirror.get_github_mirror("https://github.com/CHNZYX/Auto_Simulated_Universe/archive/refs/heads/main.zip")
            update_handler = UpdateHandler(url, cfg.universe_path, "Auto_Simulated_Universe-main")
            update_handler.run()

    @staticmethod
    def check_path():
        status = False
        if cfg.universe_operation_mode == "exe":
            if not os.path.exists(os.path.join(cfg.universe_path, "diver.exe")):
                status = True
        elif cfg.universe_operation_mode == "source":
            if not os.path.exists(os.path.join(cfg.universe_path, "diver.py")):
                status = True
        if status:
            log.warning(f"模拟宇宙路径不存在: {cfg.universe_path}")
            Universe.update()

    @staticmethod
    def check_requirements():
        if not cfg.universe_requirements:
            log.info("开始安装依赖")
            from tasks.base.fastest_mirror import FastestMirror
            subprocess.run([cfg.python_exe_path, "-m", "pip", "install", "-i", FastestMirror.get_pypi_mirror(), "pip", "--upgrade"])
            while not subprocess.run([cfg.python_exe_path, "-m", "pip", "install", "-i", FastestMirror.get_pypi_mirror(), "-r", "requirements.txt"], check=True, cwd=cfg.universe_path):
                log.error("依赖安装失败")
                pause_and_retry()
            log.info("依赖安装成功")
            cfg.set_value("universe_requirements", True)

    @staticmethod
    def before_start():
        Universe.check_path()
        if cfg.universe_operation_mode == "source":
            PythonChecker.run()
            Universe.check_requirements()
        return True

    @staticmethod
    def start_calibration():
        """
        开始校准流程
        :return: 如果校准成功，返回 True；否则返回 False
        """
        return True
        # 不再强制校准
        # log.info("开始校准")
        # calibration_command = [os.path.join(cfg.universe_path, "align_angle.exe")] if cfg.universe_operation_mode == "exe" else [cfg.python_exe_path, "align_angle.py"]
        # log.debug(f"校准命令: {calibration_command}")
        # if subprocess_with_timeout(calibration_command, 60, cfg.universe_path, None if cfg.universe_operation_mode == "exe" else cfg.env):
        #     return True
        # else:
        #     return False

    @staticmethod
    def build_simulation_command(nums, category):
        """
        构建模拟宇宙命令
        :param nums: 运行次数
        :return: 模拟宇宙命令列表
        """
        if category == "divergent":
            command = [os.path.join(cfg.universe_path, "diver.exe")] if cfg.universe_operation_mode == "exe" else [cfg.python_exe_path, "diver.py"]
        else:
            command = [os.path.join(cfg.universe_path, "simul.exe")] if cfg.universe_operation_mode == "exe" else [cfg.python_exe_path, "simul.py"]

        if category == "divergent" and cfg.universe_disable_gpu:
            command.append("--cpu")

        if category != "divergent" and cfg.universe_bonus_enable:
            command.append("--bonus=1")

        if nums:
            command.append(f"--nums={nums}")
        return command

    def finalize_simulation(save, category):
        """
        完成模拟宇宙流程的后续处理
        :param save: 是否保存时间戳
        """
        if save:
            cfg.save_timestamp("universe_timestamp")

        screen.wait_for_screen_change('main')
        Universe.get_reward(category)

        if category != "divergent" and cfg.universe_bonus_enable and cfg.break_down_level_four_relicset:
            Relicset.run()

    @staticmethod
    def start_simulation(nums, save, category):
        """
        开始模拟宇宙流程
        :param nums: 运行次数
        :param save: 是否保存时间戳
        :return: 如果模拟宇宙成功，返回 True；否则返回 False
        """
        if auto.find_element("./assets/images/share/base/F.png", "image", 0.9, crop=(998.0 / 1920, 473.0 / 1080, 392.0 / 1920, 296.0 / 1080)):
            auto.press_key("f")
            if category == "divergent":
                screen.wait_for_screen_change('divergent_main')
            else:
                screen.wait_for_screen_change('universe_main')
        else:
            if category == "divergent":
                screen.change_to('divergent_main')
            else:
                screen.change_to('universe_main')
        log.info("开始模拟宇宙")
        command = Universe.build_simulation_command(nums, category)
        log.debug(f"模拟宇宙命令: {command}")
        if subprocess_with_timeout(command, cfg.universe_timeout * 3600, cfg.universe_path, None if cfg.universe_operation_mode == "exe" else cfg.env):
            Universe.finalize_simulation(save, category)
            return True
        else:
            return False

    @staticmethod
    def start(nums=cfg.universe_count, save=True, category=cfg.universe_category):
        log.hr("准备模拟宇宙", 0)
        if cfg.cloud_game_enable and cfg.browser_headless_enable:
            log.error("模拟宇宙不支持无界面模式运行")
            return False

        if Universe.before_start():

            if category == "divergent":
                asu_config.auto_config_divergent()
                screen.change_to('divergent_main')
            elif category == "divergent_weekly":
                category = "divergent"
                asu_config.auto_config_divergent_weekly()
                screen.change_to('divergent_main')
            else:
                asu_config.auto_config()
                screen.change_to('universe_main')

            # 等待可能的周一弹窗
            time.sleep(2)
            # 进入主界面
            screen.change_to('main')

            if Universe.start_calibration() and Universe.start_simulation(nums, save, category):
                return True

        log.error("模拟宇宙失败")
        log_path = os.path.join(cfg.universe_path, "logs")
        log.error(f"模拟宇宙日志路径: {log_path}")
        Base.send_notification_with_screenshot(cfg.notify_template['SimulatedUniverseNotCompleted'], NotificationLevel.ERROR)
        return False

    @staticmethod
    def get_reward(category):
        log.info("开始领取奖励")
        if auto.find_element("./assets/images/share/base/F.png", "image", 0.9, crop=(998.0 / 1920, 473.0 / 1080, 392.0 / 1920, 296.0 / 1080)):
            auto.press_key("f")
            if category == "divergent":
                screen.wait_for_screen_change('divergent_main')
            else:
                screen.wait_for_screen_change('universe_main')
        else:
            if category == "divergent":
                screen.change_to('divergent_main')
            else:
                screen.change_to('universe_main')
        time.sleep(1)
        if auto.click_element("./assets/images/share/base/RedExclamationMark.png", "image", 0.9, crop=(0 / 1920, 877.0 / 1080, 422.0 / 1920, 202.0 / 1080)):
            if auto.click_element("./assets/images/zh_CN/universe/one_key_receive.png", "image", 0.9, max_retries=10):
                if auto.find_element("./assets/images/zh_CN/base/click_close.png", "image", 0.8, max_retries=10):
                    time.sleep(2)
                    Base.send_notification_with_screenshot(cfg.notify_template['SimulatedUniverseRewardClaimed'], NotificationLevel.ALL)
                    auto.click_element("./assets/images/zh_CN/base/click_close.png", "image", 0.8, max_retries=10)
                    time.sleep(1)
                    auto.press_key("esc")
                    if category == "divergent" and cfg.universe_bonus_enable:
                        Universe.process_ornament()
        Base.send_notification_with_screenshot(cfg.notify_template['SimulatedUniverseCompleted'], NotificationLevel.ALL)

    @staticmethod
    def process_ornament():
        screen.change_to("guide3")

        immersifier_crop = (1623.0 / 1920, 40.0 / 1080, 162.0 / 1920, 52.0 / 1080)
        text = auto.get_single_line_text(crop=immersifier_crop, blacklist=['+', '米'], max_retries=3)
        if "/12" not in text:
            log.error("沉浸器数量识别失败")
            return

        immersifier_count = int(text.split("/")[0])
        log.info(f"沉浸器: {immersifier_count}/12")
        if immersifier_count > 0:
            Instance.run("饰品提取", cfg.instance_names["饰品提取"], 40, immersifier_count)

    @staticmethod
    def gui():
        if Universe.before_start():
            if subprocess.run(["start", "gui.exe"], shell=True, check=True, cwd=cfg.universe_path, env=cfg.env):
                return True
        return False

    @staticmethod
    def run_daily():
        return False
        # if config.daily_universe_enable:
        # return Universe.start(nums=1, save=False)

    @staticmethod
    def check_universe_score() -> bool:
        """
        检查模拟宇宙积分，达到 14000 时记录时间戳
        """
        screen.wait_for_screen_change("divergent_main")
        score_pos = (182 / 1920, 977 / 1080, 209 / 1920, 43 / 1080)
        score = auto.get_single_line_text(score_pos)
        if not score:
            log.warning("未识别到模拟宇宙积分")
            return False

        score_parts = score.split('/')
        if len(score_parts) == 2 and score_parts[0].isdigit() and score_parts[1].isdigit() and score_parts[1] == "14000":
            log.info(f"模拟宇宙积分：{score_parts[0]} / {score_parts[1]}")
            if score_parts[0] == "14000":
                cfg.save_timestamp("weekly_divergent_timestamp")
                log.info("已达到最高积分 14000，记录时间")
                return True
        else:
            log.warning(f"无法解析模拟宇宙积分: {score}")
        return False
