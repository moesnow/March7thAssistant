"""
自动对话模块 — 场景检测器。

将所有"判断当前画面处于什么状态"的逻辑集中在此，
与点击执行逻辑解耦，便于单独测试和调整识别参数。
"""

from __future__ import annotations

import time
from typing import Optional

from module.automation import auto
from module.logger import log

from ._config import Crop, Img, Threshold


class SceneDetector:
    """游戏画面场景检测器。

    所有方法均为静态方法，不持有状态，仅依赖 Automation 实例 (auto)
    进行截图和模板匹配。
    """

    # ========================================================================
    # 对话场景判断
    # ========================================================================

    @staticmethod
    def is_dialog_scene() -> bool:
        """判断当前画面是否处于对话场景。

        检测逻辑（按优先级）：
        1. 左上角是否存在 start / start_ps5 / start_xbox 任意一个图标
           → 说明刚进入对话，等待推进
        2. 底部中央是否存在 continue 箭头
           → 说明对话正在展示中
        3. 右上角是否存在 hide 按钮（隐藏 UI）
           → 说明对话正在展示中

        返回:
            True  当前处于对话场景
            False 当前不处于对话场景
        """
        # 截取左上角区域用于 start 系列图标检测
        auto.take_screenshot(crop=Crop.DIALOG_START)

        # 1. 检测 start 图标（键鼠 / PS5 / Xbox 任一命中即可）
        for img_path in Img.START:
            if auto.find_element(img_path, "image", Threshold.START_MATCH, take_screenshot=False):
                return True

        # 2. 检测 continue 箭头（底部中央）
        if auto.find_element(
            Img.CONTINUE, "image", Threshold.CONTINUE_MATCH,
            crop=Crop.DIALOG_CONTINUE,
        ):
            return True

        # 3. 检测 hide 按钮 → 进一步确认对话选项
        if auto.find_element(
            Img.HIDE, "image", Threshold.HIDE_MATCH,
            crop=Crop.DIALOG_HIDE,
        ):
            return True

        return False

    # ========================================================================
    # 跳过按钮检测
    # ========================================================================

    @staticmethod
    def detect_skip_button() -> bool:
        """检测并点击跳过按钮（使用 YOLO 模型）。

        步骤：
        1. 在右上角区域用 YOLO 检测 skip 目标
        2. 若检测到并点击成功，轮询等待按钮消失（最多 1 秒）
        3. 按钮消失 = 跳过成功

        返回:
            True  成功检测并点击跳过按钮，且按钮已消失
            False 未检测到跳过按钮，或点击后按钮未消失
        """
        clicked = auto.click_element(
            target=Img.SKIP_MODEL,
            find_type="yolo",
            threshold=Threshold.SKIP_YOLO,
            crop=Crop.SKIP_BUTTON,
        )
        if not clicked:
            return False

        # 等待跳过按钮消失（最多 1 秒，每 50ms 检查一次）
        deadline = time.monotonic() + Threshold.SKIP_WAIT_TIMEOUT
        while time.monotonic() < deadline:
            time.sleep(Threshold.SKIP_POLL_INTERVAL)
            if not auto.find_element(
                Img.SKIP_MODEL, "yolo", Threshold.SKIP_YOLO,
                crop=Crop.SKIP_BUTTON,
            ):
                return True
        return False

    # ========================================================================
    # 确认弹窗检测
    # ========================================================================

    @staticmethod
    def click_confirm(max_retries: int = Threshold.CONFIRM_MAX_RETRIES,
                      retry_delay: float = Threshold.CONFIRM_RETRY_DELAY) -> bool:
        """检测并点击确认按钮。

        返回:
            True  点击成功
            False 重试耗尽仍未点击到
        """
        return auto.click_element(
            Img.CONFIRM, "image", Threshold.CONFIRM_MATCH,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )

    # ========================================================================
    # 对话选项检测
    # ========================================================================

    @staticmethod
    def has_dialog_options() -> bool:
        """检查当前画面是否存在对话选项（如分支选择）。

        在对话选项区域依次匹配 select / message / exit / prev-page 图标。

        返回:
            True  存在至少一个对话选项
            False 不存在任何对话选项
        """
        auto.take_screenshot(crop=Crop.DIALOG_OPTIONS)
        for img_path in Img.DIALOG_OPTIONS:
            if auto.find_element(img_path, "image", Threshold.DIALOG_OPTION_MATCH, take_screenshot=False):
                return True
        return False

    @staticmethod
    def click_dialog_option() -> bool:
        """点击对话选项区域（优先 SELECT，不存在则尝试 EXIT）。

        返回:
            True  找到并点击了选项
            False 未找到选项
        """
        # 先尝试点击 SELECT
        if auto.click_element(
            Img.SELECT, "image", Threshold.SELECT_MATCH,
            crop=Crop.DIALOG_OPTIONS,
        ):
            return True
        # 若未找到，再尝试点击 EXIT
        return auto.click_element(
            Img.EXIT, "image", Threshold.SELECT_MATCH,
            crop=Crop.DIALOG_OPTIONS,
        )

    # ========================================================================
    # 自动战斗检测
    # ========================================================================

    @staticmethod
    def is_auto_battle_off() -> bool:
        """检查自动战斗是否处于关闭状态。

        在左下角区域检测"未自动战斗"图标。

        返回:
            True  自动战斗未开启
            False 自动战斗已开启或未检测到
        """
        return auto.find_element(
            Img.NOT_AUTO, "image", Threshold.NOT_AUTO_MATCH,
            crop=Crop.NOT_AUTO,
        )

    # ========================================================================
    # 手机对话页面检测
    # ========================================================================

    @staticmethod
    def handle_phone_dialogs() -> None:
        """检测并关闭手机对话页面。

        检测两种手机消息窗口（灰白色背景区域），
        若存在则点击该区域然后移动鼠标到安全位置，
        并尝试点击关闭按钮。
        """
        # 检测第一种手机消息窗口
        if auto.is_rgb_ratio_above_threshold(
            Crop.PHONE_MSG, Threshold.PHONE_RGB,
            Threshold.PHONE_RGB_RATIO, tolerance=Threshold.RGB_TOLERANCE,
        ):
            auto.click_element(Crop.PHONE_MSG, "crop")
            auto.click_element(Crop.WHITE_CORNER, "crop", action="move")

        # 关闭手机按钮
        auto.click_element(
            Img.CLOSE_PHONE, "image", Threshold.CLOSE_PHONE_MATCH,
            crop=Crop.CLOSE_PHONE,
        )

        # 检测第二种手机消息窗口
        if auto.is_rgb_ratio_above_threshold(
            Crop.PHONE_MSG2, Threshold.PHONE_RGB,
            Threshold.PHONE2_RGB_RATIO, tolerance=Threshold.RGB_TOLERANCE,
        ):
            auto.click_element(Crop.PHONE_MSG2, "crop")
            auto.click_element(Crop.WHITE_CORNER, "crop", action="move")

    # ========================================================================
    # 通用关闭与杂项
    # ========================================================================

    @staticmethod
    def click_close() -> None:
        """点击通用关闭按钮（关闭弹窗/页面）。"""
        auto.click_element(Img.CLICK_CLOSE, "image", Threshold.CLICK_CLOSE_MATCH)

    @staticmethod
    def click_continue() -> bool:
        """点击 continue 箭头推进对话。

        返回:
            True  点击成功
            False 未找到 continue 箭头
        """
        return auto.click_element(
            Img.CONTINUE, "image", Threshold.CONTINUE_MATCH,
            crop=Crop.DIALOG_CONTINUE,
        )

    @staticmethod
    def move_mouse_to_click_pos() -> None:
        """将鼠标移动到默认点击位置（底部中央），避免干扰后续匹配。"""
        auto.click_element(Crop.CLICK_POS, "crop", action="move")
