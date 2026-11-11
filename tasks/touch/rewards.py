"""触屏 720p 的日常领奖。"""
import time

import cv2
import numpy as np

from module.automation import auto
from module.automation.automation import screenshot_retry_timeout
from module.config import cfg
from module.localization import tr
from module.logger import log
from module.notification.notification import NotificationLevel
from module.screen import screen
from tasks.base.base import Base
from tasks.base.list_drag import changed_ratio, drag_list
from tasks.base.task_steps import run_steps
from tasks.reward.menu_alert import menu_alert
from tasks.reward.receipt import RewardError
from tasks.touch import daily
from utils.date import Date
from utils.image_utils import ImageUtils


IMAGE_ROOT = "./assets/touch_720/images/reward"
MAIL_ALERT_CROP = (0.924, 0.235, 0.076, 0.142)
ASSIST_ALERT_CROP = (0.835, 0.06, 0.105, 0.10)
MAIL_RECEIVE_CROP = (407 / 1920, 952 / 1080, 277 / 1920, 63 / 1080)
SRPASS_MENU = (1117 / 1920, 385 / 1080, 650 / 1920, 645 / 1080)
SRPASS_OPEN = (1357 / 1920, 793 / 1080, 321 / 1920, 99 / 1080)
SRPASS_RECEIVE = (866 / 1920, 957 / 1080, 947 / 1920, 113 / 1080)
SRPASS_CLOSE = (510 / 1920, 818 / 1080, 900 / 1920, 244 / 1080)
SRPASS_PAID_UNLOCK = (0.74, 0.88, 0.25, 0.10)
DISPATCH_RECEIVE_CROP = (1270 / 1920, 905 / 1080, 493 / 1920, 90 / 1080)
DISPATCH_STATUS_CROP = (1228 / 1920, 482 / 1080, 571 / 1920, 132 / 1080)
DISPATCH_RUNNING = ("委托正在进行中", "委托派遣中", "每小时可持续获得奖励")
SUPPORT_HEADER = (1046 / 1920, 181 / 1080, 822 / 1920, 66 / 1080)
SUPPORT_GIFT = (1050 / 1920, 165 / 1080, 822 / 1920, 144 / 1080)
MESSAGE_LIST = (60 / 1920, 138 / 1080, 557 / 1920, 774 / 1080)
MESSAGE_CONTACT_ALERT = (137 / 1920, 141 / 1080, 43 / 1920, 764 / 1080)
MESSAGE_PENDING = (96 / 1920, 141 / 1080, 52 / 1920, 768 / 1080)
MESSAGE_REPLIES = (708 / 1920, 744 / 1080, 76 / 1920, 272 / 1080)
MESSAGE_STICKERS = (872 / 1920, 749 / 1080, 796 / 1920, 62 / 1080)


class MessageTimeout(RewardError):
    """单个短信会话超时。"""


def _close_item_reward(return_screen, *, notify=None):
    if not auto.find_element(daily.REWARD_POPUP, "image", 0.9, crop=daily.REWARD_POPUP_CROP,
                             max_retries=15, retry_delay=0.25):
        raise RewardError("领取结果未确认（未出现获得物品）")
    if notify:
        frame, _, _ = auto.take_screenshot(crop=daily.REWARD_REPORT_CROP)
        Base.send_notification_with_screenshot(notify, NotificationLevel.ALL, screenshot=frame)
    if not auto.click_element((960 / 1920, 854 / 1080, 0, 0), "crop"):
        log.warning("已确认到账，获得物品弹窗仍未关闭")
        return False
    return True


def claim_dispatch():
    screen.change_to("dispatch", max_recursion=1)
    if not auto.click_element("领取奖励", "text", crop=DISPATCH_RECEIVE_CROP,
                              max_retries=4, retry_delay=0.3):
        if auto.find_element(DISPATCH_RUNNING, "text", include=True, crop=DISPATCH_STATUS_CROP):
            log.info("委托派遣中，暂无奖励")
            return
        raise RewardError("未确认委托可领或派遣中的状态")

    _close_item_reward("dispatch")
    log.info("已领取委托奖励")


