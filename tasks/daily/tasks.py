from module.logger import log
from module.automation import auto
from module.ocr import ocr
import time
import json
import sys
import re  # 用于加载正则表达式
from utils.console import pause_on_error


class Tasks:
    def __init__(self, config_example_path):
        self.crop = (243.0 / 1920, 377.0 / 1080, 1428.0 / 1920, 528.0 / 1080)
        self.task_mappings = self._load_config(config_example_path)
        self.daily_tasks = {}

    def _load_config(self, config_example_path):
        try:
            with open(config_example_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        except FileNotFoundError:
            log.error(f"配置文件不存在：{config_example_path}")
            pause_on_error()
            sys.exit(1)

    def start(self):
        if self.detect():
            self.scroll()
            self.detect()

    def detect(self):
        screenshot, _, _ = auto.take_screenshot(crop=self.crop)
        result = ocr.recognize_multi_lines(screenshot)
        for coords, text_data in result:
            if "本日活跃度已满" in text_data[0]:
                log.info("检测到本日活跃度已满提示，跳过后续任务检测")
                return False
        merged_texts = self._merge_ocr_blocks(result, x_gap=100)
        log.debug(f"每日实训分栏拼接的文本: {merged_texts}")
        progress_pattern = re.compile(r'(\d+)\s*[/／]\s*(\d+)')  # 用于匹配“X/Y”格式的正则表达式
        for text in merged_texts:
            for keyword, task_name in self.task_mappings.items():
                if keyword in text:
                    match = progress_pattern.search(text)
                    if match and match.group(1) == match.group(2):
                        self.daily_tasks[task_name] = False
                        log.debug(f"{task_name}:已完成")
                    else:
                        self.daily_tasks[task_name] = True
                        log.debug(f"{task_name}:待完成")
                    break
        return True

    def scroll(self):
        auto.click_element("./assets/images/zh_CN/reward/quest/activity.png", "image", 0.95, crop=self.crop)
        auto.mouse_scroll(40, -1)
        time.sleep(1)

    def _merge_block_data(self, block_list):
        """合并一个块内所有小元素的文本"""
        return "".join([b['text'] for b in block_list])

    def _merge_ocr_blocks(self, raw_ocr_results, x_gap=100):
        """按 X Y 轴将OCR文本片段合并成连续的文本字符串列表。"""
        # 输入检查
        if not raw_ocr_results:
            log.debug("每日实训未识别到任何文本")
            return []

        # 提取文本；X 轴边界用于判断同一块；Y 轴边界用于排序
        parsed_data = []
        for coords_list, text_data in raw_ocr_results:
            text, _ = text_data  # 忽略置信度
            point_x = [c[0] for c in coords_list]  # 提取X轴坐标
            point_y = [c[1] for c in coords_list]  # 提取Y轴坐标
            parsed_data.append({
                'x_min': min(point_x),  # 用于X轴分栏和排序
                'x_max': max(point_x),  # 用于X轴间距判断
                'y_min': min(point_y),  # 用于块内文本拼接的顺序
                'text': text,
            })
        # 按X轴从左到右，按Y轴从上到下排序(X轴优先，Y轴次之)
        parsed_data.sort(key=lambda item: (item['x_min'], item['y_min']))
        # 合并文本块
        merged_texts = []  # 存储最终合并的文本结果
        current_block = []  # 当前正在合并的文本块
        last_x_max = -1
        for item in parsed_data:
            x_min_current = item['x_min']
            if last_x_max == -1 or (x_min_current - last_x_max) > x_gap:
                # 与上一个块间隔过大，视为新块
                if current_block:
                    current_block.sort(key=lambda b: b['y_min'])  # 确保一个块内的文本顺序正确
                    merged_texts.append(self._merge_block_data(current_block))
                current_block = [item]  # 开始新块
            else:
                current_block.append(item)  # 属于同一块，合并
            last_x_max = item['x_max']  # 更新最新X轴右边界
        if current_block:
            current_block.sort(key=lambda b: b['y_min'])  # 确保一个块内的文本顺序正确
            merged_texts.append(self._merge_block_data(current_block))
        return merged_texts
