import os
import sys
import cv2
import numpy as np
import json
import time
import datetime
import re
from abc import ABC, abstractmethod
from typing import Callable, Generator
from module.screen import screen
from module.automation import auto
from module.logger import log
from module.config import cfg
from module.notification.notification import NotificationLevel
from module.localization import get_raw_instance_names
from tasks.base.base import Base
from utils.image_utils import ImageUtils


class BuildTargetHandler(ABC):
    """待刷副本的识别方案接口"""

    @abstractmethod
    def collect(self) -> list[tuple[str, str]]:
        """收集待刷副本信息，返回最终可用的副本列表。"""
        raise NotImplementedError()

    def _iter_scroll_windows(self, crop: tuple[float, float, float, float], capture_items: Callable) -> Generator[tuple[str, str] | None, None, None]:
        """
        滚动扫描列表，并通过 capture_items 采集当前窗口中的识别结果。
        capture_items 逐项产出当前窗口中的识别结果，返回 None 表示失败。
        """

        anchor_template = None
        paging_boundary_y = 0

        auto.take_screenshot(crop=crop)

        for _ in range(5):
            if anchor_template is not None:
                for _ in range(3):
                    auto.take_screenshot(crop)
                    screenshot = cv2.cvtColor(np.array(auto.screenshot), cv2.COLOR_BGR2RGB)
                    match_val, match_loc = ImageUtils.scale_and_match_template(screenshot, anchor_template, 0.8, None)
                    if match_val > 0.95:
                        paging_boundary_y = match_loc[1] + 64
                        break
                    else:
                        auto.mouse_scroll(2, 1)
                        time.sleep(1)
                else:
                    log.warning("滚动锚点跟踪失败")
                    break

            auto.take_screenshot(crop)
            screenshot_pos = auto.screenshot_pos
            has_items = False

            for pos, result in capture_items(paging_boundary_y, screenshot_pos):
                if result is None:
                    yield None
                    return

                has_items = True
                last_enter_pos = pos
                log.info(f"识别到副本: {result}")
                yield result

            if not has_items:
                log.info("查找结束，未找到更多可进入副本")
                break

            anchor_crop_height = (last_enter_pos[1][1] - last_enter_pos[0][1]) * auto.screenshot_scale_factor / 1080.0
            anchor_crop_top = crop[1] + last_enter_pos[0][1] * auto.screenshot_scale_factor / 1080.0
            anchor_crop = (crop[0], anchor_crop_top, crop[2], anchor_crop_height)
            anchor_template, _, _ = auto.take_screenshot(anchor_crop)
            anchor_template = cv2.cvtColor(np.array(anchor_template.copy()), cv2.COLOR_RGB2BGR)

            auto.mouse_scroll(12)
            time.sleep(1)


