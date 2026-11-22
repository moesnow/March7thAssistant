import time

import numpy as np

from module.automation import auto
from module.automation.screenshot import Screenshot
from module.config import cfg
from module.localization import get_character_names
from module.logger import log
from tasks.base.list_drag import changed_ratio, drag_list
from tasks.power.policy import SupportNameSearch


SUPPORT_BUTTON_CROPS = {
    "standard": (966 / 1920, 954 / 1080, 176 / 1920, 60 / 1080),
    "ornament": (610 / 1920, 864 / 1080, 184 / 1920, 64 / 1080),
}
CHALLENGE = (1392 / 1920, 946 / 1080, 487 / 1920, 83 / 1080)
SUPPORT_RETRY_CROPS = {
    "standard": (966 / 1920, 946 / 1080, 913 / 1920, 83 / 1080),
    "ornament": (610 / 1920, 864 / 1080, 1269 / 1920, 165 / 1080),
}
SUPPORT_LIST_TITLES = ["支援列表", "支援角色"]
SUPPORT_LIST_TITLE_CROP = (157 / 1920, 22 / 1080, 300 / 1920, 81 / 1080)
SUPPORT_LIST_CROP = (40 / 1920, 180 / 1080, 544 / 1920, 770 / 1080)


def _support_scrollbar(frame):
    # 1080P 下轨道位于 x=568–583，滑块比左右两侧亮。
    track = frame.crop((round(frame.width * 528 / 544), 0, frame.width, frame.height))
    gray = np.asarray(track.convert("L"), dtype=np.int16)
    width = track.width
    side = round(width * 5 / 16)
    center = np.median(gray[:, round(width * 6 / 16):round(width * 10 / 16)], axis=1)
    sides = (np.median(gray[:, :side], axis=1) + np.median(gray[:, -side:], axis=1)) / 2
    edges = np.flatnonzero(np.diff(np.r_[False, center - sides >= 30, False]))
    top, bottom = max(zip(edges[::2], edges[1::2]), key=lambda span: span[1] - span[0], default=(0, 0))
    if bottom - top >= round(24 * frame.height / 770):
        return top, bottom
    return None


def _support_list_stable(before, after):
    previous = _support_scrollbar(before)
    current = _support_scrollbar(after)
    if previous is None and current is None:
        # 没有滑块时只比较头像列，避开持续播放的横幅。
        avatars = (0, 0, round(before.width * 106 / 544), before.height)
        return changed_ratio(before.crop(avatars), after.crop(avatars)) <= 0.01
    return previous is not None and current is not None and all(
        abs(a - b) <= 1 for a, b in zip(previous, current)
    )


def _button_in_crop(button, crop, frame_crop):
    if not button:
        return False
    (left, top), (right, bottom) = button
    frame_left, frame_top, frame_width, frame_height = auto.screenshot_pos
    frame_x, frame_y, frame_width_ratio, frame_height_ratio = frame_crop
    scale = auto.screenshot_scale_factor
    x = frame_x + ((left + right) / 2 - frame_left) * scale * frame_width_ratio / frame_width
    y = frame_y + ((top + bottom) / 2 - frame_top) * scale * frame_height_ratio / frame_height
    crop_x, crop_y, crop_width, crop_height = crop
    return crop_x <= x <= crop_x + crop_width and crop_y <= y <= crop_y + crop_height