def claim_mail():
    screen.change_to("menu", max_recursion=1)
    if menu_alert(auto, MAIL_ALERT_CROP, "./assets/images/share/menu/mail.png", scales=(0.62, 0.9)) is False:
        log.info("已确认邮件图标无红点")
        return

    screen.change_to("mail", max_recursion=1)
    button = auto.find_element("全部领取", "text", crop=MAIL_RECEIVE_CROP,
                               max_retries=5, retry_delay=0.3)
    if not button:
        if auto.find_element(("暂无邮件", "没有邮件"), "text", include=True):
            log.info("邮箱暂无可领取附件")
            return
        raise RewardError("未确认邮箱附件状态")
    # 未读邮件也会显示红点。只有金色的「全部领取」按钮可领取附件。
    red, green, blue = np.moveaxis(np.asarray(auto.screenshot.convert("RGB")), -1, 0)
    if ((red > 180) & (green > 125) & (blue < 155)).mean() < 0.25:
        log.info("邮箱暂无可领取附件")
        return
    if not auto.click_element_with_pos(button):
        raise RewardError("无法点击邮箱的全部领取按钮")
    _close_item_reward("mail", notify="邮件奖励已领取")
    log.info("已领取邮件奖励")


def _open_srpass():
    """等待新赛季片头结束，按需开启免费勋礼。"""
    opened = False
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        if screen.check_screen("pass1") or screen.check_screen("pass2"):
            return
        if not opened:
            opened = auto.click_element("开启无名勋礼", "text", crop=SRPASS_OPEN)
        time.sleep(0.4)
    raise RewardError("未进入无名勋礼")


def _claim_srpass_tab(tab, label):
    button = auto.find_element("一键领取", "text", crop=SRPASS_RECEIVE, max_retries=3, retry_delay=0.3)
    if not button:
        return
    if not auto.click_element_with_pos(button):
        raise RewardError("无法点击无名勋礼的一键领取")
    time.sleep(3)
    deadline = time.monotonic() + 16
    while time.monotonic() < deadline:
        if auto.find_element(daily.REWARD_POPUP, "image", 0.9, crop=daily.REWARD_POPUP_CROP):
            _close_item_reward(tab)
        elif auto.click_element(("点击空白处关闭", "点击任意处关闭"), "text", crop=SRPASS_CLOSE):
            time.sleep(0.5)
        elif screen.check_screen(tab) and not auto.find_element("一键领取", "text", crop=SRPASS_RECEIVE):
            log.info(f"已领取无名勋礼{label}")
            return
        time.sleep(0.4)
    raise RewardError("无名勋礼领取后未确认返回")


def claim_srpass():
    screen.change_to("menu", max_recursion=1)
    if not auto.click_element("无名勋礼", "text", crop=SRPASS_MENU, max_retries=3, retry_delay=0.3):
        auto.drag_mouse((1710 / 1920, 474 / 1080), (1710 / 1920, 975 / 1080), 0.6)
        time.sleep(0.7)
        if not auto.click_element("无名勋礼", "text", crop=SRPASS_MENU):
            log.info("手机菜单暂无无名勋礼")
            return
    _open_srpass()
    screen.change_to("pass2", max_recursion=1)
    _claim_srpass_tab("pass2", "本周及本期任务经验")
    screen.change_to("pass1", max_recursion=1)
    if auto.find_element("解锁无名客的荣勋", "text", crop=SRPASS_PAID_UNLOCK, max_retries=4, retry_delay=0.3):
        _claim_srpass_tab("pass1", "等级奖励")
    else:
        log.info("未确认无名勋礼付费档仍锁定，跳过等级奖励")


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
    if menu_alert(auto, ASSIST_ALERT_CROP, "./assets/touch_720/images/screen/menu.png") is False:
        log.info("已确认更多菜单无红点")
        return

    screen.change_to("visa", max_recursion=1)
    if not auto.find_element("支援角色", "text", crop=SUPPORT_HEADER):
        if not auto.click_element("角色展示", "text", crop=(802 / 1920, 54 / 1080, 286 / 1920, 70 / 1080)):
            raise RewardError("无法切换到漫游签证的角色展示")
        time.sleep(0.5)
    if not auto.find_element("支援角色", "text", crop=SUPPORT_HEADER):
        raise RewardError("未确认漫游签证的支援角色栏")
    gift = _find_support_gift()
    if not gift:
        log.info("暂无支援礼盒")
        return
    if not auto.click_element_with_pos(gift):
        raise RewardError("支援礼盒无法点击")
    _close_item_reward("visa")
    log.info("已领取支援奖励")