class DefaultHandler(BuildTargetHandler):
    """
    点进每一个副本的详情页，识别副本名称和类型。
    """

    def __init__(self) -> None:
        super().__init__()
        self._valid_instance_names = get_raw_instance_names()

    def collect(self) -> list[tuple[str, str]]:
        results = []
        page_crop = (688.0 / 1920, 286.0 / 1080, 969.0 / 1920, 676.0 / 1080)

        for instance in self._iter_scroll_windows(page_crop, self._capture_items_in_window):
            if not instance:
                Base.send_notification_with_screenshot(
                    "获取培养目标副本时出错，已提前返回当前已获取列表。\n详细情况请检查日志，如果持续出现错误可尝试切换识别方案", NotificationLevel.ERROR
                )
                break

            validated = self._is_valid_instance(instance)
            if validated:
                log.debug(f"副本名称 {validated} 检验通过，加入目标列表")
                results.append(validated)
                if "饰品提取" in validated[0]:
                    break
            else:
                log.warning(f"目标副本识别错误，{instance} 不在任何已知副本列表中")

        return results

    def _capture_items_in_window(self, paging_boundary_y: float, screenshot_pos):
        positions = []
        auto.perform_ocr()
        for box, (text, _) in auto.ocr_result:
            match, _ = auto.is_text_match(text, ["进入", "传送"], True)
            if match and box[0][1] > paging_boundary_y:
                positions.append(auto.calculate_text_position(box, True))

        screenshot_left, screenshot_top, _, _ = screenshot_pos

        for pos in positions:
            x1, y1 = screenshot_left + pos[0][0], screenshot_top + pos[0][1]
            x2, y2 = screenshot_left + pos[1][0], screenshot_top + pos[1][1]

            if not auto.click_element_with_pos(((x1, y1), (x2, y2))):
                log.error("尝试点击进入按钮时出错")
                yield pos, None
                return

            instance = self._get_instance_info()
            if not instance:
                log.error("未能获得任何副本信息")
                yield pos, None
                return

            log.debug(f"识别到副本信息: {instance}")

            if not self._exit_instance(instance[0]):
                log.error("未能返回培养目标列表页面")
                yield pos, None
                return

            yield pos, instance

    def _is_valid_instance(self, instance) -> tuple[str, str] | None:
        """验证并返回标准化的副本元组 (instance_type, instance_name) ，若无法验证返回 None。"""
        instance_type, instance_name = instance

        if not instance_type or not instance_name:
            return None

        known_names = self._valid_instance_names.get(instance_type)
        if not known_names:
            return None

        # 完全匹配优先
        if known_names.get(instance_name):
            return (instance_type, instance_name)

        # 模糊匹配：如果识别名称包含某个已知名称的子串，则使用该已知名称作为标准名
        for valid_name in known_names.keys():
            if valid_name in instance_name:
                log.debug(f"副本名称模糊匹配成功: 识别名称 '{instance_name}' 包含已知名称 '{valid_name}'，使用标准名称 '{valid_name}'")
                return (instance_type, valid_name)

        return None

    @staticmethod
    def _get_instance_info() -> tuple[str, str] | None:
        # 机械硬盘加载慢，可能需要较长时间等待挑战按钮出现
        if not auto.find_element(["挑战", "开始挑战"], "text", max_retries=60, crop=(1520.0 / 1920, 933.0 / 1080, 390.0 / 1920, 111.0 / 1080)):
            log.error("未能检测到挑战按钮")
            return None

        instance_type = auto.get_single_line_text(max_retries=5, retry_delay=1.0, crop=(93.0 / 1920, 33.0 / 1080, 150.0 / 1920, 68.0 / 1080))

        if instance_type is not None:
            if "饰品提取" in instance_type:
                instance_type = "饰品提取"
                instance_name = DefaultHandler._parse_ornament_instance_info()
            elif "拟造花萼" in instance_type:
                instance_name, instance_type = DefaultHandler._parse_calyx_instance_info()
            else:
                instance_name, _ = DefaultHandler._parse_standard_instance_info()

            instance_type = (instance_type or "").strip()
            instance_name = (instance_name or "").strip()

            if instance_type and instance_name:
                return (instance_type, instance_name)

        log.warning("未能识别到副本信息")
        return None

    @staticmethod
    def _exit_instance(instance_type) -> bool:
        auto.press_key("esc")

        if "饰品提取" in instance_type:
            time.sleep(0.5)
            auto.press_key("esc")
            return True

        if "拟造花萼（赤）" in instance_type:
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
    def _parse_ornament_instance_info() -> str | None:
        name = auto.get_single_line_text(max_retries=5, retry_delay=1.0, crop=(584.0 / 1920, 112.0 / 1080, 614.0 / 1920, 52.0 / 1080))
        if not name:
            return None

        # 移除“难度”及其之后的内容（例如“难度V”或“难度VI”），并去掉首尾空白
        parsed = re.sub(r"难度.*$", "", name).strip()

        # 如果解析后为空字符串，则返回原始去空白的名称
        return parsed or name.strip()

    @staticmethod
    def _parse_calyx_instance_info() -> tuple[str | None, str | None]:
        calyx_instance, calyx_type = DefaultHandler._parse_standard_instance_info()

        if not calyx_type or "拟造花萼" not in calyx_type:
            return None, None

        if "金" in calyx_type:
            calyx_type = "拟造花萼（金）"
        elif "赤" in calyx_type:
            calyx_type = "拟造花萼（赤）"
            for i in range(2):
                click_offset = (i * 88 / auto.screenshot_scale_factor, 64 / auto.screenshot_scale_factor)
                if not auto.click_element(
                    "可能获取", "text", offset=click_offset, max_retries=5, crop=(1196.0 / 1920, 492.0 / 1080, 705.0 / 1920, 456.0 / 1080)
                ):
                    log.error("尝试提取拟造花萼副本信息时失败，无法识别特定副本页面")
                    break

                item_name = auto.get_single_line_text(crop=(783.0 / 1920, 318.0 / 1080, 204.0 / 1920, 55.0 / 1080), max_retries=3, retry_delay=0.5)
                if not item_name or "信用点" in item_name:
                    log.error("尝试提取拟造花萼副本信息时失败，无法获取光锥晋阶材料信息")
                    break

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
                        calyx_instance = instance_name_match.group(1)
                        break
                    else:
                        log.error("尝试提取拟造花萼副本信息时失败，无法获取副本地点名称")

                auto.press_key("esc")
                time.sleep(1)

        return calyx_instance, calyx_type

    @staticmethod
    def _parse_standard_instance_info() -> tuple[str | None, str | None]:
        """解析普通副本标题，返回元组的副本名称与副本类型的排列顺序对应 OCR 识别到的顺序。通常情况下是 (副本名称, 副本类型)"""
        raw_instance_name = auto.get_single_line_text(max_retries=5, retry_delay=1.0, crop=(1173.0 / 1920, 113.0 / 1080, 735.0 / 1920, 53.0 / 1080))
        if raw_instance_name and "·" in raw_instance_name:
            blocks = raw_instance_name.split("·")
            if len(blocks) > 1:
                return (blocks[0], blocks[1])

        return None, None


