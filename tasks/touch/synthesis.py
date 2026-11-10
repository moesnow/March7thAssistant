"""触屏每日实训的微光原核合成。"""
import re
import time

from module.automation import auto
from module.logger import log
from module.screen import screen
from tasks.touch.daily import DailyTrainingError, REWARD_POPUP, REWARD_POPUP_CROP


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


def _filter_recipes():
    if not auto.click_element((222 / 1920, 994 / 1080, 0, 0), "crop"):
        raise DailyTrainingError("无法打开合成筛选")
    if not auto.find_element("筛选规则", "text", crop=FILTER_TITLE, max_retries=6, retry_delay=0.25):
        raise DailyTrainingError("未确认合成筛选弹窗")
    for text, crop in (("全部清除", FILTER_CLEAR), ("通用培养材料", FILTER_OPTION), ("确认", FILTER_CONFIRM)):
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
    screen.change_to("material", max_recursion=1)
    _filter_recipes()
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
    if not auto.click_element("合成", "text", crop=SYNTHESIZE):
        raise DailyTrainingError("未找到微光原核的合成按钮")

    if not auto.find_element(REWARD_POPUP, "image", 0.9, crop=REWARD_POPUP_CROP,
                             max_retries=4, retry_delay=0.3):
        if not auto.find_element("微光原核", "text", include=True, crop=DIALOG_CONTENT):
            raise DailyTrainingError("点击合成后未确认微光原核或奖励弹窗")
        if not auto.click_element("确认", "text", crop=DIALOG_CONFIRM):
            raise DailyTrainingError("未找到合成确认按钮")
        if not auto.find_element(REWARD_POPUP, "image", 0.9, crop=REWARD_POPUP_CROP,
                                 max_retries=10, retry_delay=0.3):
            raise DailyTrainingError("确认合成后未出现获得物品")
    if not auto.click_element((960 / 1920, 854 / 1080, 0, 0), "crop"):
        raise DailyTrainingError("无法关闭合成获得物品弹窗")
    screen.wait_for_screen_change("material", max_recursion=0)
    log.info("已合成 1 个微光原核")
    return True
