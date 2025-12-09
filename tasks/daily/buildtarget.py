import cv2
import numpy as np
from module.screen import screen
from module.automation import auto
from module.logger import log
from module.config import cfg
from module.notification.notification import NotificationLevel
from tasks.base.base import Base
from utils.image_utils import ImageUtils
import json
import time
import datetime
import re


class BuildTarget:
    _initialized = False
    _build_target_name = None
    _target_instances = []
    _valid_instance_names = {}

    @staticmethod
    def get_target_instance() -> tuple[str, str] | None:
        """尝试获取培养目标普通副本信息"""
        if not BuildTarget._initialized:
            BuildTarget.init_build_targets()

        require_ornament = datetime.date.today().weekday() >= (7 - cfg.build_target_ornament_weekly_count)

        for instance_type, instance_name in BuildTarget._target_instances:
            if "历战余响" in instance_type:
                continue
            if not require_ornament:
                return (instance_type, instance_name)
            if "饰品提取" in instance_type:
                return (instance_type, instance_name)

        return None

    @staticmethod
    def get_target_echo_instance() -> tuple[str, str] | None:
        """尝试获取培养目标历战余响副本信息"""
        if not BuildTarget._initialized:
            BuildTarget.init_build_targets()

        for instance_type, instance_name in BuildTarget._target_instances:
            if "历战余响" in instance_type:
                return (instance_type, instance_name)

        return None

    @staticmethod
    def get_target_instances() -> list[tuple[str, str]]:
        """尝试获取培养目标所有待刷副本信息"""
        if not BuildTarget._initialized:
            BuildTarget.init_build_targets()

        return BuildTarget._target_instances

    @staticmethod
    def init_build_targets():
        BuildTarget._initialized = True
        BuildTarget._build_target_name = None
        BuildTarget._target_instances = []

        log.hr("开始获取培养目标")

        screenshot = None
        instances = []

        if BuildTarget._enter_build_target_page():
            # 提前截图培养目标界面
            auto.take_screenshot()
            screenshot = auto.screenshot

            instances = BuildTarget._get_target_instances_all()
            # instances = BuildTarget._get_target_instances_by_fixed_strategy()

            for instance in instances:
                if BuildTarget._is_valid_instance(instance):
                    log.debug(f"副本名称 {instance} 检验通过，加入目标列表")
                    BuildTarget._target_instances.append(instance)
                else:
                    log.warning(f"目标副本识别错误，{instance} 不在任何已知副本列表中")

        if BuildTarget._target_instances:
            message = f"培养目标{BuildTarget._build_target_name or 'None'}的待刷副本: \n{'\n'.join(f'{k} - {v}' for k, v in BuildTarget._target_instances)}"
            Base.send_notification_with_screenshot(message, NotificationLevel.ALL, screenshot)
        else:
            Base.send_notification_with_screenshot("未能获取到任何培养目标副本信息，回退至默认的设置", NotificationLevel.ALL)

    @staticmethod
    def _enter_build_target_page():
        screen.change_to("guide3")

        if not auto.click_element("培养目标", "text", max_retries=5, crop=(300.0 / 1920, 291.0 / 1080, 147.0 / 1920, 104.0 / 1080)):
            log.error("未能识别培养目标入口")
            return False

        if len(auto.ocr_result) == 2:
            try:
                BuildTarget._build_target_name = auto.ocr_result[1][1][0]
            except:
                pass

        if not auto.click_element("./assets/images/screen/guide/power.png", "image", 0.7, max_retries=5, crop=(688.0 / 1920, 286.0 / 1080, 969.0 / 1920, 676.0 / 1080)):
            log.warning("未检测到任何可进入的培养目标副本")
            return False

        return True

    @staticmethod
    def _get_target_instances_by_fixed_strategy():
        entry_patterns = []
        targets = []

        if not auto.find_element("./assets/images/share/build_target/resources_sufficient_icon.png", "image", 0.7, take_screenshot=False):
            entry_patterns.append(("进入", "./assets/images/share/build_target/traces_icon.png", "bottom_right"))
            if auto.find_element("奖励次数", "text", include=True, crop=(1388.0 / 1920, 390.0 / 1080, 252.0 / 1920, 488.0 / 1080)):
                if not any(map(lambda box: "0/3" in box[1][0], auto.ocr_result)):
                    entry_patterns.append(("进入", "./assets/images/share/build_target/reward_count_label.png", "bottom_left"))
        else:
            if datetime.date.today().weekday() >= (7 - cfg.build_target_ornament_weekly_count):
                entry_patterns.append(("传送", "./assets/images/share/build_target/ornament_icon.png", "bottom_right"))
            else:
                entry_patterns.append(("进入", "./assets/images/share/build_target/relic_icon.png", "bottom_right"))

        log.warning(f"使用固定策略查找: {entry_patterns}")

        for pattern in entry_patterns:
            enter_target, enter_source, direction = pattern

            for _ in range(5):
                enter_pos = auto.find_element(
                    enter_target,
                    "min_distance_text",
                    crop=(688.0 / 1920, 286.0 / 1080, 969.0 / 1920, 676.0 / 1080),
                    source=enter_source,
                    source_type="image",
                    position=direction,
                )
                if not enter_pos:
                    auto.mouse_scroll(6, -1)
                    time.sleep(1)
                else:
                    break

            if not enter_pos or not auto.click_element_with_pos(enter_pos):
                break

            if target_instance := BuildTarget._get_instance_info():
                instance_type, instance_name = target_instance
                targets.append((instance_type, instance_name))
                if not BuildTarget._exit_instance(instance_type):
                    log.warning("由于流程错误，终止获取培养目标副本信息，返回当前已获取列表")
                    return targets

        return targets

    @staticmethod
    def _get_target_instances_all():
        target_instances = []

        anchor_template = None
        paging_boundary_y = 0

        page_crop = (688.0 / 1920, 286.0 / 1080, 969.0 / 1920, 676.0 / 1080)
        auto.take_screenshot(crop=page_crop)

        for _ in range(5):
            enter_positions = []

            if anchor_template is not None:
                for _ in range(3):
                    auto.take_screenshot(page_crop)
                    screenshot = cv2.cvtColor(np.array(auto.screenshot), cv2.COLOR_BGR2RGB)
                    match_val, match_loc = ImageUtils.scale_and_match_template(screenshot, anchor_template, 0.8, None)
                    if match_val > 0.95:
                        paging_boundary_y = match_loc[1] + 64
                        break
                    else:
                        auto.mouse_scroll(2, 1)
                        time.sleep(1)
                else:
                    log.error("滚动锚点跟踪失败")
                    break

            auto.perform_ocr()
            for box, (text, _) in auto.ocr_result:
                match, _ = auto.is_text_match(text, ["进入", "传送"], True)
                if match and box[0][1] > paging_boundary_y:
                    enter_positions.append(auto.calculate_text_position(box, True))

            if not enter_positions:
                log.info("查找结束，未找到更多可进入副本")
                break

            screenshot_left, screenshot_top, _, _ = auto.screenshot_pos

            for pos in enter_positions:
                x1, y1 = screenshot_left + pos[0][0], screenshot_top + pos[0][1]
                x2, y2 = screenshot_left + pos[1][0], screenshot_top + pos[1][1]

                if not auto.click_element_with_pos(((x1, y1), (x2, y2))):
                    log.error("尝试进入培养目标副本时失败")
                    return target_instances

                if instance := BuildTarget._get_instance_info():
                    log.debug(f"识别到副本信息: {instance}")

                    target_instances.append(instance)
                    instance_type, _ = instance

                    if not BuildTarget._exit_instance(instance_type):
                        log.error("由于流程错误，终止获取培养目标副本信息，返回当前已获取列表")
                        return target_instances

                    if "饰品提取" in instance_type:
                        return target_instances

                else:
                    log.warning("未能识别到副本信息")

            last_enter_pos = enter_positions[-1]
            anchor_crop_height = (last_enter_pos[1][1] - last_enter_pos[0][1]) * auto.screenshot_scale_factor / 1080.0
            anchor_crop_top = page_crop[1] + last_enter_pos[0][1] * auto.screenshot_scale_factor / 1080.0
            anchor_crop = (page_crop[0], anchor_crop_top, page_crop[2], anchor_crop_height)
            anchor_template, _, _ = auto.take_screenshot(anchor_crop)
            anchor_template = cv2.cvtColor(np.array(anchor_template.copy()), cv2.COLOR_RGB2BGR)

            auto.mouse_scroll(12)
            time.sleep(1)

        return target_instances

    @staticmethod
    def _exit_instance(instance_type):
        auto.press_key("esc")

        if "饰品提取" in instance_type:
            time.sleep(0.5)
            auto.press_key("esc")
            return True

        if "拟造花萼" in instance_type:
            time.sleep(0.5)
            auto.press_key("esc")

        # 防止“新难度等级解锁”弹窗阻碍返回
        for _ in range(2):
            if auto.find_element(["进入", "传送"], "text", max_retries=4, retry_delay=0.5, crop=(688.0 / 1920, 286.0 / 1080, 969.0 / 1920, 676.0 / 1080)):
                return True
            else:
                log.debug("由于未知原因，未能返回培养目标副本列表页面，进行重试")
                auto.press_key("esc")
        else:
            log.warning("由于未知原因，未能返回培养目标副本列表页面")
            return False

    @staticmethod
    def _get_instance_info() -> tuple[str, str] | None:
        if not auto.find_element(["挑战", "开始挑战"], "text", max_retries=10, crop=(1520.0 / 1920, 933.0 / 1080, 390.0 / 1920, 111.0 / 1080)):
            log.error("尝试进入培养目标副本时失败")
            return None

        instance_type = auto.get_single_line_text(max_retries=5, retry_delay=1.0, crop=(93.0 / 1920, 33.0 / 1080, 150.0 / 1920, 68.0 / 1080))

        if "饰品提取" in instance_type:
            instance_type = "饰品提取"
            instance_name = BuildTarget._parse_ornament_instance_info()
        elif "拟造花萼" in instance_type:
            instance_type = "拟造花萼（赤）"
            instance_name = BuildTarget._parse_calyx_instance_info()
        else:
            instance_name = BuildTarget._parse_standard_instance_info()

        instance_type = (instance_type or "").strip()
        instance_name = (instance_name or "").strip()

        if instance_type and instance_name:
            return (instance_type, instance_name)

        log.warning("未能识别到副本信息")
        return None

    @staticmethod
    def _parse_ornament_instance_info() -> str | None:
        return auto.get_single_line_text(max_retries=5, retry_delay=1.0, crop=(584.0 / 1920, 112.0 / 1080, 614.0 / 1920, 52.0 / 1080))

    @staticmethod
    def _parse_calyx_instance_info() -> str | None:
        for i in range(2):
            click_offset = (i * 88 / auto.screenshot_scale_factor, 64 / auto.screenshot_scale_factor)
            if not auto.click_element("可能获取", "text", offset=click_offset, max_retries=5, crop=(1196.0 / 1920, 492.0 / 1080, 705.0 / 1920, 456.0 / 1080)):
                log.error("尝试提取拟造花萼副本信息时失败，无法识别特定副本页面")
                return None

            item_name = auto.get_single_line_text(crop=(783.0 / 1920, 318.0 / 1080, 204.0 / 1920, 55.0 / 1080), max_retries=3, retry_delay=0.5)
            if not item_name or "信用点" in item_name:
                log.error("尝试提取拟造花萼副本信息时失败，无法获取光锥晋阶材料信息")
                return None

            auto.mouse_scroll(6, -1)
            time.sleep(1)

            text_crop = (790.0 / 1920, 377.0 / 1080, 694.0 / 1920, 354.0 / 1080)
            text_pos = auto.find_element("拟造花萼", "text", crop=text_crop, include=True, relative=True)

            if text_pos:
                text_pos = tuple((x * auto.screenshot_scale_factor, y * auto.screenshot_scale_factor) for (x, y) in text_pos)
                x1, y1 = text_crop[0] + (text_pos[0][0] - 12) / 1920, text_crop[1] + (text_pos[0][1] - 12) / 1080
                x2, y2 = text_crop[0] + (text_pos[1][0] + 12) / 1920, text_crop[1] + (text_pos[1][1] + 12) / 1080
                instance_name_match = re.search(r"[【（\(](.+?)[】）\)]", auto.get_single_line_text(crop=(x1, y1, x2 - x1, y2 - y1)) or "")
                if instance_name_match:
                    return instance_name_match.group(1)

            auto.press_key("esc")
            time.sleep(1)

        return None

    @staticmethod
    def _parse_standard_instance_info() -> str | None:
        raw_instance_name = auto.get_single_line_text(max_retries=5, retry_delay=1.0, crop=(1173.0 / 1920, 113.0 / 1080, 735.0 / 1920, 53.0 / 1080))

        if "·" in raw_instance_name:
            return raw_instance_name.split("·")[0]

        return None

    @staticmethod
    def _is_valid_instance(instance):
        instance_type, instance_name = instance

        if not BuildTarget._valid_instance_names:
            with open("./assets/config/instance_names.json", "r", encoding="utf-8") as f:
                BuildTarget._valid_instance_names = json.load(f)

        if not instance_type or not instance_name:
            return False

        if BuildTarget._valid_instance_names.get(instance_type):
            if BuildTarget._valid_instance_names[instance_type].get(instance_name):
                return True

        return False