class DropHandler(BuildTargetHandler):
    """
    通过列表左侧显示的掉落物匹配对应的副本。
    """

    SIMILARITY_THRESHOLD = 0.6

    def __init__(self):
        super().__init__()
        self._instance_drops = []
        self._init_drop_index()

    def collect(self) -> list[tuple[str, str]]:
        results = []
        page_crop = (688.0 / 1920, 286.0 / 1080, 969.0 / 1920, 676.0 / 1080)

        for instance in self._iter_scroll_windows(page_crop, self._capture_items_in_window):
            if not instance:
                Base.send_notification_with_screenshot("获取培养目标副本时出错，已提前返回当前已获取列表。\n详细情况请检查日志。", NotificationLevel.ERROR)
                break

            results.append(instance)

        return results

    def _init_drop_index(self) -> list[tuple[str, str, str]]:
        """加载副本掉落信息，构建索引列表。格式为 [(instance_type, instance_name, drop), ...]"""
        if self._instance_drops:
            return self._instance_drops

        if getattr(sys, "frozen", False):
            file_path = os.path.join(os.path.dirname(sys.executable), "assets", "config", "instance_drops.json")
        else:
            file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "config", "instance_drops.json")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

                self._instance_drops.extend(
                    (instance_type, instance_name, instance_drop)
                    for instance_type, instance in data.items()
                    for instance_name, instance_drops in instance.items()
                    for instance_drop in instance_drops
                )

                log.debug(f"成功加载副本信息，共 {len(self._instance_drops)} 条")

        except Exception as e:
            log.error("加载 instance_drops 文件时出错: " + str(e))

        return self._instance_drops

    def _capture_items_in_window(self, paging_boundary_y: float, screenshot_pos):
        positions = auto.find_image_with_multiple_targets("./assets/images/share/build_target/power.png", 0.8, None, relative=True)
        positions = [pos for pos in positions if pos[0][1] > paging_boundary_y]

        screenshot_left, screenshot_top, _, _ = screenshot_pos

        for pos in positions:
            x1, y1 = screenshot_left + pos[0][0], screenshot_top + pos[0][1]
            x2, y2 = screenshot_left + pos[1][0], screenshot_top + pos[1][1]

            if not auto.click_element_with_pos(((x1, y1), (x2, y2)), offset=(-510 * auto.screenshot_scale_factor, 0)):
                log.error("尝试点击进入按钮时出错")
                yield pos, None
                return

            if instance := self._get_instance_by_drop():
                yield pos, (instance[0], instance[1])
            else:
                yield pos, None
                return

    def _get_instance_by_drop(self) -> tuple[str, str, str, float] | None:
        """
        识别掉落物名称，并匹配对应的副本信息，返回 (instance_type, instance_name, drop, similarity_score) 或 None
        """
        time.sleep(0.5)
        if auto.find_element(
            "./assets/images/share/build_target/drop_modal_close.png",
            "image",
            0.8,
            max_retries=4,
            retry_delay=0.5,
            crop=(1330 / 1920, 222 / 1080, 256 / 1920, 236 / 1080),
        ):
            drop_name = auto.get_single_line_text(crop=(783 / 1920, 318 / 1080, 300 / 1920, 55 / 1080), max_retries=2, retry_delay=0.5)
            if auto.click_element(
                "./assets/images/share/build_target/drop_modal_close.png", "image", 0.8, crop=(1330 / 1920, 222 / 1080, 256 / 1920, 236 / 1080)
            ):
                time.sleep(1.0)
            if drop_name:
                log.debug(f"识别到掉落物: {drop_name}")
                return self._match_instance(drop_name)
        log.warning("未能识别到掉落物")
        return None

    def _match_instance(self, query: str) -> tuple[str, str, str, float] | None:
        """
        在所有已知的副本掉落信息中，找到与查询字符串最相似的掉落项，返回(instance_type, instance_name, drop, similarity_score)
        如果没有任何项的相似度超过阈值，则返回 None。
        """

        results = []
        for instance_type, instance_name, drop in self._instance_drops:
            score = self._similarity(query, drop)
            if score >= self.SIMILARITY_THRESHOLD:
                results.append((instance_type, instance_name, drop, round(score, 4)))

        if results:
            results.sort(key=lambda r: r[3], reverse=True)
            log.debug(f"副本掉落信息匹配结果: {results}")
            return results[0]
        else:
            log.warning(f"未找到与 '{query}' 匹配的副本信息")
            return None

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """字符串相似度计算，结合 Levenshtein 和 LCS，返回 0.0 到 1.0 之间的相似度分数。"""
        m, n = len(a), len(b)
        if not m and not n:
            return 1.0
        if not m or not n:
            return 0.0

        # --- Levenshtein ---
        prev = list(range(n + 1))
        for i in range(1, m + 1):
            curr = [i] + [0] * n
            for j in range(1, n + 1):
                curr[j] = min(
                    curr[j - 1] + 1,
                    prev[j] + 1,
                    prev[j - 1] + (0 if a[i - 1] == b[j - 1] else 1),
                )
            prev = curr
        lev = 1.0 - prev[n] / max(m, n)

        # --- LCS ---
        prev = [0] * (n + 1)
        for ch in a:
            curr = [0] * (n + 1)
            for j, c in enumerate(b, 1):
                curr[j] = prev[j - 1] + 1 if ch == c else max(curr[j - 1], prev[j])
            prev = curr
        lcs = 2 * prev[n] / (m + n)

        return (lev + lcs) / 2


