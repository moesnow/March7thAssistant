from dataclasses import dataclass
import re
import time

from module.automation import auto
from module.config import cfg
from module.logger import log
from module.notification.notification import NotificationLevel
from module.screen import screen
from tasks.base.base import Base
from utils.date import Date


@dataclass(frozen=True)
class EmberExchangeItem:
    display_name: str
    enable_key: str
    timestamp_key: str
    exchange_limit: int


class EmberExchange:
    FULL_SCREEN_CROP = (0, 0, 1, 1)
    MENU_TEXT_CROP = (1240 / 1920, 0, 680 / 1920, 1)
    ITEM_LIST_CROP = (120 / 1920, 120 / 1080, 1680 / 1920, 820 / 1080)
    EMBER_TAB_CROP = (571 / 1920, 110 / 1080, 186 / 1920, 42 / 1080)
    RETRY_SCROLL_CENTER_CROP = (955 / 1920, 535 / 1080, 10 / 1920, 10 / 1080)
    ITEM_INFO_WIDTH = 132 / 1920
    ITEM_INFO_HEIGHT = 204 / 1080
    PLUS_BUTTON_IMAGE = "./assets/images/share/ember_exchange/plus.png"
    PLUS_BUTTON_CROP = (860 / 1920, 500 / 1080, 560 / 1920, 240 / 1080)
    CONFIRM_BUTTON_CROP = (987 / 1920, 710 / 1080, 362 / 1920, 61 / 1080)
    SUCCESS_POPUP_CROP = (700 / 1920, 730 / 1080, 540 / 1920, 240 / 1080)
    SUCCESS_TEXTS = ("点击空白处关闭", "点击空白处")
    SOLD_OUT_TEXTS = ("已售馨", "已售罄")
    EXCHANGE_COUNT_PATTERN = re.compile(r"可兑换[:：]?\s*(\d+)\s*[/／]\s*(\d+)")
    RESULT_SUCCESS = "success"
    RESULT_RETRY = "retry"
    RESULT_FAILED = "failed"
    RESULT_SOLD_OUT = "sold_out"
    ACTION_PAUSE = 1.0
    ITEM_CLICK_PAUSE = 1.8
    QUANTITY_CLICK_PAUSE = 0.45
    BEFORE_CONFIRM_PAUSE = 0.9
    AFTER_CONFIRM_PAUSE = 1.5
    AFTER_CLOSE_PAUSE = 1.2
    DIALOG_TIMEOUT = 8
    POLL_PAUSE = 0.6
    RETRY_SCROLL_COUNT = 120
    ITEMS = (
        EmberExchangeItem("星轨专票", "asset_ember_special_pass_enable", "asset_ember_special_pass_timestamp", 5),
        EmberExchangeItem("星轨通票", "asset_ember_regular_pass_enable", "asset_ember_regular_pass_timestamp", 5),
        EmberExchangeItem("命运的足迹", "asset_ember_tracks_of_destiny_enable", "asset_ember_tracks_of_destiny_timestamp", 2),
    )

    @classmethod
    def start(cls):
        pending_items = []
        enabled_count = 0

        for item in cls.ITEMS:
            if not cfg.get_value(item.enable_key, False):
                log.info(f"每月自动购买「{item.display_name}」未开启")
                continue

            enabled_count += 1
            timestamp = float(cfg.get_value(item.timestamp_key, 0) or 0)
            if Date.is_next_month_x_am(timestamp, cfg.refresh_hour):
                pending_items.append(item)
            else:
                log.info(f"「{item.display_name}」自动购买尚未刷新")

        if enabled_count == 0:
            log.info("余烬兑换每月自动购买未开启")
            return False

        if not pending_items:
            log.info("余烬兑换每月自动购买尚未刷新")
            return True

        log.hr("准备进行余烬兑换每月购买", 2)
        has_success = False
        unresolved_items = []

        try:
            if not cls._navigate_to_ember_exchange():
                log.error("进入余烬兑换失败")
                return False

            for item in pending_items:
                result = cls._purchase_item(item)
                if result == cls.RESULT_RETRY:
                    unresolved_items.append(item)
                    continue

                if result not in {cls.RESULT_SUCCESS, cls.RESULT_SOLD_OUT}:
                    log.warning(f"「{item.display_name}」购买未完成，本次不记录时间")
                    continue

                cfg.save_timestamp(item.timestamp_key)
                has_success = True

            if unresolved_items:
                unresolved_names = "、".join(item.display_name for item in unresolved_items)
                log.info(f"检测到未命中商品：{unresolved_names}，准备下滚后补扫")
                if cls._scroll_to_bottom_for_retry():
                    for item in unresolved_items:
                        result = cls._purchase_item(item, accept_sold_out=True)
                        if result not in {cls.RESULT_SUCCESS, cls.RESULT_SOLD_OUT}:
                            log.warning(f"「{item.display_name}」下滚补扫后仍未完成，本次不记录时间")
                            continue

                        cfg.save_timestamp(item.timestamp_key)
                        has_success = True
        except Exception as e:
            log.error(f"余烬兑换每月自动购买失败: {e}")
        finally:
            cls._restore_main_screen()

        return has_success

    @classmethod
    def _navigate_to_ember_exchange(cls):
        if not cls._return_to_known_screen():
            return False

        if screen.current_screen != "menu":
            screen.change_to("menu")
            time.sleep(1)

        if not cls._click_text_and_wait("商店", "兑换商店", click_crop=cls.MENU_TEXT_CROP):
            log.error("从手机菜单进入商店失败")
            return False

        if not cls._click_text_and_wait("兑换商店", "余烬兑换"):
            log.error("进入兑换商店失败")
            return False

        if not cls._select_ember_exchange_tab():
            log.error("进入余烬兑换失败")
            return False

        time.sleep(cls.ITEM_CLICK_PAUSE)
        return True

    @classmethod
    def _purchase_item(cls, item: EmberExchangeItem, accept_sold_out=False):
        item_entry = cls._find_purchasable_item(item, accept_sold_out=accept_sold_out)
        if not item_entry:
            return cls.RESULT_FAILED if accept_sold_out else cls.RESULT_RETRY

        if item_entry.get("status") == cls.RESULT_SOLD_OUT:
            log.info(f"「{item.display_name}」已售罄，本月视为已处理")
            return cls.RESULT_SOLD_OUT

        log.info(f"尝试购买「{item.display_name}」")

        if not auto.click_element_with_pos(item_entry["absolute_box"]):
            log.warning(f"点击「{item.display_name}」失败")
            return cls.RESULT_FAILED

        time.sleep(cls.ITEM_CLICK_PAUSE)
        if not cls._wait_for_purchase_dialog():
            log.warning(f"未进入「{item.display_name}」购买界面")
            cls._close_current_dialog()
            return cls.RESULT_FAILED

        if not cls._increase_purchase_quantity(item.display_name, item_entry["remaining_count"]):
            cls._close_current_dialog()
            return cls.RESULT_FAILED

        time.sleep(cls.BEFORE_CONFIRM_PAUSE)

        if not auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.88, max_retries=6, crop=cls.CONFIRM_BUTTON_CROP, retry_delay=0.8):
            if not auto.click_element("确认", "text", max_retries=6, crop=cls.CONFIRM_BUTTON_CROP, include=True, retry_delay=0.8):
                log.warning(f"未找到「{item.display_name}」购买界面的确认按钮")
                cls._close_current_dialog()
                return cls.RESULT_FAILED

        time.sleep(cls.AFTER_CONFIRM_PAUSE)

        if not cls._close_success_popup(item.display_name):
            log.warning(f"未检测到「{item.display_name}」购买成功弹窗")
            cls._close_current_dialog()
            return cls.RESULT_FAILED

        log.info(f"「{item.display_name}」购买完成")
        return cls.RESULT_SUCCESS

    @classmethod
    def _select_ember_exchange_tab(cls):
        for _ in range(5):
            if auto.is_rgb_ratio_above_threshold(cls.EMBER_TAB_CROP, (224, 224, 225), 0.7, tolerance=0.01):
                return True

            auto.click_element(cls.EMBER_TAB_CROP, "crop")
            time.sleep(0.8)

            if auto.is_rgb_ratio_above_threshold(cls.EMBER_TAB_CROP, (224, 224, 225), 0.7, tolerance=0.01):
                return True

        return False

    @classmethod
    def _find_purchasable_item(cls, item: EmberExchangeItem, accept_sold_out=False):
        auto.take_screenshot(cls.FULL_SCREEN_CROP)
        auto.perform_ocr()

        for box, (text, confidence) in auto.ocr_result:
            if item.display_name not in text:
                continue

            absolute_box = auto.calculate_text_position(box, False)
            relative_box = auto.calculate_text_position(box, True)
            log.debug(f"找到「{item.display_name}」文字：{text} 相似度：{confidence:.2f}")

            item_info = cls._inspect_item_info(item, relative_box, accept_sold_out=accept_sold_out)
            if not item_info:
                continue

            item_info["absolute_box"] = absolute_box
            return item_info

        log.warning(f"未找到符合购买条件的「{item.display_name}」")
        return None

    @classmethod
    def _inspect_item_info(cls, item: EmberExchangeItem, relative_box, accept_sold_out=False):
        info_crop = cls._build_item_info_crop(relative_box)
        auto.take_screenshot(info_crop)
        auto.perform_ocr()

        texts = cls._collect_ordered_texts(auto.ocr_result)
        merged_text = "\n".join(text.strip() for text in texts if text)
        sold_out_detected = any(any(target in text for target in cls.SOLD_OUT_TEXTS) for text in texts)

        if not any("超值" in text for text in texts) and not sold_out_detected:
            log.info(f"「{item.display_name}」上方区域未识别到“超值”，跳过")
            return None

        matched = cls._extract_exchange_count_match(texts)
        if not matched:
            if accept_sold_out and sold_out_detected:
                log.info(f"「{item.display_name}」未识别到可兑换数量，但识别到已售罄，视为本月已处理")
                return {"status": cls.RESULT_SOLD_OUT}
            log.info(f"「{item.display_name}」上方区域未识别到可兑换数量，OCR结果：{merged_text or '空'}")
            return None

        remaining_count = int(matched.group(1))
        total_count = int(matched.group(2))
        log.info(f"检测到「{item.display_name}」可兑换：{remaining_count}/{total_count}")

        if total_count != item.exchange_limit:
            log.info(f"「{item.display_name}」识别到的上限为 {total_count}，预期为 {item.exchange_limit}，跳过")
            return None

        if remaining_count <= 0:
            log.info(f"「{item.display_name}」当前可兑换数量为 0，跳过")
            return None

        return {
            "status": cls.RESULT_SUCCESS,
            "remaining_count": remaining_count,
            "total_count": total_count,
        }

    @classmethod
    def _extract_exchange_count_match(cls, texts):
        normalized_texts = [text.replace(" ", "") for text in texts if text]

        for text in normalized_texts:
            if matched := cls.EXCHANGE_COUNT_PATTERN.search(text):
                return matched

        merged_text = "\n".join(normalized_texts)
        return cls.EXCHANGE_COUNT_PATTERN.search(merged_text)

    @classmethod
    def _build_item_info_crop(cls, relative_box):
        screen_width = max(auto.screenshot.width, 1)
        screen_height = max(auto.screenshot.height, 1)
        top_left, bottom_right = relative_box
        anchor_x = ((top_left[0] + bottom_right[0]) / 2) / screen_width
        anchor_y = top_left[1] / screen_height

        crop_x = max(0.0, anchor_x - cls.ITEM_INFO_WIDTH)
        crop_y = max(0.0, anchor_y - cls.ITEM_INFO_HEIGHT)

        if crop_x + cls.ITEM_INFO_WIDTH > 1:
            crop_x = max(0.0, 1 - cls.ITEM_INFO_WIDTH)
        if crop_y + cls.ITEM_INFO_HEIGHT > 1:
            crop_y = max(0.0, 1 - cls.ITEM_INFO_HEIGHT)

        return crop_x, crop_y, cls.ITEM_INFO_WIDTH, cls.ITEM_INFO_HEIGHT

    @staticmethod
    def _collect_ordered_texts(ocr_results):
        ordered_results = sorted(
            ocr_results,
            key=lambda item: (
                min(point[1] for point in item[0]),
                min(point[0] for point in item[0]),
            ),
        )
        return [text for _, (text, _) in ordered_results if text]

    @classmethod
    def _wait_for_purchase_dialog(cls):
        end_time = time.time() + cls.DIALOG_TIMEOUT
        while time.time() < end_time:
            if auto.find_element("./assets/images/zh_CN/base/confirm.png", "image", 0.88, max_retries=1, crop=cls.CONFIRM_BUTTON_CROP):
                return True
            if auto.find_element("确认", "text", max_retries=1, crop=cls.CONFIRM_BUTTON_CROP, include=True):
                return True
            time.sleep(cls.POLL_PAUSE)
        return False

    @classmethod
    def _increase_purchase_quantity(cls, item_name, remaining_count):
        if remaining_count <= 1:
            return True

        plus_clicks = remaining_count - 1
        log.info(f"「{item_name}」需要点击加号 {plus_clicks} 次")

        for index in range(plus_clicks):
            if not auto.click_element(cls.PLUS_BUTTON_IMAGE, "image", 0.85, max_retries=6, crop=cls.PLUS_BUTTON_CROP, retry_delay=0.3):
                log.warning(f"「{item_name}」第 {index + 1} 次点击加号失败")
                return False
            time.sleep(cls.QUANTITY_CLICK_PAUSE)

        return True

    @classmethod
    def _click_text_and_wait(cls, click_target, wait_target, click_crop=None, wait_crop=None, timeout=8):
        if not auto.click_element(
            click_target,
            "text",
            max_retries=8,
            crop=click_crop or cls.FULL_SCREEN_CROP,
            include=True,
            retry_delay=0.8,
        ):
            return False

        time.sleep(cls.ITEM_CLICK_PAUSE)
        return cls._wait_for_text(wait_target, crop=wait_crop or cls.FULL_SCREEN_CROP, timeout=timeout)

    @classmethod
    def _wait_for_text(cls, targets, crop=None, timeout=8):
        end_time = time.time() + timeout
        while time.time() < end_time:
            if auto.find_element(targets, "text", crop=crop or cls.FULL_SCREEN_CROP, include=True):
                return True
            time.sleep(cls.POLL_PAUSE)
        return False

    @classmethod
    def _close_success_popup(cls, item_name):
        end_time = time.time() + 8
        while time.time() < end_time:
            if coordinates := auto.find_element("./assets/images/zh_CN/base/click_close.png", "image", 0.8, max_retries=1, crop=cls.SUCCESS_POPUP_CROP):
                screenshot, _, _ = auto.take_screenshot(cls.FULL_SCREEN_CROP)
                Base.send_notification_with_screenshot(f"余烬兑换购买成功：{item_name}", NotificationLevel.ALL, screenshot)
                time.sleep(cls.ACTION_PAUSE)
                auto.click_element_with_pos(coordinates)
                time.sleep(cls.AFTER_CLOSE_PAUSE)
                return True
            if coordinates := auto.find_element(cls.SUCCESS_TEXTS, "text", max_retries=1, crop=cls.SUCCESS_POPUP_CROP, include=True):
                screenshot, _, _ = auto.take_screenshot(cls.FULL_SCREEN_CROP)
                Base.send_notification_with_screenshot(f"余烬兑换购买成功：{item_name}", NotificationLevel.ALL, screenshot)
                time.sleep(cls.ACTION_PAUSE)
                auto.click_element_with_pos(coordinates)
                time.sleep(cls.AFTER_CLOSE_PAUSE)
                return True
            time.sleep(cls.POLL_PAUSE)
        return False

    @classmethod
    def _scroll_to_bottom_for_retry(cls):
        try:
            auto.click_element(cls.RETRY_SCROLL_CENTER_CROP, "crop", action="move")
            time.sleep(cls.ACTION_PAUSE)
            auto.mouse_scroll(cls.RETRY_SCROLL_COUNT, -1, False)
            time.sleep(cls.ITEM_CLICK_PAUSE)
            return True
        except Exception as e:
            log.warning(f"余烬兑换下滚补扫失败: {e}")
            return False

    @staticmethod
    def _close_current_dialog():
        auto.press_key("esc")
        time.sleep(1.2)

    @classmethod
    def _return_to_known_screen(cls):
        for _ in range(6):
            if screen.get_current_screen(autotry=False, max_retries=1) and screen.current_screen in {"main", "menu"}:
                return True
            auto.press_key("esc")
            time.sleep(1.2)
        log.warning("未能回到可识别界面，无法继续执行余烬兑换")
        return False

    @classmethod
    def _restore_main_screen(cls):
        if not cls._return_to_known_screen():
            log.warning("余烬兑换结束后未能回到主界面，请检查当前游戏画面")
            return False

        if screen.current_screen == "menu":
            try:
                screen.change_to("main")
            except Exception as e:
                log.warning(f"余烬兑换结束后返回主界面失败: {e}")
                return False
        return True
