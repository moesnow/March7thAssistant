"""自动化已识别的数值。每次将值和时间一并写入配置。"""
from datetime import datetime, timedelta
import logging
import time

from utils.date import Date
from .types import DailyTraining, PowerReading

POWER_CAP = 300
SECONDS_PER_POWER = 6 * 60


def seconds_until_full(value):
    return max(0, POWER_CAP - value) * SECONDS_PER_POWER


def save_reading(config, key, value):
    try:
        config.set_value(key, {"value": value, "timestamp": time.time()})
    except Exception as error:
        from module.accounts.errors import AccountError
        if isinstance(error, AccountError):
            raise
        logging.getLogger("March7thAssistant").warning("无法保存总览读数 %s，本次任务继续", key, exc_info=True)


def power_now(reading, now):
    """按每 6 分钟恢复 1 点估算现在的开拓力，最多恢复到上限。"""
    gained = int(max(0, (now - reading.read_at).total_seconds()) // SECONDS_PER_POWER)
    return max(reading.value, min(reading.value + gained, reading.maximum))


def next_power_in(reading, now):
    """恢复下一点还要多少秒。已经回满时返回 None。"""
    if power_now(reading, now) >= reading.maximum:
        return None
    return SECONDS_PER_POWER - max(0, (now - reading.read_at).total_seconds()) % SECONDS_PER_POWER


def power_reading(config):
    reading = config.get_value("overview_power")
    if not reading:
        return PowerReading(None, None, None)
    value = reading["value"]
    if type(value) is not int or value < 0:
        raise ValueError("开拓力读数无效")
    read_at = datetime.fromtimestamp(reading["timestamp"])
    return PowerReading(value, read_at, read_at + timedelta(seconds=seconds_until_full(value)))


def daily_training(config, now):
    stamp = config.last_run_timestamp
    completed = bool(stamp) and not Date.is_next_x_am(stamp, config.refresh_hour, now=now)
    activity = 500 if completed else None
    reading = config.get_value("overview_daily_activity")
    if reading and not Date.is_next_x_am(reading["timestamp"], config.refresh_hour, now=now):
        value = reading["value"]
        if type(value) is not int or not 0 <= value <= 500:
            raise ValueError("每日实训活跃度无效")
        activity = value
    return DailyTraining(completed, datetime.fromtimestamp(stamp) if completed else None, activity)