class BuildTarget:
    _initialized = False
    _build_target_name = None

    # 培养目标待刷副本，格式为 {instance_type: [instance_name1, instance_name2, ...], ...}
    _target_instances: dict[str, list[str]] = {}

    @staticmethod
    def get_target_instance() -> tuple[str, str] | None:
        """尝试获取培养目标普通副本信息"""
        if not BuildTarget._initialized:
            BuildTarget.init_build_targets()

        require_ornament = False
        only_erosion_and_ornament = False
        if BuildTarget._target_instances:
            only_erosion_and_ornament = all(("侵蚀隧洞" in instance_type) or ("饰品提取" in instance_type) for instance_type in BuildTarget._target_instances)
            if only_erosion_and_ornament:
                require_ornament = datetime.date.today().weekday() >= (7 - cfg.build_target_ornament_weekly_count)

        if only_erosion_and_ornament and cfg.build_target_use_user_instance_when_only_erosion_and_ornament:
            log.info("培养目标仅识别到侵蚀隧洞/饰品提取，按配置回退至自定义副本")
            return None

        for instance_type, instance_names in BuildTarget._target_instances.items():
            if "历战余响" in instance_type:
                continue
            if not require_ornament:
                return (instance_type, instance_names[0])
            if "饰品提取" in instance_type:
                return (instance_type, instance_names[0])

        return None

    @staticmethod
    def get_target_echo_instance() -> tuple[str, str] | None:
        """尝试获取培养目标历战余响副本信息"""
        if not BuildTarget._initialized:
            BuildTarget.init_build_targets()

        if instance_names := BuildTarget._target_instances.get("历战余响"):
            return ("历战余响", instance_names[0])

        return None

    @staticmethod
    def get_target_instances() -> list[tuple[str, str]]:
        """尝试获取培养目标所有待刷副本信息"""
        if not BuildTarget._initialized:
            BuildTarget.init_build_targets()

        return [(instance_type, name) for instance_type, names in BuildTarget._target_instances.items() for name in names]

    @staticmethod
    def init_build_targets():
        BuildTarget._initialized = True
        BuildTarget._build_target_name = None
        BuildTarget._target_instances = {}

        handler = BuildTarget._get_handler()

        log.hr("开始获取培养目标")

        screenshot = None

        if BuildTarget._enter_build_target_page():
            auto.take_screenshot()
            screenshot = auto.screenshot

            for instance_type, instance_name in handler.collect():
                BuildTarget._target_instances.setdefault(instance_type, []).append(instance_name)

        if BuildTarget._target_instances:
            lines = [f"{t} - {', '.join(names)}" for t, names in BuildTarget._target_instances.items()]
            message = f"培养目标{BuildTarget._build_target_name or 'None'}的待刷副本:\n{"\n".join(lines)}"
            Base.send_notification_with_screenshot(message, NotificationLevel.ALL, screenshot)
        else:
            Base.send_notification_with_screenshot("未能获取到任何培养目标副本信息，回退至默认的设置", NotificationLevel.ERROR)

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

        if not auto.click_element(
            "./assets/images/share/build_target/power.png", "image", 0.8, max_retries=5, crop=(688.0 / 1920, 286.0 / 1080, 969.0 / 1920, 676.0 / 1080)
        ):
            log.warning("未检测到任何可进入的培养目标副本")
            return False

        return True

    @staticmethod
    def _get_handler() -> BuildTargetHandler:
        scheme = cfg.build_target_scheme
        if scheme == "instance":
            return DefaultHandler()
        else:
            return DropHandler()
