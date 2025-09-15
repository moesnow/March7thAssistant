import os
import re
import json
import yaml
import shutil
from datetime import datetime, timedelta
from module.logger import log

RED, YELLOW, GREEN, RESET = "\033[91m", "\033[93m", "\033[92m", "\033[0m"
date_pat = re.compile(r"\d{4}-\d{1,2}-\d{1,2}")

# 自定义 YAML Loader
# 用于在加载 YAML 文件时记录行号，同时检测重复 key
class LineLoader(yaml.SafeLoader):
    def __init__(self, stream):
        super().__init__(stream)
        self.tip_list = []
        self.warn_list = []
        self.error_list = []
        self.valid_dates = []

    def construct_mapping(self, node, deep=False, is_top_level=False):
        result, seen_keys = {}, {}

        for key_node, value_node in node.value:
            key = str(self.construct_object(key_node, deep=deep))
            value = self.construct_object(value_node, deep=deep)
            line = key_node.start_mark.line + 1

            # 检查重复的副本类型
            if key in seen_keys and not is_top_level:
                msg = f"同一天内副本类型重复 '{key}'，前一个 '{key}' 会把这个覆盖掉"
                self.warn_list.append((line, msg))
                continue

            # 检查日期是否正确
            if is_top_level and not self.check_top_level_key(line, key):
                continue

            # 检查每天的计划的格式
            if is_top_level and not isinstance(value, dict):
                self.error_list.append((line, f"{key} 该日期下任务格式错误"))
                continue

            seen_keys[key] = value
            result[key] = value

        result['_start_line'] = node.start_mark.line + 1
        return result

    def check_top_level_key(self, line, key):
        if not date_pat.fullmatch(key):
            self.error_list.append((line, f"日期格式错误: {key}"))
            return False
        try:
            date_obj = datetime.strptime(key, "%Y-%m-%d")
            for d, k, l in self.valid_dates:
                if date_obj == d:
                    self.warn_list.append((line, f"{key} 日期重复，前一个日期 {key} 会把这个覆盖掉"))
                    return False
            self.valid_dates.append((date_obj, key, line))
        except ValueError:
            self.warn_list.append((line, f"日历上可不存在这一天哦: {key}"))
            return False
        return True


def construct_document(loader, node):
    return loader.construct_mapping(node, is_top_level=True)


LineLoader.construct_document = construct_document
LineLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    LineLoader.construct_mapping
)

# 该函数用于加载并检查 schedule.yaml
# 返回值是当天的计划 
def check_schedule(
    schedule_file="schedule.yaml",
    instance_file="assets/config/instance_names.json"
):
    log_str = []

    with open(instance_file, "r", encoding="utf-8") as f:
        instance_data = json.load(f)

    if not os.path.exists(schedule_file):
        shutil.copy("assets/config/schedule.template.yaml", schedule_file)

    try:
        with open(schedule_file, "r", encoding="utf-8") as f:
            loader = LineLoader(f)
            schedule = yaml.load(f, Loader=lambda stream: loader)
            warn_list = loader.warn_list
            error_list = loader.error_list
            tip_list = loader.tip_list
            valid_dates = loader.valid_dates
    except yaml.YAMLError as e:
        log.error(f"{RED}[ERROR] YAML 格式错误: {e}{RESET}")
        log.warn("\n".join(log_str))
        return None
    except Exception as e:
        log.error(f"{RED}[ERROR] 无法读取 YAML 文件: {e}{RESET}")
        log.warn("\n".join(log_str))
        return None

    # ------------------- 检查副本和章节是否存在 -------------------
    for date, tasks in schedule.items():
        if date == "_start_line":
            continue

        line = tasks.get("_start_line", '未知行')
        instances = [ins for ins in tasks.keys() if ins != "_start_line"]

        for ins in list(instances):
            chap = tasks[ins]
            if ins not in instance_data:
                error_list.append((line, f"{date} 不存在名为“{ins}”的副本类型"))
                tasks.pop(ins)
                instances.remove(ins)
                continue
            elif chap not in instance_data[ins]:
                error_list.append((line, f"{date} 不存在名为“{chap}”的{ins}"))
                tasks.pop(ins)
                instances.remove(ins)
                continue

        if len(instances) == 1 and instances[0] == "历战余响":
            tip_list.append((line, f"{date} 做完历战余响后可能有剩余的体力，建议安排第二个副本"))
        elif len(instances) > 1 and instances[0] != "历战余响":
            warn_list.append((line, f"{date} 做完第一个副本 '{instances[0]}' 后，可能不会有剩余的体力去做后续副本"))
        elif len(instances) > 2:
            warn_list.append((line, f"{date} 做完第第二个副本 '{instances[1]}' 后，可能不会有剩余的体力去做后续副本"))

    # ------------------- 检查日期是否递增和连续 -------------------
    for i in range(1, len(valid_dates)):
        prev_d, prev_s, prev_l = valid_dates[i - 1]
        curr_d, curr_s, curr_l = valid_dates[i]
        if curr_d <= prev_d:
            tip_list.append((curr_l, f"{prev_s} -> {curr_s} 日期不是按时间顺序排列的，推荐按时间顺序编写任务"))

    sorted_dates = sorted(valid_dates, key=lambda x: x[0])
    for prev, curr in zip(sorted_dates, sorted_dates[1:]):
        if curr[0] != prev[0] + timedelta(days=1):
            tip_list.append((curr[2], f"{prev[1]} -> {curr[1]} 中间有空缺的日期，您是否忘了分配任务？"))

    # ------------------- 输出检查结果 -------------------
    combined = sorted(
        [(l, "ERROR", m) for l, m in error_list] +
        [(l, "WARN", m) for l, m in warn_list] +
        [(l, "TIPS", m) for l, m in tip_list],
        key=lambda x: x[0]
    )

    if combined:
        log_str.append(f"{os.path.basename(schedule_file)} 检查结果：")
        for l, lvl, msg in combined:
            color = GREEN if lvl == "TIPS" else YELLOW if lvl == "WARN" else RED
            log_str.append(f" - {color}[{lvl:^7}] 第{l:^4}行 {msg}{RESET}")
        if warn_list or error_list:
            log_str.append("")
        if error_list:
            log_str.append(f"{RED}⚠ 含 ERROR 的任务当天不会被执行{RESET}")
    else:
        log_str.append(f"{os.path.basename(schedule_file)} 检查通过，没有发现任何问题。")

    # ------------------- 返回当天副本 -------------------
    today = datetime.today().date()
    today_tasks = next(
        (tasks for d, tasks in schedule.items()
         if d != "_start_line" and datetime.strptime(d, "%Y-%m-%d").date() == today),
        None
    )

    has_today_error = today_tasks and any(
        l == today_tasks.get("_start_line", -1) for l, _ in error_list
    )
    if has_today_error:
        log_str.append(f"{RED}⚠ 今天计划的任务含有 ERROR，做可能与预期不符{RESET}")

    if today_tasks:
        today_tasks = {ins: chap for ins, chap in today_tasks.items() if ins != "_start_line"}
    else:
        today_tasks = None

    if log_str:
        log.info("\n".join(log_str))

    return today_tasks
