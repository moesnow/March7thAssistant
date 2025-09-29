import os
import sys
import time
import psutil


from app.tools.account_manager import load_acc_and_pwd
from utils.registry.gameaccount import gamereg_uid
from .starrailcontroller import StarRailController

from utils.date import Date
from tasks.power.power import Power
from module.logger import log
from module.screen import screen
from module.automation import auto
from module.config import cfg
from module.notification import notif
from module.ocr import ocr


starrail = StarRailController(cfg.game_path, cfg.game_process_name, cfg.game_title_name, 'UnityWndClass', logger=log, script_path=cfg.script_path)


def start():
    log.hr("开始运行", 0)
    start_game()
    log.hr("完成", 2)


def start_game():
    MAX_RETRY = 3

    def wait_until(condition, timeout, period=1):
        """等待直到条件满足或超时"""
        end_time = time.time() + timeout
        while time.time() < end_time:
            if condition():
                return True
            time.sleep(period)
        return False

    def check_and_click_enter():
        # 点击进入
        if auto.click_element("./assets/images/screen/click_enter.png", "image", 0.9):
            return True
        # 游戏热更新，需要确认重启
        auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, take_screenshot=False)
        # 网络异常等问题，需要重新启动
        auto.click_element("./assets/images/zh_CN/base/restart.png", "image", 0.9, take_screenshot=False)
        # 适配国际服，需要点击“开始游戏”
        auto.click_element("./assets/images/screen/start_game.png", "image", 0.9, take_screenshot=False)
        # 适配B服，需要点击“登录”
        auto.click_element("./assets/images/screen/bilibili_login.png", "image", 0.9, take_screenshot=False)
        # 适配用户协议和隐私政策更新提示，需要点击“同意”
        auto.click_element("./assets/images/screen/agree_update.png", "image", 0.9, take_screenshot=False)
        # 登录过期
        if auto.find_element("./assets/images/screen/account_and_password.png", "image", 0.9, take_screenshot=False):
            if load_acc_and_pwd(gamereg_uid()) != (None, None):
                log.info("检测到登录过期，尝试自动登录")
                auto_login()
            else:
                raise Exception("账号登录过期")
        return False

    def get_process_path(name):
        # 通过进程名获取运行路径
        for proc in psutil.process_iter(attrs=['pid', 'name']):
            if name in proc.info['name']:
                process = psutil.Process(proc.info['pid'])
                return process.exe()
        return None

    for retry in range(MAX_RETRY):
        try:
            if not starrail.switch_to_game():
                if cfg.auto_set_resolution_enable:
                    starrail.change_resolution(1920, 1080)
                    starrail.change_auto_hdr("disable")

                if cfg.auto_battle_detect_enable:
                    starrail.change_auto_battle(True)

                if not starrail.start_game():
                    raise Exception("启动游戏失败")
                time.sleep(10)

                if not wait_until(lambda: starrail.switch_to_game(), 360):
                    starrail.restore_resolution()
                    starrail.restore_auto_hdr()
                    raise TimeoutError("切换到游戏超时")

                time.sleep(10)
                starrail.restore_resolution()
                starrail.restore_auto_hdr()
                starrail.check_resolution_ratio(1920, 1080)

                if not wait_until(lambda: check_and_click_enter(), 600):
                    raise TimeoutError("查找并点击进入按钮超时")
                time.sleep(10)
                # 修复B服问题 https://github.com/moesnow/March7thAssistant/discussions/321#discussioncomment-10565807
                auto.press_mouse()
            else:
                starrail.check_resolution_ratio(1920, 1080)
                if cfg.auto_set_game_path_enable:
                    program_path = get_process_path(cfg.game_process_name)
                    if program_path is not None and program_path != cfg.game_path:
                        cfg.set_value("game_path", program_path)
                        log.info(f"游戏路径更新成功：{program_path}")
                time.sleep(1)

            if not wait_until(lambda: screen.get_current_screen(), 360):
                raise TimeoutError("获取当前界面超时")
            break  # 成功启动游戏，跳出重试循环
        except Exception as e:
            log.error(f"尝试启动游戏时发生错误：{e}")
            starrail.stop_game()  # 确保在重试前停止游戏
            if retry == MAX_RETRY - 1:
                raise  # 如果是最后一次尝试，则重新抛出异常