def _message_pending():
    return auto.find_element(f"{IMAGE_ROOT}/message_pending.png", "image", 0.9, crop=MESSAGE_PENDING)


def _finish_message():
    """只回复可见选项，等待会话完成或出现领奖弹窗。"""
    deadline = time.monotonic() + 65
    finished_frames = 0
    while time.monotonic() < deadline:
        if auto.find_element(daily.REWARD_POPUP, "image", 0.9, crop=daily.REWARD_POPUP_CROP):
            _close_item_reward("incoming_message")
            log.info("已领取短信奖励")
            return True
        if _message_pending():
            finished_frames = 0
            replies = auto.find_element(f"{IMAGE_ROOT}/message_reply.png", "image_with_multiple_targets",
                                        0.9, crop=MESSAGE_REPLIES)
            if replies:
                first = min(replies, key=lambda box: box[0][1])
                if not auto.click_element_with_pos(first):
                    raise RewardError("短信回复选项无法点击")
                time.sleep(1)
            else:
                sticker = auto.find_element(f"{IMAGE_ROOT}/message_sticker.png", "image", 0.94,
                                            crop=MESSAGE_STICKERS)
                if sticker:
                    if not auto.click_element_with_pos(sticker, offset=(55, 62)):
                        raise RewardError("短信表情回复无法点击")
                    time.sleep(1)
        else:
            finished_frames += 1
            if finished_frames == 3:
                log.info("短信会话已结束，未出现奖励弹窗")
                return False
        time.sleep(0.75)
    raise MessageTimeout("短信会话未在限时内结束")


def _open_unread_message(avoid=()):
    thread_icon = f"{IMAGE_ROOT}/message_thread.png"

    def find_thread():
        if not avoid:
            return auto.find_element(thread_icon, "image", 0.89, crop=MESSAGE_PENDING, max_retries=3, retry_delay=0.25)
        candidates = auto.find_element(thread_icon, "image_with_multiple_targets", 0.89, crop=MESSAGE_PENDING) or []
        return next((box for box in candidates if all(abs(box[0][1] - row) > 22 for row in avoid)), None)

    thread = find_thread()
    if not thread:
        contact = auto.find_element(f"{IMAGE_ROOT}/message_alert.png", "image", 0.89, crop=MESSAGE_CONTACT_ALERT)
        if not contact:
            return False
        if not auto.click_element_with_pos(contact, offset=(18, 14)):
            raise RewardError("无法展开有未读短信的联系人")
        time.sleep(0.4)
        thread = find_thread()
        if not thread:
            if avoid:
                return False
            raise RewardError("联系人有红点，但未找到待处理会话")
    if not auto.click_element_with_pos(thread, offset=(24, 0)):
        raise RewardError("未读会话无法点击")
    if not auto.find_element(f"{IMAGE_ROOT}/message_pending.png", "image", 0.9, crop=MESSAGE_PENDING,
                             max_retries=6, retry_delay=0.25):
        raise RewardError("未确认短信进入待回复状态")
    return True


