"""补充开拓力，以及补充失败后的弹窗恢复。"""
import time

from module.automation.automation import screenshot_retry_timeout
from module.automation.input_base import input_deadline_reached, limit_input_deadline, observe_input_dispatch
from module.logger import log
from tasks.power.policy import PowerError
from tasks.power.readout import read_number
from tasks.reward.receipt import ITEM_POPUP
from utils.pause import pause_ctl


def _crop(rect):
    x, y, w, h = rect
    return (x / 1280, y / 720, w / 1280, h / 720)


TITLE = _crop((512, 175, 256, 81))
DESCRIPTION = (0.40, 0.55, 0.20, 0.054)
CANCEL = _crop((335, 465, 269, 143))
CONFIRM = _crop((675, 465, 266, 143))
AMOUNT_TITLE = _crop((448, 123, 336, 132))

# 数量弹窗的最大值按钮。
PC_MAX_BUTTONS = {
    "后备开拓力": (941, 460),
    "燃料": (965, 422),
}
TOUCH_MAX_BUTTONS = {
    "后备开拓力": (1016, 486),
    "燃料": (1046, 438),
}


def _number(text):
    text = text.strip()
    return int(text) if text.isdecimal() else None


def _find_text(auto, text, crop, *, retries=1, include=False):
    return auto.find_element(text, "text", crop=crop, include=include, max_retries=retries, retry_delay=0.3)


def _check_input():
    pause_ctl.checkpoint()
    if input_deadline_reached(time.monotonic()):
        raise PowerError("补充开拓力操作超时")


def _click(auto, point):
    if point:
        _check_input()
        auto.click_element_with_pos(point)


def _tap(auto, x, y):
    _click(auto, auto.find_element(_crop((x, y, 0, 0)), "crop"))


def _prepare_exchange(auto, screen, config, locate_entry, return_screen, desktop):
    for _ in range(2):
        _click(auto, locate_entry())
        if _find_text(auto, "开拓力补充", TITLE, retries=8):
            break
        # 只在新画面确认仍在入口页时补点，避免点到加载中的弹窗。
        if not screen.check_screen(return_screen):
            raise PowerError("未找到开拓力补充弹窗")
    else:
        raise PowerError("未找到开拓力补充弹窗")

    max_buttons = PC_MAX_BUTTONS if desktop else TOUCH_MAX_BUTTONS
    stock_y, stock_height = (362, 29) if desktop else (364, 26)
    for enabled, source, label, x in (
        (config.use_reserved_trailblaze_power, "后备开拓力", "取出等量后备开拓力", 550 if desktop else 528),
        (config.use_fuel, "燃料", "兑换60开拓力", 640),
    ):
        if not enabled:
            continue
        if desktop:
            # PC 会把未耗尽的资源卡片重新居中；按图标定位，避免读到相邻星琼卡片。
            template = "reserved_trailblaze_power" if source == "后备开拓力" else "fuel"
            card = auto.find_element(f"./assets/images/share/power/trailblaze_power/{template}.png",
                                     "image", 0.9, relative=True, scale_range=(0.9, 1.1))
            if not card:
                continue
            x = (card[0][0] + card[1][0]) * 640 / auto.screenshot.width
        _tap(auto, x, 327)
        if not _find_text(auto, label, DESCRIPTION, retries=6):
            raise PowerError("未确认开拓力补充方式")
        stock = read_number(auto, _crop((x - 36, stock_y, 72, stock_height)), _number, "未识别到补充资源库存")
        if stock == 0:
            continue
        method_button = _find_text(auto, "确认", CONFIRM, retries=6)
        if not method_button:
            raise PowerError("无法确认补充方式")
        _click(auto, method_button)
        if not _find_text(auto, source, AMOUNT_TITLE, retries=8, include=True):
            raise PowerError("未确认补充数量弹窗")
        _tap(auto, *max_buttons[source])
        confirm = _find_text(auto, "确认", CONFIRM, retries=6)
        if not confirm:
            raise PowerError("无法确认补充数量")
        return confirm
    return None


def _return_from_dialog(auto, screen, return_screen, *, exchange_sent):
    remaining_inputs = 4
    waiting_for_return = exchange_sent
    # 转场只占用等待时间，关闭弹窗有独立的输入次数。
    for _ in range(20):
        if input_deadline_reached(time.monotonic()):
            break
        if screen.check_screen(return_screen):
            return
        if remaining_inputs:
            if exchange_sent and _find_text(auto, "获得物品", ITEM_POPUP):
                remaining_inputs -= 1
                _tap(auto, 640, 569)
            elif cancel := _find_text(auto, "取消", CANCEL):
                waiting_for_return = True
                remaining_inputs -= 1
                _click(auto, cancel)
            elif not waiting_for_return:
                break
        time.sleep(0.5)
    if not screen.check_screen(return_screen):
        raise PowerError(f"补充开拓力后未能恢复{screen.get_name(return_screen)}界面")


def supplement(auto, screen, config, balance, locate_entry, read_balance, *, return_screen, desktop=False):
    exchange_sent = False
    after = balance
    failure = None

    try:
        if not (config.use_reserved_trailblaze_power or config.use_fuel):
            return balance
        with screenshot_retry_timeout(5):
            with limit_input_deadline(time.monotonic() + 18):
                try:
                    confirm = _prepare_exchange(auto, screen, config, locate_entry, return_screen, desktop)
                    if confirm:
                        _check_input()
                        # 最终确认会消耗库存，派发后只核对结果。
                        def record_dispatch(_):
                            nonlocal exchange_sent
                            exchange_sent = True

                        if getattr(auto.input_handler, "reports_dispatch", False) is True:
                            with observe_input_dispatch(record_dispatch):
                                auto.click_element_with_pos(confirm)
                        else:
                            exchange_sent = True
                            auto.click_element_with_pos(confirm)
                        if not exchange_sent:
                            raise PowerError("未能发送补充开拓力确认")
                        # 为正常转场保留等待；获得页漏识别仍按实际余额收尾。
                        _find_text(auto, "获得物品", ITEM_POPUP, retries=8)
                except Exception as error:
                    failure = error

            with limit_input_deadline(time.monotonic() + 10):
                _return_from_dialog(auto, screen, return_screen, exchange_sent=exchange_sent)
                if exchange_sent:
                    after = read_balance()
    except Exception as error:
        # 后续副本照常导航，screen.change_to 会处理可退出的未知界面。
        failure = failure or error

    if after > balance:
        log.info(f"开拓力由 {balance} 补充至 {after}")
    if failure is not None:
        log.warning(f"补充步骤出现异常（{failure}），按已确认的开拓力继续清体力")
    return after
