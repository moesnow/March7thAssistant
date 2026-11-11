"""开拓力补充弹窗在两种界面下使用相同的相对布局。"""
import time

from module.logger import log
from tasks.power.policy import PowerError, normalize
from tasks.power.readout import read_number


TITLE = (0.40, 0.25, 0.20, 0.065)
DESCRIPTION = (0.40, 0.55, 0.20, 0.054)
CANCEL = (0.25, 0.68, 0.23, 0.13)
CONFIRM = (0.52, 0.68, 0.23, 0.13)
AMOUNT_TITLE = (0.35, 0.18, 0.26, 0.13)
QUANTITIES = {
    "后备开拓力": ((1016, 486), (880, 471, 42, 30), (550, 409, 130, 34), 1),
    "燃料": ((1046, 438), (926, 422, 24, 31), (824, 399, 48, 36), 60),
}


def _number(text):
    text = normalize(text)
    return int(text) if text.isdecimal() else None


def _crop(rect):
    x, y, w, h = rect
    return (x / 1280, y / 720, w / 1280, h / 720)


def supplement(auto, screen, config, balance, open_dialog, read_balance, *, return_screen):
    if not (config.use_reserved_trailblaze_power or config.use_fuel):
        return balance
    if not open_dialog() or not auto.find_element("开拓力补充", "text", crop=TITLE, max_retries=8, retry_delay=0.3):
        raise PowerError("未找到开拓力补充弹窗")

    def click_label(label, crop):
        return auto.click_element(label, "text", crop=crop, max_retries=6, retry_delay=0.25)

    expected = None
    try:
        for enabled, source, label, x in (
            (config.use_reserved_trailblaze_power, "后备开拓力", "取出等量后备开拓力", 528),
            (config.use_fuel, "燃料", "兑换60开拓力", 640),
        ):
            if not enabled:
                continue
            if not auto.click_element(_crop((x, 327, 0, 0)), "crop") or not auto.find_element(
                label, "text", crop=DESCRIPTION, max_retries=6, retry_delay=0.25,
            ):
                raise PowerError("未确认开拓力补充方式")
            stock = read_number(auto, _crop((x - 36, 364, 72, 26)), _number, "未识别到补充资源库存")
            if stock == 0:
                continue
            if not click_label("确认", CONFIRM):
                raise PowerError("无法确认补充方式")
            if not auto.find_element(source, "text", include=True, crop=AMOUNT_TITLE, max_retries=8, retry_delay=0.25):
                raise PowerError("未确认补充数量弹窗")
            max_point, max_crop, selected_crop, multiplier = QUANTITIES[source]
            max_quantity = read_number(auto, _crop(max_crop), _number, "未确认弹窗允许的最大补充量")
            if not 1 <= max_quantity <= stock:
                raise PowerError(f"游戏显示的最大补充量无效：{max_quantity}")
            if not auto.click_element(_crop((*max_point, 0, 0)), "crop"):
                raise PowerError("无法点选最大补充量")
            read_number(auto, _crop(selected_crop), lambda text: max_quantity if _number(text) == max_quantity else None,
                        "补充数量未达到弹窗最大值")
            confirm = (0.52, 0.75, 0.23, 0.1) if source == "后备开拓力" else CONFIRM
            if not click_label("确认", confirm):
                raise PowerError("无法确认补充数量")
            expected = max_quantity * multiplier
            break
    except PowerError:
        click_label("取消", (0.25, 0.68, 0.23, 0.19))
        if auto.find_element("开拓力补充", "text", crop=TITLE):
            click_label("取消", CANCEL)
        raise

    if expected is not None:
        if auto.find_element("获得物品", "text", crop=(0.40, 0.07, 0.20, 0.13), max_retries=5, retry_delay=0.3):
            auto.click_element(_crop((640, 569, 0, 0)), "crop")
            time.sleep(0.4)
    if auto.find_element("开拓力补充", "text", crop=TITLE) and not click_label("取消", CANCEL):
        raise PowerError("无法关闭开拓力补充弹窗")
    screen.wait_for_screen_change(return_screen, max_recursion=0)
    if expected is None:
        return balance
    after = read_balance()
    if not balance + expected <= after <= balance + expected + 1:
        raise PowerError(f"补充开拓力后余额未确认（原有 {balance}，预期增加 {expected}，实际 {after}）")
    log.info(f"开拓力由 {balance} 补充至 {after}")
    return after