def stop(detect_loop=False):
    log.hr("停止运行", 0)

    def play_audio():
        log.info("开始播放音频")
        try:
            from playsound3 import playsound
            playsound("./assets/audio/pa.mp3", backend="winmm")
            log.info("播放音频完成")
        except Exception as e:
            log.warning(f"播放音频时发生错误：{e}")

    if cfg.play_audio:
        play_audio()

    if detect_loop and cfg.after_finish == "Loop":
        after_finish_is_loop()
    else:
        if detect_loop:
            notify_after_finish_not_loop()
        if cfg.after_finish in ["Exit", "Loop", "Shutdown", "Sleep", "Hibernate", "Restart", "Logoff", "RunScript"]:
            starrail.shutdown(cfg.after_finish)
        log.hr("完成", 2)
        if cfg.after_finish not in ["Shutdown", "Sleep", "Hibernate", "Restart", "Logoff", "RunScript"]:
            input("按回车键关闭窗口. . .")
        sys.exit(0)


def after_finish_is_loop():

    def get_wait_time(current_power):
        # 距离体力到达配置文件指定的上限剩余秒数
        wait_time_power_limit = (cfg.power_limit - current_power) * 6 * 60
        # 距离第二天凌晨4点剩余秒数，+30避免显示3点59分不美观，#7
        wait_time_next_day = Date.get_time_next_x_am(cfg.refresh_hour) + 30
        # 取最小值
        wait_time = min(wait_time_power_limit, wait_time_next_day)
        return wait_time

    if cfg.loop_mode == "power":
        current_power = Power.get()
        if current_power >= cfg.power_limit:
            log.info(f"🟣开拓力 >= {cfg.power_limit}")
            log.info("即将再次运行")
            log.hr("完成", 2)
            return
        else:
            starrail.stop_game()
            wait_time = get_wait_time(current_power)
            future_time = Date.calculate_future_time(wait_time)
    else:
        starrail.stop_game()
        scheduled_time = cfg.scheduled_time
        wait_time = Date.time_to_seconds(scheduled_time)
        future_time = Date.calculate_future_time(scheduled_time)

    log.info(cfg.notify_template['ContinueTime'].format(time=future_time))
    notif.notify(cfg.notify_template['ContinueTime'].format(time=future_time))
    log.hr("完成", 2)
    # 等待状态退出OCR避免内存占用
    ocr.exit_ocr()
    time.sleep(wait_time)

    # 启动前重新加载配置 #262
    cfg._load_config()


def notify_after_finish_not_loop():

    def get_wait_time(current_power):
        # 距离体力到达300上限剩余秒数
        wait_time_power_full = (300 - current_power) * 6 * 60
        return wait_time_power_full

    current_power = Power.get()

    wait_time = get_wait_time(current_power)
    future_time = Date.calculate_future_time(wait_time)
    log.info(cfg.notify_template['FullTime'].format(power=current_power, time=future_time))
    notif.notify(cfg.notify_template['FullTime'].format(power=current_power, time=future_time))


def auto_login():
    def auto_type(text):
        after_alpha = False
        for character in text:
            if character.isalpha():
                after_alpha = True
            else:
                if after_alpha:
                    after_alpha = False
                    # 切换两下中英文模式，避免中文输入法影响英文输入
                    auto.secretly_press_key("shift", wait_time=0.1)
                    auto.secretly_press_key("shift", wait_time=0.1)
            auto.secretly_press_key(character, wait_time=0.1)
        if text[-1].isalpha():
            auto.secretly_press_key("shift", wait_time=0.1)
            auto.secretly_press_key("shift", wait_time=0.1)
        time.sleep(2)

    account, password = load_acc_and_pwd(gamereg_uid())
    if auto.click_element("./assets/images/screen/account_and_password.png", "image", 0.9, max_retries=10):
        if auto.click_element("./assets/images/screen/account_field.png", "image", 0.9, max_retries=10):
            auto_type(account)
            if auto.click_element("./assets/images/screen/password_field.png", "image", 0.9, take_screenshot=False):
                auto_type(password)
                if auto.click_element("./assets/images/screen/agree_conditions.png", "image", 0.9, max_retries=10):
                    if auto.click_element("./assets/images/screen/enter_game.png", "image", 0.9, max_retries=10):
                        if auto.find_element("./assets/images/screen/welcome.png", "image", 0.9, max_retries=10):
                            return
    raise Exception("尝试自动登录失败")
