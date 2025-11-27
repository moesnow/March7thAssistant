from module.screen import screen
from module.automation import auto
from module.logger import log
from module.config import cfg
from tasks.base.base import Base
import json
import time
import datetime
import re


class BuildTarget:
    _initialized = False
    _target_instances = []
    _template_instance_names = {}

    @staticmethod
    def get_target_instance() -> tuple[str, str] | None:
        if not BuildTarget._initialized:
            BuildTarget.init_build_targets()

        for instance_type, instance_name in BuildTarget._target_instances:
            if "历战余响" not in instance_type:
                return (instance_type, instance_name)

        return None

    @staticmethod
    def get_target_echo_instance() -> tuple[str, str] | None:
        if not BuildTarget._initialized:
            BuildTarget.init_build_targets()

        for instance_type, instance_name in BuildTarget._target_instances:
            if "历战余响" in instance_type:
                return (instance_type, instance_name)

        return None

    @staticmethod
    def init_build_targets():
        BuildTarget._initialized = True
        BuildTarget._target_instances = []

        log.hr("开始获取培养目标")
        instances = BuildTarget._get_build_targets()

        for instance in instances:
            if BuildTarget._is_valid_instance(instance):
                log.debug(f"副本名称 {instance} 检验通过，加入目标列表")
                BuildTarget._target_instances.append(instance)
            else:
                log.warning(f"目标副本识别错误，{instance} 不在任何已知副本列表中")

        if BuildTarget._target_instances:
            Base.send_notification_with_screenshot(f"成功识别到培养目标，计划刷取: {', '.join(f'{k} - {v}' for k,v in BuildTarget._target_instances)}")
        else:
            Base.send_notification_with_screenshot("未能获取到培养目标，回退至默认的设置")

    @staticmethod
    def _get_build_targets():
        screen.change_to("guide3")

        entry_patterns = []
        targets = []

        if not auto.click_element("培养目标", "text", max_retries=5, crop=(300.0 / 1920, 291.0 / 1080, 147.0 / 1920, 104.0 / 1080)):
            log.error("未能识别培养目标入口")
            return targets

        if not auto.click_element("./assets/images/screen/guide/power.png", "image", 0.7, max_retries=5, crop=(688.0 / 1920, 286.0 / 1080, 969.0 / 1920, 676.0 / 1080)):
            log.warning("未检测到任何可进入的培养目标副本")
            return targets

        if not auto.find_element("./assets/images/share/build_target/resources_sufficient_icon.png", "image", 0.7, take_screenshot=False):
            entry_patterns.append(("进入", "./assets/images/share/build_target/traces_icon.png", "bottom_right"))
            if auto.find_element("奖励次数", "text", include=True, crop=(1388.0 / 1920, 390.0 / 1080, 252.0 / 1920, 488.0 / 1080)):
                if not any(map(lambda box: "0/3" in box[1][0], auto.ocr_result)):
                    entry_patterns.append(("进入", "./assets/images/share/build_target/reward_count_label.png", "bottom_left"))
        else:
            if datetime.date.today().weekday() >= 7 - cfg.build_target_ornament_weekly_count:
                entry_patterns.append(("传送", "./assets/images/share/build_target/ornament_icon.png", "bottom_right"))
            else:
                entry_patterns.append(("进入", "./assets/images/share/build_target/relic_icon.png", "bottom_right"))

        log.debug(f"计划查找副本: {entry_patterns}")

        for pattern in entry_patterns:
            if not BuildTarget._enter_instance(pattern):
                break
            if target_instance := BuildTarget._get_instance_info():
                instance_type, instance_name = target_instance
                targets.append((instance_type, instance_name))
                BuildTarget._exit_instance(instance_type)

        return targets

    @staticmethod
    def _enter_instance(pattern: tuple[str, str, str]):
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
            return False

        return True

    @staticmethod
    def _exit_instance(instance_type):
        is_deep_menu = any(keyword in instance_type for keyword in ["拟造花萼", "饰品提取"])
        steps = 2 if is_deep_menu else 1
        for _ in range(steps):
            auto.press_key("esc")
            time.sleep(1)

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
        click_offset = (0, -280 / auto.screenshot_scale_factor)
        if not auto.click_element("./assets/images/share/build_target/power.png", "image", max_retries=5, offset=click_offset, crop=(1223.0 / 1920, 961.0 / 1080, 93.0 / 1920, 44.0 / 1080)):
            log.error("尝试提取拟造花萼副本信息时失败")
            return None

        time.sleep(1)
        auto.mouse_scroll(6, -1)
        time.sleep(1)

        text_crop = (790.0 / 1920, 377.0 / 1080, 694.0 / 1920, 354.0 / 1080)
        text_pos = auto.find_element("拟造花萼", "text", crop=text_crop, include=True, relative=True)

        if text_pos:
            text_pos = tuple((x * auto.screenshot_scale_factor, y * auto.screenshot_scale_factor) for (x, y) in text_pos)
            x1, y1 = text_crop[0] + (text_pos[0][0] + 100) / 1920, text_crop[1] + (text_pos[0][1] - 6) / 1080
            x2, y2 = text_crop[0] + (text_pos[1][0] + 64) / 1920, text_crop[1] + (text_pos[1][1] + 6) / 1080
            instance_name_match = re.search(r"【(.+?)】", auto.get_single_line_text(crop=(x1, y1, x2 - x1, y2 - y1)) or "")
            if instance_name_match:
                return instance_name_match.group(1)

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

        if not BuildTarget._template_instance_names:
            with open("./assets/config/instance_names.json", "r", encoding="utf-8") as f:
                BuildTarget._template_instance_names = json.load(f)

        if not instance_type or not instance_name:
            return False

        if BuildTarget._template_instance_names.get(instance_type):
            if BuildTarget._template_instance_names[instance_type].get(instance_name):
                return True

        return False