def claim_messages():
    # 打开过但未读完的短信，手机菜单的红点可能已消失。以短信页的标记为准。
    screen.change_to("incoming_message", max_recursion=1)
    completed = 0
    received = 0
    timed_out = 0
    blocked_rows = set()
    drags = 0
    try:
        for _ in range(30):
            if (not timed_out and _message_pending()) or _open_unread_message(blocked_rows):
                try:
                    received += bool(_finish_message())
                    completed += 1
                except MessageTimeout as error:
                    timed_out += 1
                    if pending := _message_pending():
                        blocked_rows.add(pending[0][1])
                    log.warning(f"{error}，尝试返回列表继续其他会话")
                    screen.change_to("menu", max_recursion=0)
                    screen.change_to("incoming_message", max_recursion=0)
                drags = 0
                continue
            if drags >= 4:
                break
            before, _, _ = auto.take_screenshot(crop=MESSAGE_LIST)
            if not drag_list(auto, (478 / 1920, 834 / 1080), (478 / 1920, 328 / 1080),
                             crop=MESSAGE_LIST, end_pause=0.2, settle=0.4):
                raise RewardError("短信列表拖动后未稳定")
            if changed_ratio(before, auto.screenshot) <= 0.01:
                break
            drags += 1
    finally:
        if received:
            Base.send_notification_with_screenshot(f"处理了 {completed} 个短信会话，领取 {received} 次奖励", NotificationLevel.ALL)
    log.info(f"本次已处理 {completed} 个短信会话" if completed else "本次未发现待处理短信")
    if timed_out:
        raise RewardError(f"有 {timed_out} 个短信会话超时")


def _claim():
    return run_steps((name, action) for enabled, name, action in (
        (cfg.reward_dispatch_enable, "委托", claim_dispatch),
        (cfg.reward_mail_enable, "邮件", claim_mail),
        (cfg.reward_assist_enable, "支援礼盒", claim_assist),
        (cfg.reward_srpass_enable, "无名勋礼", claim_srpass),
        (cfg.reward_message_enable, "短信", claim_messages),
    ) if enabled)


def claim():
    """领取启用的日常奖励。"""
    log.hr("开始触屏领奖", 0)
    with screenshot_retry_timeout(5):
        return _claim()


def run(*, complete_training=False, on_summary=None):
    def report_daily(summary):
        on_summary(tr("奖励检查完成，{daily_summary}").format(daily_summary=summary))

    log.hr("开始触屏领奖", 0)
    with screenshot_retry_timeout(5):
        if cfg.reward_enable and not _claim():
            return False
        return daily.run(complete_training=complete_training, on_summary=report_daily if on_summary is not None else None)


def run_daily_training(*, on_summary=None):
    return daily.run(complete_training=True, on_summary=on_summary)


def routine(*, on_summary=None, full_run=False, on_step=None):
    """on_step(name, state, summary) 转发 run_steps 的步骤事件，summary 是该步的一行摘要。"""
    from tasks.touch import power
    from tasks.power.policy import SupportDemand

    summaries = []
    step_summaries = {}

    def collector(name):
        # 没人要摘要时保持 None，与不传回调时的调用完全一致。
        if on_summary is None and on_step is None:
            return None

        def collect(text):
            summaries.append(text)
            step_summaries[name] = text
        return collect

    steps = []
    demand = SupportDemand()

    def query_support():
        demand.pending = daily.support_demand(full_run=full_run).pending

    if cfg.power_enable:
        steps.append(("查询支援实训", query_support))
        if cfg.echo_of_war_enable and (not full_run or Date.is_next_mon_x_am(cfg.echo_of_war_timestamp, cfg.refresh_hour)):
            steps.append(("历战余响", lambda: power.run_weekly_echo(borrow_for_daily=demand)))
        steps.append(("清体力", lambda: power.run(borrow_for_daily=demand, on_summary=collector("清体力"))))
    if cfg.reward_enable:
        steps.append(("日常领奖", claim))
    steps.append(("每日实训", lambda: daily.run(complete_training=True, full_run=full_run,
                                               on_summary=collector("每日实训"))))

    def report(name, state):
        on_step(name, state, step_summaries.get(name))

    with screenshot_retry_timeout(5):
        result = run_steps(steps, on_step=None if on_step is None else report)
        screen.change_to("main", max_recursion=1)
    if summaries and on_summary is not None:
        on_summary(tr("；").join(summaries))
    return result
