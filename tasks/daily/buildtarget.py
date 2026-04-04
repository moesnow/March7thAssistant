import os
import sys
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


class BuildTarget:
    SIMILARITY_THRESHOLD = 0.6

    _initialized = False
    _build_target_name = ""

    # 培养目标，格式为 {instance_type: [instance_name1, instance_name2, ...], ...}
    _target_instances = {}

    # 掉落物到副本的反向索引，格式为 [(instance_type, instance_name, drop), ...]
    _instance_drops = []

    @staticmethod
    def get_target_instance() -> tuple[str, str] | None:
        """尝试获取培养目标普通副本信息"""
        if not BuildTarget._initialized:
            BuildTarget.init_build_targets()

        require_ornament = False
        if BuildTarget._target_instances:
            only_erosion_and_ornament = all(("侵蚀隧洞" in instance_type) or ("饰品提取" in instance_type) for instance_type in BuildTarget._target_instances)
            if only_erosion_and_ornament:
                require_ornament = datetime.date.today().weekday() >= (7 - cfg.build_target_ornament_weekly_count)

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
        BuildTarget._target_instances = {}

        log.hr("开始获取培养目标")

        screenshot = None

        if BuildTarget._enter_build_target_page():
            auto.take_screenshot()
            screenshot = auto.screenshot

            for instance in BuildTarget._get_target_instances():
                if not instance:
                    Base.send_notification_with_screenshot("获取培养目标副本时出错，已提前返回当前已获取列表。\n详细情况请检查日志。", NotificationLevel.ERROR)
                    break

                instance_type, instance_name, _, _ = instance

                BuildTarget._target_instances[instance_type] = BuildTarget._target_instances.get(instance_type, [])
                BuildTarget._target_instances[instance_type].append(instance_name)

        if BuildTarget._target_instances:
            message = f"培养目标{BuildTarget._build_target_name or 'None'}的待刷副本:\n" + "\n".join(
                f"{instance_type} - {', '.join(names)}" for instance_type, names in BuildTarget._target_instances.items()
            )
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

        if not auto.click_element("./assets/images/share/build_target/power.png", "image", 0.8, max_retries=5, crop=(688.0 / 1920, 286.0 / 1080, 969.0 / 1920, 676.0 / 1080)):
            log.warning("未检测到任何可进入的培养目标副本")
            return False

        return True

    @staticmethod
    def _get_target_instances():
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
                    log.warning("滚动锚点跟踪失败")
                    break

            auto.take_screenshot(page_crop)
            enter_positions = auto.find_image_with_multiple_targets("./assets/images/share/build_target/power.png", 0.8, None, relative=True)
            enter_positions = [pos for pos in enter_positions if pos[0][1] > paging_boundary_y]

            if not enter_positions:
                log.info("查找结束，未找到更多可进入副本")
                break

            screenshot_left, screenshot_top, _, _ = auto.screenshot_pos

            for pos in enter_positions:
                x1, y1 = screenshot_left + pos[0][0], screenshot_top + pos[0][1]
                x2, y2 = screenshot_left + pos[1][0], screenshot_top + pos[1][1]

                if not auto.click_element_with_pos(((x1, y1), (x2, y2)), offset=(-510 * auto.screenshot_scale_factor, 0)):
                    log.error("尝试点击进入按钮时出错")
                    yield None
                    return

                if not (instance := BuildTarget._get_instance_info()):
                    log.error("未能获得任何副本信息")
                    yield None
                    return

                log.info(f"识别到副本: {instance}")

                yield instance

            last_enter_pos = enter_positions[-1]
            anchor_crop_height = (last_enter_pos[1][1] - last_enter_pos[0][1]) * auto.screenshot_scale_factor / 1080.0
            anchor_crop_top = page_crop[1] + last_enter_pos[0][1] * auto.screenshot_scale_factor / 1080.0
            anchor_crop = (page_crop[0], anchor_crop_top, page_crop[2], anchor_crop_height)
            anchor_template, _, _ = auto.take_screenshot(anchor_crop)
            anchor_template = cv2.cvtColor(np.array(anchor_template.copy()), cv2.COLOR_RGB2BGR)

            auto.mouse_scroll(12)
            time.sleep(1)

    @staticmethod
    def _get_instance_info():
        time.sleep(0.5)
        if auto.find_element(
            "./assets/images/share/build_target/drop_modal_close.png",
            "image",
            max_retries=4,
            retry_delay=0.5,
            crop=(1330 / 1920, 222 / 1080, 256 / 1920, 236 / 1080),
        ):
            drop_name = auto.get_single_line_text(crop=(783 / 1920, 318 / 1080, 300 / 1920, 55 / 1080), max_retries=2, retry_delay=0.5)
            if auto.click_element("./assets/images/share/build_target/drop_modal_close.png", "image", crop=(1330 / 1920, 222 / 1080, 256 / 1920, 236 / 1080)):
                time.sleep(0.5)
            if drop_name:
                log.debug(f"识别到掉落物: {drop_name}")
                return BuildTarget._match_instance(drop_name)
        log.warning("未能识别到掉落物")
        return None

    @staticmethod
    def _init_drop_index() -> list:
        """加载副本掉落信息，构建反向索引列表"""
        if BuildTarget._instance_drops:
            return BuildTarget._instance_drops

        if getattr(sys, "frozen", False):
            file_path = os.path.join(os.path.dirname(sys.executable), "assets", "config", "instance_drops.json")
        else:
            file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "config", "instance_drops.json")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

                BuildTarget._instance_drops.extend(
                    (instance_type, instance_name, instance_drop)
                    for instance_type, instance in data.items()
                    for instance_name, instance_drops in instance.items()
                    for instance_drop in instance_drops
                )

                log.debug(f"成功加载副本信息，共 {len(BuildTarget._instance_drops)} 条")

        except Exception as e:
            log.error("加载 instance_drops 文件时出错: " + str(e))

        return BuildTarget._instance_drops

    @staticmethod
    def _match_instance(query: str) -> tuple[str, str, str, float] | None:
        """
        在所有已知的副本掉落信息中，找到与查询字符串最相似的掉落项，返回对应(instance_type, instance_name, drop, similarity_score)
        如果没有任何项的相似度超过阈值，则返回 None。
        """
        BuildTarget._init_drop_index()

        results = []
        for instance_type, instance_name, drop in BuildTarget._instance_drops:
            score = BuildTarget._similarity(query, drop)
            if score >= BuildTarget.SIMILARITY_THRESHOLD:
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
