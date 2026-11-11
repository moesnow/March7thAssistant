"""Windows 与触屏副本共用的计划和结算规则。"""
import re
import unicodedata

from module.localization import get_raw_instance_names
from module.logger import log


GOLDEN_CALYX = "拟造花萼（金）"
CRIMSON_CALYX = "拟造花萼（赤）"
STAGNANT_SHADOW = "凝滞虚影"
CAVERN = "侵蚀隧洞"
ECHO = "历战余响"
ORNAMENT = "饰品提取"
INSTANCE_LIMITS = {
    GOLDEN_CALYX: (10, 24), CRIMSON_CALYX: (10, 24), STAGNANT_SHADOW: (30, 8),
    CAVERN: (40, 6), ECHO: (30, 3), ORNAMENT: (40, 6),
}
ENTRY_TIMEOUT = 90
BATTLE_TIMEOUT = 30 * 60
DEFEAT_RETRIES = 2


class PowerError(RuntimeError):
    """副本未达到继续消耗开拓力所需的状态。"""


class BattleDefeat(PowerError):
    """确认战败且已离开结算页。"""


class RelicBagFull(PowerError):
    """检测到遗器满包，尚未开打。"""


class SupportDemand:
    def __init__(self, pending=False):
        self.pending = pending

    def should_borrow(self, config):
        return config.borrow_enable and (config.borrow_character_enable or self.pending)

    def won(self, borrowed):
        if borrowed:
            self.pending = False


def normalize(text):
    return "".join(unicodedata.normalize("NFKC", text or "").split())


def parse_power(text):
    value = unicodedata.normalize("NFKC", text or "").strip().strip("+").strip()
    match = re.fullmatch(r"(\d{1,4})\s*/\s*300", value)
    return int(match[1]) if match else None


def parse_ornament_payment(text, waves):
    """挑战按钮从左到右显示沉浸器和开拓力。两项总价须匹配波次。"""
    amounts = normalize(text).lower().replace("×", "").replace("x", "").replace("米", "")
    for immersifiers in range(waves + 1):
        cost = (waves - immersifiers) * INSTANCE_LIMITS[ORNAMENT][0]
        if amounts == f"{immersifiers or ''}{cost or ''}":
            return cost, immersifiers
    return None


def check_balance(before, after, cost, elapsed):
    expected = before - cost
    # 战斗期间可能跨过自然恢复的时间点。
    ceiling = max(expected, min(300, expected + int(elapsed // 360) + 1))
    if not expected <= after <= ceiling:
        raise PowerError(f"结算开拓力与预期不符（预计 {expected}，实际 {after}）")


def batch_limit(config, instance_type):
    _, limit = INSTANCE_LIMITS[instance_type]
    value = config.instance_names_challenge_count.get(instance_type, limit)
    if type(value) is not int or not 1 <= value <= limit:
        log.warning(f"{instance_type} 的连续挑战次数无效，使用 {limit}")
        return limit
    return value


def run_plan(config, plan, run_instance):
    """按当前计划逐项执行。生成器确认一批便回写，再进行余额或退出检查。"""
    if not isinstance(plan, list):
        log.warning("体力计划格式无效，已保留")
        return False

    names = get_raw_instance_names()
    remaining = list(plan)
    complete = True
    for index, item in enumerate(plan):
        if not isinstance(item, (list, tuple)) or len(item) != 3:
            log.warning(f"体力计划第 {index + 1} 项格式无效，已保留")
            complete = False
            continue
        instance_type, name, count = item
        if (not isinstance(instance_type, str) or instance_type not in INSTANCE_LIMITS
                or not isinstance(name, str) or name == "无" or name not in names[instance_type]
                or type(count) is not int or count <= 0):
            log.warning(f"体力计划第 {index + 1} 项副本或次数无效，已保留")
            complete = False
            continue

        log.info(f"体力计划 [{index + 1}/{len(plan)}] {instance_type} · {name}，剩余 {count} 次")
        for completed in run_instance(instance_type, name, count):
            if not 0 < completed <= count:
                raise PowerError(f"确认的结算次数 {completed} 超出计划剩余次数 {count}")
            count -= completed
            if not config.power_plan_keep:
                remaining[index] = [instance_type, name, count] if count else None
                config.set_value("power_plan", [entry for entry in remaining if entry is not None])
        if count:
            log.info(f"资源不足，保留当前计划的 {count} 次及后续计划")
            return False
    if complete:
        log.info("体力计划已完成")
    return complete
