from dataclasses import dataclass
import re
import time

from module.automation import auto
from module.config import cfg
from module.logger import log
from module.notification.notification import NotificationLevel
from module.screen import screen
from tasks.base.base import Base
from tasks.base.list_drag import drag_to_edge
from tasks.base.task_steps import FATAL_GAME_ERRORS
from module.overview.plan import EMBER_ITEMS, ember_due
from utils.date import Date  # 与现有调用方共用的刷新时钟
from utils.pause import pause_ctl
from utils.wait import wait_until


@dataclass(frozen=True)
class EmberExchangeItem:
    display_name: str
    enable_key: str
    timestamp_key: str
    exchange_limit: int


class EmberExchange:
    FULL_SCREEN_CROP = (0, 0, 1, 1)
    MENU_TEXT_CROP = (1240 / 1920, 0, 680 / 1920, 1)
    SHOP_HEADER_CROP = (0, 0, 550 / 1920, 116 / 1080)
    SHOP_MENU_CROP = (0, 0, 550 / 1920, 1)
    SHOP_ENTRY_TEXTS = ("兑换商店", "常驻商店")
    SHOP_ENTRY_ATTEMPTS = 3
    ITEM_LIST_CROP = (120 / 1920, 120 / 1080, 1680 / 1920, 820 / 1080)
    EMBER_TABS_CROP = (460 / 1920, 98 / 1080, 331 / 1920, 109 / 1080)
    LEGACY_EMBER_TAB_CROP = (571 / 1920, 110 / 1080, 186 / 1920, 42 / 1080)
    UNDERLINED_EMBER_TAB_IMAGE = "./assets/images/zh_CN/ember_exchange/underlined_tab.png"
    UNDERLINED_EMBER_TAB_CROP = (460 / 1920, 132 / 1080, 253 / 1920, 76 / 1080)
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
    ITEMS = tuple(EmberExchangeItem(name, base + "_enable", base + "_timestamp", limit)
                  for name, base, limit in EMBER_ITEMS)

    @classmethod
    def start(cls):
        pending_items = []
        enabled_count = 0

        for item in cls.ITEMS:
            if not cfg.get_value(item.enable_key, False):
                log.info(f"每月自动购买「{item.display_name}」未开启")
                continue

            enabled_count += 1
            if ember_due(cfg, item.timestamp_key):
                pending_items.append(item)
            else:
                log.info(f"「{item.display_name}」自动购买尚未刷新")

        if enabled_count == 0:
            log.info("余烬兑换每月自动购买未开启")
            return True

        if not pending_items:
            log.info("余烬兑换每月自动购买尚未刷新")
            return True

        log.hr("准备进行余烬兑换每月购买", 2)
        completed_count = 0
        unresolved_items = []

        try:
            if not cls._navigate_to_ember_exchange():
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
                completed_count += 1

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
                        completed_count += 1
        except Exception as e:
            log.error(f"余烬兑换每月自动购买失败: {e}")
            return False
        finally:
            pause_ctl.check_stop()
            cls._restore_main_screen()

        return completed_count == len(pending_items)

    @classmethod
    def _navigate_to_ember_exchange(cls):
        if not cls._open_shop():
            log.warning("多次尝试后仍未能从手机菜单进入商店")
            return False

        if not cls._click_text_and_wait("常驻商店", "兑换商店", cls.SHOP_HEADER_CROP, cls.SHOP_MENU_CROP):
            log.warning("多次尝试后仍未找到兑换商店入口")
            return False
        if not cls._click_text_and_wait("兑换商店", "余烬兑换", cls.SHOP_MENU_CROP, cls.EMBER_TABS_CROP):
            log.warning("多次尝试后仍未找到余烬兑换标签")
            return False

        if not cls._select_ember_exchange_tab():
            log.warning("多次尝试后仍未确认余烬兑换标签已选中")
            return False

        time.sleep(cls.ITEM_CLICK_PAUSE)
        return True

    @classmethod
    def _open_shop(cls):
        for _ in range(cls.SHOP_ENTRY_ATTEMPTS):
            if not cls._return_to_known_screen():
                return False
            if screen.current_screen == "main":
                auto.press_key("esc")
                if not wait_until(lambda: screen.check_screen("menu"), cls.DIALOG_TIMEOUT, cls.POLL_PAUSE):
                    continue

            shop = cls._find_shop_text("商店", cls.MENU_TEXT_CROP, max_retries=3)
            if not shop:
                continue

            auto.click_element_with_pos(shop)
            if cls._wait_for_text(cls.SHOP_ENTRY_TEXTS, cls.SHOP_MENU_CROP):
                return True
            if cls._check_known_screen():
                continue

            log.info("尚未看到商店，尝试按 ESC 关闭入口动画")
            auto.press_key("esc")
            if cls._wait_for_text(cls.SHOP_ENTRY_TEXTS, cls.SHOP_MENU_CROP):
                return True
        return False

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
            if cls._ember_tab_selected():
                return True

            if tab := cls._find_shop_text("余烬兑换", cls.EMBER_TABS_CROP):
                auto.click_element_with_pos(tab)
            time.sleep(0.8)
        return cls._ember_tab_selected()

    @classmethod
    def _ember_tab_selected(cls):
        # 新版标签有下划线，旧版标签用灰白底高亮。
        try:
            if auto.find_element(cls.UNDERLINED_EMBER_TAB_IMAGE, "image", 0.92, crop=cls.UNDERLINED_EMBER_TAB_CROP):
                return True
            return auto.is_rgb_ratio_above_threshold(cls.LEGACY_EMBER_TAB_CROP, (224, 224, 225), 0.7, tolerance=0.01)
        except FATAL_GAME_ERRORS:
            raise
        except RuntimeError as error:
            log.debug(f"暂时无法确认余烬兑换标签：{error}")
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
            log.info(f"「{item.display_name}」当前可兑换数量为 0，本月视为已处理")
            return {"status": cls.RESULT_SOLD_OUT}

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
    def _click_text_and_wait(cls, click_target, wait_target, click_crop, wait_crop):
        for _ in range(cls.SHOP_ENTRY_ATTEMPTS):
            if cls._find_shop_text(wait_target, wait_crop):
                return True
            if position := cls._find_shop_text(click_target, click_crop):
                auto.click_element_with_pos(position)
                if cls._wait_for_text(wait_target, wait_crop):
                    return True
            else:
                time.sleep(cls.POLL_PAUSE)
        return False

    @classmethod
    def _wait_for_text(cls, targets, crop):
        return wait_until(lambda: cls._find_shop_text(targets, crop), cls.DIALOG_TIMEOUT, cls.POLL_PAUSE)

    @classmethod
    def _find_shop_text(cls, targets, crop, *, max_retries=1):
        try:
            return auto.find_element(targets, "text", crop=crop, include=True,
                                     max_retries=max_retries, retry_delay=cls.POLL_PAUSE)
        except FATAL_GAME_ERRORS:
            raise
        except RuntimeError as error:
            log.debug(f"读取商店文字时画面暂时不可用：{error}")
            return None

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
            time.sleep(cls.ACTION_PAUSE)
            completed = drag_to_edge(auto, (550 / 1920, 850 / 1080), (550 / 1920, 350 / 1080),
                                     crop=(320 / 1920, 175 / 1080, 1420 / 1920, 755 / 1080), max_drags=12, duration=1.2)
            time.sleep(cls.ITEM_CLICK_PAUSE)
            return completed
        except Exception as e:
            log.warning(f"余烬兑换下滚补扫失败: {e}")
            return False

    @staticmethod
    def _close_current_dialog():
        auto.press_key("esc")
        time.sleep(1.2)

    @staticmethod
    def _check_known_screen():
        auto.take_screenshot()
        return screen.check_screen("menu", take_screenshot=False) or screen.check_screen("main", take_screenshot=False)

    @classmethod
    def _return_to_known_screen(cls):
        for _ in range(6):
            if cls._check_known_screen():
                return True
            auto.press_key("esc")
            time.sleep(1.2)
        return cls._check_known_screen()

    @classmethod
    def _restore_main_screen(cls):
        try:
            if not cls._return_to_known_screen():
                log.warning("余烬兑换结束后未能回到主界面，请检查当前游戏画面")
                return False
            if screen.current_screen == "menu":
                screen.change_to("main")
        except Exception as e:
            log.warning(f"余烬兑换结束后返回主界面失败: {e}")
            return False
        return True
