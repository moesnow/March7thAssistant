"""触屏每日实训的微光原核合成。"""
import re
import time

from module.automation import auto
from module.automation.automation import screenshot_retry_timeout
from module.automation.input_base import input_deadline, input_deadline_reached, limit_input_deadline
from module.logger import log
from module.screen import screen
from tasks.base.task_steps import FATAL_GAME_ERRORS, optional_reward
from tasks.touch.daily import DailyTrainingError, REWARD_CLOSE_CROP, REWARD_POPUP, REWARD_POPUP_CROP
from utils.pause import pause_ctl


FILTER_TITLE = (244 / 1920, 158 / 1080, 247 / 1920, 84 / 1080)
FILTER_OPTION = (363 / 1920, 317 / 1080, 579 / 1920, 67 / 1080)
FILTER_CLEAR = (492 / 1920, 833 / 1080, 412 / 1920, 84 / 1080)
FILTER_CONFIRM = (1015 / 1920, 833 / 1080, 419 / 1920, 84 / 1080)
RECIPES = (183 / 1920, 133 / 1080, 499 / 1920, 790 / 1080)
RECIPE_TITLE = (1155 / 1920, 134 / 1080, 284 / 1920, 48 / 1080)
MATERIALS = (1149 / 1920, 733 / 1080, 285 / 1920, 47 / 1080)
AMOUNT = (1197 / 1920, 806 / 1080, 229 / 1920, 55 / 1080)
SYNTHESIZE = (1055 / 1920, 945 / 1080, 495 / 1920, 84 / 1080)
DIALOG_CONTENT = (446 / 1920, 301 / 1080, 1029 / 1920, 481 / 1080)
DIALOG_CONFIRM = (973 / 1920, 739 / 1080, 491 / 1920, 183 / 1080)
CORE = "./assets/touch_720/images/synthesis/core.png"


def _check():
    pause_ctl.check_stop()
    if input_deadline_reached(time.monotonic()):
        raise DailyTrainingError("实训合成等待超时，返回实训页核对奖励")


def _wait(probe, message, timeout=15):
    deadline = min(time.monotonic() + timeout, input_deadline.get() or float("inf"))
    with limit_input_deadline(deadline), screenshot_retry_timeout(2):
        while time.monotonic() < deadline:
            _check()
            try:
                result = probe()
            except Exception as error:
                if isinstance(error, FATAL_GAME_ERRORS) and not (
                    getattr(error, "frame_only", False)
                    or getattr(error, "code", None) in ("frame_timeout", "frame_clock_unavailable")
                ):
                    raise
                log.debug(f"实训合成画面暂未确认：{error}")
                result = None
            _check()
            if result:
                return result
            time.sleep(min(0.3, max(0, deadline - time.monotonic())))
    raise DailyTrainingError(message)


def _reward_visible():
    return auto.find_element(REWARD_POPUP, "image", 0.9, crop=REWARD_POPUP_CROP)


def _synthesis_response():
    if _reward_visible():
        return "reward"
    text = _read_text(DIALOG_CONTENT)
    if "确认合成" in text and "微光原核" in text:
        return "confirm"


def _filter_recipes():
    if not auto.click_element((222 / 1920, 994 / 1080, 0, 0), "crop"):
        raise DailyTrainingError("无法打开合成筛选")
    if not auto.find_element("筛选规则", "text", crop=FILTER_TITLE, max_retries=6, retry_delay=0.25):
        raise DailyTrainingError("未确认合成筛选弹窗")
    for text, crop in (("全部清除", FILTER_CLEAR), ("通用培养材料", FILTER_OPTION), ("确认", FILTER_CONFIRM)):
        _check()
        if not auto.click_element(text, "text", crop=crop, max_retries=4, retry_delay=0.25):
            raise DailyTrainingError(f"合成筛选未找到「{text}」")
        time.sleep(0.35)
    screen.wait_for_screen_change("material", max_recursion=0)


def _read_text(crop):
    auto.take_screenshot(crop=crop)
    auto.perform_ocr()
    lines = sorted(auto.ocr_result, key=lambda line: line[0][0][0])
    return "".join("".join(text.split()) for _, (text, _) in lines)


def material():
    with limit_input_deadline(time.monotonic() + 90), screenshot_retry_timeout(3):
        return _material()


def _material():
    _check()
    screen.change_to("material", max_recursion=1)
    _check()
    _filter_recipes()
    _check()
    if not auto.find_element("微光原核", "text", crop=RECIPE_TITLE):
        if not auto.click_element(CORE, "image", 0.89, crop=RECIPES):
            raise DailyTrainingError("未找到微光原核配方")
        if not auto.find_element("微光原核", "text", crop=RECIPE_TITLE, max_retries=5, retry_delay=0.3):
            raise DailyTrainingError("选中配方后未确认是微光原核")
    if not re.fullmatch(r"合成数量[:：]?1", _read_text(AMOUNT)):
        raise DailyTrainingError("未确认只合成 1 个微光原核")
    materials = re.fullmatch(r"(\d+)/(\d+)", _read_text(MATERIALS))
    if not materials or int(materials[2]) != 3:
        raise DailyTrainingError("未确认微光原核的合成材料数量")
    if int(materials[1]) < int(materials[2]):
        log.info("微光原核所需材料不足，跳过实训合成")
        return False
    _check()
    if not auto.click_element("合成", "text", crop=SYNTHESIZE):
        raise DailyTrainingError("未找到微光原核的合成按钮")

    response = _wait(_synthesis_response, "点击合成后未确认微光原核或奖励弹窗")
    if response == "confirm":
        button = _wait(lambda: auto.find_element("确认", "text", crop=DIALOG_CONFIRM),
                       "未找到合成确认按钮")
        _check()
        # 确认可能已生效，即使输入回执丢失也只等待结果，不重复消耗材料。
        auto.click_element_with_pos(button)
        _wait(_reward_visible, "确认合成后未出现获得物品，返回实训页核对奖励")
    log.info("已合成 1 个微光原核")
    with optional_reward("合成到账后的弹窗收尾"):
        _check()
        if not auto.click_element(REWARD_CLOSE_CROP, "crop"):
            log.warning("已确认合成到账，获得物品弹窗仍未关闭")
        else:
            _wait(lambda: screen.check_screen("material"), "合成到账后未确认返回材料合成页", timeout=8)
    return True