class Character:
    @staticmethod
    def borrow(type="standard", *, for_training=False):
        # 检测是否可以执行借助支援角色
        if Character.is_borrow_disabled(for_training):
            return False

        # 点击支援按钮并进入支援列表
        if not Character.click_support_button(type):
            return False

        # 开始查找支援角色
        return Character.find_and_select_support(type)

    @staticmethod
    def is_borrow_disabled(for_training=False):
        """检测是否需要使用支援角色"""
        if not cfg.borrow_enable:
            return True
        return not (cfg.borrow_character_enable or for_training)

    @staticmethod
    def click_support_button(type):
        """点击支援按钮，进入支援列表"""
        crop = SUPPORT_BUTTON_CROPS.get(type)
        if crop is None:
            return False
        button = auto.find_element("支援", "text", max_retries=10, crop=crop)
        if not button:
            log.warning("找不到支援按钮，本次跳过借用支援")
            return False

        for attempt in range(2):
            auto.click_element_with_pos(button)
            time.sleep(1)
            if auto.find_element(SUPPORT_LIST_TITLES, "text", max_retries=10, crop=SUPPORT_LIST_TITLE_CROP):
                return True
            if attempt:
                break
            # 补点前用同一帧确认仍在挑战页，且支援按钮还在。
            frame_crop = SUPPORT_RETRY_CROPS[type]
            challenge = auto.find_element("开始挑战", "text", crop=frame_crop)
            if not _button_in_crop(challenge, CHALLENGE, frame_crop):
                break
            button = auto.find_element("支援", "text", take_screenshot=False, need_ocr=False)
            if not _button_in_crop(button, crop, frame_crop):
                break
        log.warning("未确认打开支援列表，本次跳过借用支援")
        return False

    @staticmethod
    def find_and_select_support(type):
        """查找并选择支援角色"""
        window = Screenshot.get_window(cfg.game_title_name)
        left, top, width, height = Screenshot.get_window_region(window)
        name_search = SupportNameSearch()

        for i in range(cfg.borrow_scroll_times):
            for key, value in cfg.borrow_friends:
                if key == "None":
                    continue
                if Character.find_character_and_click(key, value, left, top, width, height, name_search=name_search):
                    break
            else:
                # 若未找到角色，尝试滚动页面
                if i < cfg.borrow_scroll_times - 1:
                    if not Character.scroll_support_list():
                        if auto.find_element(SUPPORT_LIST_TITLES, "text", crop=SUPPORT_LIST_TITLE_CROP):
                            Character.exit_support_list(type)
                        return False
                continue

            # 当队伍已满时点击编队界面的最后一个槽位，踢出最后一个角色
            if auto.find_element(
                "已满",
                "text",
                include=True,
                retry_delay=0.5,
                max_retries=4,
                crop=(796 / 1920, 84 / 1080, 322 / 1920, 270 / 1080),
            ):
                if type == "standard":
                    auto.click_element((1654 / 1920, 506 / 1080, 106 / 1920, 108 / 1080), "crop")
                elif type == "ornament":
                    auto.click_element((908 / 1920, 794 / 1080, 48 / 1920, 46 / 1080), "crop")

            elif Character.confirm_selection(type):
                return True

        # 未借到支援角色，退出
        name_search.warn_if_unmatched()
        Character.exit_support_list(type)
        return False

    @staticmethod
    def find_character_and_click(key, value, left, top, width, height, *, name_search=None):
        """查找支援角色并点击"""
        crop = (0 / 1920, 0 / 1080, 593.0 / 1920, 1005.0 / 1080)
        image_path = "./assets/images/share/character/" + key + ".png"
        if name_search is None:
            name_search = SupportNameSearch()
        name = get_character_names().get(key, key) if value else key
        # 已入队头像可能带有右上角角标；原匹配未选到目标时才遮罩该区域重试。
        for mask_ratio in (None, 0.26):
            matches = auto.find_element(
                image_path, "image_with_multiple_targets", 0.8, max_retries=1,
                scale_range=0.9, crop=crop, relative=True,
                mask_top_right_ratio=mask_ratio,
            ) or []
            for match in matches:
                top_right = (match[1][0] + width * crop[0], match[0][1] + height * crop[1])
                crop_new = (top_right[0] / width, top_right[1] / height, 402.0 / 1920, 43.0 / 1080)
                if value == "":
                    auto.click_element_with_pos(match, (left, top))
                    time.sleep(1)
                    return True
                owner_match = name_search.find_owner(auto, name, value, crop_new)
                if owner_match and auto.click_element_with_pos(owner_match):
                    time.sleep(1)
                    return True
        return False

    @staticmethod
    def confirm_selection(type):
        """确认选择的支援角色并入队"""
        if type == "standard":
            if not auto.click_element(["入队", "确认"], "text", max_retries=10, crop=(1518 / 1920, 960 / 1080, 334 / 1920, 61 / 1080)):
                log.error("找不到入队按钮")
                return False
            time.sleep(1)
            result = auto.find_element(("解除支援", "取消"), "text", max_retries=10, include=True)
            return Character.process_support_selection_result(result)
        elif type == "ornament":
            return Character.complete_ornament_borrow()

    @staticmethod
    def process_support_selection_result(result):
        """处理支援选择的结果"""
        if result:
            if auto.matched_text == "解除支援":
                return True
            elif auto.matched_text == "取消":
                auto.click_element_with_pos(result)
                time.sleep(1)
                auto.find_element("支援列表", "text", max_retries=10, crop=(157.0 / 1920, 22.0 / 1080, 276.0 / 1920, 81.0 / 1080))
                return False
        return False

    @staticmethod
    def complete_ornament_borrow():
        """完成饰品提取的后续操作"""
        auto.press_key("esc")
        time.sleep(1)
        return bool(auto.find_element("解除支援", "text", max_retries=10, crop=SUPPORT_BUTTON_CROPS["ornament"]))

    @staticmethod
    def scroll_support_list():
        """拖动支援列表，失败时由调用方退出，不继续选择角色。"""
        completed = drag_list(auto, (400 / 1920, 850 / 1080), (400 / 1920, 400 / 1080),
                              crop=SUPPORT_LIST_CROP, duration=1.0, is_stable=_support_list_stable)
        time.sleep(0.5)
        return completed

    @staticmethod
    def exit_support_list(type):
        """退出支援列表"""
        auto.press_key("esc")
        time.sleep(1)
        crop = SUPPORT_BUTTON_CROPS.get(type)
        if crop is not None:
            auto.find_element("支援", "text", max_retries=10, crop=crop)
