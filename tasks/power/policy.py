"""Windows 与触屏副本共用的计划、支援和结算规则。"""
import re
import unicodedata

from module.localization import get_raw_instance_names
from module.logger import log


from module.instance_limits import CAVERN, CRIMSON_CALYX, ECHO, GOLDEN_CALYX, INSTANCE_LIMITS, ORNAMENT, STAGNANT_SHADOW

ENTRY_TIMEOUT = 90
BATTLE_TIMEOUT = 30 * 60
DEFEAT_RETRIES = 2
_POWER_METER = re.compile(r"\+*\s*(?:满\s*)?(\d{1,4})\s*/\s*300\s*[+十]*")
_PC_POWER_METER = re.compile(r"\+*\s*(?:满\s*)?(\d{1,4})\s*(?:/|1)\s*300\s*[+十]*")
_IMMERSIFIER_METER = re.compile(r"\+*\s*(\d{1,2})\s*/\s*12\s*[+十]*")


class PowerError(RuntimeError):
    """副本未达到继续消耗开拓力所需的状态。"""


class InstanceUnavailable(PowerError):
    """已确认指定副本无法进入。"""


class InstanceTeamUnavailable(PowerError):
    """切队后没有可确认的出战编队，本项尚未开打。"""


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


class SupportNameSearch:
    """记录一次支援查找中读到的好友名字。"""

    def __init__(self):
        self._mismatches = set()
        self._matched = False

    def find_owner(self, auto, character_name, owner, crop):
        if match := auto.find_element(owner, "text", crop=crop, include=True):
            self._matched = True
            return match

        # 保留本次查找读到的原文，方便用户按日志填写。
        readings = tuple(text for _, (text, _) in auto.ocr_result if text)
        mismatch = character_name, owner, readings
        if mismatch in self._mismatches:
            return None
        self._mismatches.add(mismatch)
        names = "、".join(f"「{text}」" for text in readings)
        result = f"小助手读到的是{names}" if names else "小助手没读出这一位的名字"
        log.info(f"找到支援角色「{character_name}」，你填的好友名字是「{owner}」，{result}。")
        return None

    def warn_if_unmatched(self):
        if self._mismatches and not self._matched:
            log.warning(
                "本次没找到名字对得上的好友。请对照上面的日志和游戏里的好友名字。"
                "如果确认小助手读错了，可以把小助手「支援列表」里填的好友名字改成日志里读到的写法，再试一次。"
            )


def normalize(text):
    return "".join(unicodedata.normalize("NFKC", text or "").split())


def _parse_meter(text, pattern):
    value = unicodedata.normalize("NFKC", text or "").strip()
    if match := pattern.fullmatch(value):
        return int(match[1])
    readings = {int(match[1]) for box in value.splitlines() if (match := pattern.fullmatch(box.strip()))}
    return readings.pop() if len(readings) == 1 else None


def parse_power(text):
    return _parse_meter(text, _POWER_METER)


def parse_pc_power(text):
    # PC 地图上的斜线偶尔被 OCR 识别为 1。
    return _parse_meter((text or "").replace("?", "").replace("？", ""), _PC_POWER_METER)


def parse_immersifier_stock(text):
    return _parse_meter(text, _IMMERSIFIER_METER)


def parse_echo_rewards(text):
    value = unicodedata.normalize("NFKC", text)
    quotas = {int(match[1]) for match in re.finditer(r"(?<![\d/])([0-3])\s*/\s*3(?!\d)", value)}
    return quotas.pop() if len(quotas) == 1 else None


def plan_paid_batch(requested, available, cost_per_wave, *, immersifiers=0):
    """先使用沉浸器，其余波次由可用开拓力支付。"""
    waves = min(requested, immersifiers + available // cost_per_wave)
    immersifier_cost = min(waves, immersifiers)
    return waves, (waves - immersifier_cost) * cost_per_wave, immersifier_cost


def batch_limit(config, instance_type):
    _, limit = INSTANCE_LIMITS[instance_type]
    value = config.instance_names_challenge_count.get(instance_type, limit)
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= limit:
        log.warning(f"{instance_type} 的连续挑战次数无效，使用 {limit}")
        return limit
    return value


def remaining_plan(config):
    return config.remaining_power_plan() if hasattr(type(config), "remaining_power_plan") else config.power_plan


def run_plan(config, plan, run_instance):
    """按当前计划逐项执行。生成器确认一批便回写，再继续运行。"""
    if not isinstance(plan, list):
        log.warning("体力计划格式无效，已保留")
        return False

    names = get_raw_instance_names()
    remaining = list(plan)
    base = getattr(config, "power_plan", plan)
    complete = True
    skipped = None
    for index, item in enumerate(plan):
        if not isinstance(item, (list, tuple)) or len(item) != 3:
            log.warning(f"体力计划第 {index + 1} 项格式无效，已保留")
            complete = False
            continue
        instance_type, name, count = item
        if (not isinstance(instance_type, str) or instance_type not in INSTANCE_LIMITS
                or not isinstance(name, str) or name == "无" or name not in names[instance_type]
                or not isinstance(count, int) or isinstance(count, bool) or count <= 0):
            log.warning(f"体力计划第 {index + 1} 项副本或次数无效，已保留")
            complete = False
            continue

        log.info(f"体力计划 [{index + 1}/{len(plan)}] {instance_type} · {name}，剩余 {count} 次")
        try:
            for completed in run_instance(instance_type, name, count):
                if not 0 < completed <= count:
                    raise PowerError(f"确认的结算次数 {completed} 超出计划剩余次数 {count}")
                count -= completed
                if not config.power_plan_keep:
                    remaining[index] = [instance_type, name, count] if count else None
                    left = [entry for entry in remaining if entry is not None]
                    if hasattr(type(config), "consume_power_plan"):
                        config.consume_power_plan(left, base=base)
                    else:
                        config.set_value("power_plan", left)
        except InstanceTeamUnavailable as error:
            log.warning(error)
            skipped = skipped or error
            continue
        if count:
            log.info(f"资源不足，保留当前计划的 {count} 次及后续计划")
            complete = False
            break
    if skipped is not None:
        raise skipped
    if complete:
        log.info("体力计划已完成")
    return complete
