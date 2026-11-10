"""触屏 720p 的日常领奖。"""
import time

import cv2
import numpy as np

from module.automation import auto
from module.automation.automation import screenshot_retry_timeout
from module.config import cfg
from module.logger import log
from module.notification.notification import NotificationLevel
from module.screen import screen
from tasks.base.base import Base
from tasks.touch import daily
from utils.image_utils import ImageUtils


IMAGE_ROOT = "./assets/touch_720/images/reward"
MAIL_ALERT_CROP = (1842 / 1920, 300 / 1080, 75 / 1920, 65 / 1080)
ASSIST_ALERT_CROP = (1710 / 1920, 75 / 1080, 68 / 1920, 65 / 1080)
MAIL_RECEIVE_CROP = (407 / 1920, 952 / 1080, 277 / 1920, 63 / 1080)
DISPATCH_RECEIVE_CROP = (1270 / 1920, 905 / 1080, 493 / 1920, 90 / 1080)
DISPATCH_STATUS_CROP = (1228 / 1920, 482 / 1080, 571 / 1920, 132 / 1080)
DISPATCH_RUNNING = ("委托正在进行中", "委托派遣中", "每小时可持续获得奖励")
SUPPORT_HEADER = (1046 / 1920, 181 / 1080, 822 / 1920, 66 / 1080)
SUPPORT_GIFT = (1050 / 1920, 165 / 1080, 822 / 1920, 144 / 1080)


class RewardError(RuntimeError):
    """奖励页面未达到预期状态。"""


def _has_alert(crop):
    return bool(auto.find_element(f"{IMAGE_ROOT}/alert.png", "image", 0.83, crop=crop))


def _close_item_reward(return_screen, *, notify=None):
    if not auto.find_element(daily.REWARD_POPUP, "image", 0.9, crop=daily.REWARD_POPUP_CROP,
                             max_retries=15, retry_delay=0.25):
        raise RewardError("点击领取后未确认获得物品")
    if notify:
        frame, _, _ = auto.take_screenshot(crop=daily.REWARD_REPORT_CROP)
        Base.send_notification_with_screenshot(notify, NotificationLevel.ALL, screenshot=frame)
    if not auto.click_element((960 / 1920, 854 / 1080, 0, 0), "crop"):
        raise RewardError("无法关闭获得物品弹窗")
    screen.wait_for_screen_change(return_screen, max_recursion=0)


def claim_dispatch():
    screen.change_to("dispatch", max_recursion=1)
    if not auto.click_element("领取奖励", "text", crop=DISPATCH_RECEIVE_CROP,
                              max_retries=4, retry_delay=0.3):
        if auto.find_element(DISPATCH_RUNNING, "text", include=True, crop=DISPATCH_STATUS_CROP):
            log.info("委托派遣中，暂无奖励")
            return
        raise RewardError("未确认委托可领或派遣中的状态")

    _close_item_reward("dispatch")
    if not auto.find_element(DISPATCH_RUNNING, "text", include=True,
                             crop=DISPATCH_STATUS_CROP, max_retries=6, retry_delay=0.3):
        raise RewardError("领取委托奖励后，未确认委托继续派遣")
    log.info("已领取委托奖励，现有委托继续派遣")


def claim_mail():
    screen.change_to("menu", max_recursion=1)
    if not _has_alert(MAIL_ALERT_CROP):
        log.info("邮箱没有奖励标记，跳过邮件")
        return

    screen.change_to("mail", max_recursion=1)
    if not auto.click_element("全部领取", "text", crop=MAIL_RECEIVE_CROP,
                              max_retries=5, retry_delay=0.3):
        raise RewardError("邮箱有奖励标记，但未找到全部领取按钮")
    _close_item_reward("mail", notify="邮件奖励已领取")
    log.info("已领取邮件奖励")


def _find_support_gift():
    """支援礼盒是亮金色。仅在支援角色标题栏内匹配盒身和丝带。"""
    frame, _, _ = auto.take_screenshot(crop=SUPPORT_GIFT)
    glyph = ImageUtils.read_image(f"{IMAGE_ROOT}/gift_shape.png", cv2.IMREAD_GRAYSCALE)
    box = find_support_gift(np.asarray(frame.convert("RGB")), glyph)
    return auto.calculate_text_position(box, False) if box else None


def find_support_gift(pixels, glyph):
    red, green, blue = np.moveaxis(pixels.astype(np.int16), -1, 0)
    cream = (red >= 223) & (green >= 208) & (blue >= 136) & (green - blue >= 21) & (red - green <= 24)
    mask = cream.astype(np.uint8) * 255
    best_score = 0.70
    best_box = None
    for scale in (0.8, 0.95, 1.0, 1.1, 1.25, 1.4, 1.55, 1.7, 1.85, 2.0, 2.15):
        template = cv2.resize(glyph, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        height, width = template.shape
        if height > mask.shape[0] or width > mask.shape[1]:
            break
        _, score, _, (x, y) = cv2.minMaxLoc(cv2.matchTemplate(mask, template, cv2.TM_CCOEFF_NORMED))
        if score > best_score:
            best_score = score
            best_box = ((x, y), (x + width, y), (x + width, y + height), (x, y + height))
    return best_box


def claim_assist():
    screen.change_to("menu", max_recursion=1)
    if not _has_alert(ASSIST_ALERT_CROP):
        log.info("漫游签证没有奖励标记，跳过支援奖励")
        return

    screen.change_to("visa", max_recursion=1)
    if not auto.find_element("支援角色", "text", crop=SUPPORT_HEADER):
        if not auto.click_element("角色展示", "text", crop=(802 / 1920, 54 / 1080, 286 / 1920, 70 / 1080)):
            raise RewardError("无法切换到漫游签证的角色展示")
        time.sleep(0.5)
    if not auto.find_element("支援角色", "text", crop=SUPPORT_HEADER):
        raise RewardError("未确认漫游签证的支援角色栏")
    gift = _find_support_gift()
    if not gift or not auto.click_element_with_pos(gift):
        raise RewardError("漫游签证有奖励标记，但未能定位支援礼盒")
    _close_item_reward("visa")
    log.info("已领取支援奖励")


def run():
    log.hr("开始触屏领奖", 0)
    with screenshot_retry_timeout(5):
        if cfg.reward_enable:
            try:
                for enabled, collect in (
                    (cfg.reward_dispatch_enable, claim_dispatch),
                    (cfg.reward_mail_enable, claim_mail),
                    (cfg.reward_assist_enable, claim_assist),
                ):
                    if enabled:
                        collect()
            except RewardError as error:
                log.error(f"触屏领奖：{error}")
                return False
        return daily.run()


def routine():
    from tasks.touch import power

    if cfg.power_enable and not power.run():
        return False
    if not run():
        return False
    with screenshot_retry_timeout(5):
        screen.change_to("main", max_recursion=1)
    return True
