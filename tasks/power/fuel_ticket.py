"""助燃券速刷的纯预算、提交与结算规则；不依赖图像识别或平台输入。"""
from dataclasses import dataclass
import re
import unicodedata
from typing import Protocol


# 3.7 游戏公告：花萼和凝滞虚影每消费 10 开拓力需 1 张助燃券。
_TICKET_INSTANCE_COST = {
    "拟造花萼（金）": 10,
    "拟造花萼（赤）": 10,
    "凝滞虚影": 30,
}


class FuelTicketSettlementUnknown(RuntimeError):
    """速刷可能已经支付，但无法确认结算；禁止回退到普通战斗或重试扣费。"""


@dataclass(frozen=True)
class FuelTicketBatch:
    instance_type: str
    name: str
    waves: int
    power: int
    tickets: int


@dataclass(frozen=True)
class FuelTicketReceipt:
    instance_type: str
    name: str
    completed: int
    requested: int
    spent_power: int
    spent_tickets: int


class FuelTicketScreen(Protocol):
    def prepare(self, batch: FuelTicketBatch) -> bool:
        """仅进行不扣费的界面操作及验证；False 时已返回可安全常规刷取的页面。"""
        ...

    def submit(self, batch: FuelTicketBatch) -> None:
        """仅提交一次；任何异常都视为可能已扣费。"""
        ...

    def read_receipt(self) -> FuelTicketReceipt:
        """从真实完成页面识别目标、次数及消费；不允许以计划数据填充。"""
        ...


def plan_fuel_ticket_batch(instance_type: str, name: str, requested: int,
                           available: int, tickets: int | None, *,
                           enabled: bool, support_pending: bool = False) -> FuelTicketBatch | None:
    """优先使用可支付的最大整批，保留原副本、计划上限和支援实训需求。"""
    cost = _TICKET_INSTANCE_COST.get(instance_type)
    if not enabled or support_pending or not cost or not name or name == "无":
        return None
    values = (requested, available, tickets)
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in values):
        return None
    waves = min(requested, available // cost, tickets // (cost // 10),
                8 if cost == 30 else 24)
    if not waves:
        return None
    return FuelTicketBatch(instance_type, name, waves, waves * cost, waves * (cost // 10))


def parse_clear_progress(text: str) -> tuple[int, int] | None:
    """识别标明刷取次数的进度；不要把顶部券库存、体力读数误当结算。"""
    text = unicodedata.normalize("NFKC", text or "")
    matches = re.findall(r"刷取次数[ \t\r\n:：]*(\d{1,2})\s*/\s*(\d{1,2})(?!\d)", text)
    readings = {(int(done), int(total)) for done, total in matches}
    if len(readings) != 1:
        return None
    done, total = readings.pop()
    if not 0 <= done <= total <= 24 or total == 0:
        return None
    return done, total


def verify_fuel_ticket_receipt(batch: FuelTicketBatch, receipt: FuelTicketReceipt) -> int:
    """返回实际确认完成次数；不可靠或重复/超额结算必须停止。"""
    if not isinstance(receipt, FuelTicketReceipt):
        raise FuelTicketSettlementUnknown("未识别到助燃券速刷结算")
    counts = (receipt.completed, receipt.requested, receipt.spent_power, receipt.spent_tickets)
    if any(not isinstance(value, int) or isinstance(value, bool) for value in counts):
        raise FuelTicketSettlementUnknown("助燃券结算数值异常")
    if (receipt.instance_type != batch.instance_type or receipt.name != batch.name
            or receipt.requested != batch.waves
            or not 0 < receipt.completed <= batch.waves
            or receipt.spent_power != receipt.completed * (batch.power // batch.waves)
            or receipt.spent_tickets != receipt.completed * (batch.tickets // batch.waves)):
        raise FuelTicketSettlementUnknown("助燃券速刷结算与副本、次数或消费不一致")
    return receipt.completed


def execute_fuel_ticket_batch(screen: FuelTicketScreen, batch: FuelTicketBatch) -> int:
    """只在无扣费的准备阶段允许普通战斗回退；发起后必须先辨明交易结果。"""
    if not screen.prepare(batch):
        return 0
    # 不在此处捕获异常并尝试普通战斗：点击失败也可能已经触发扣费。
    screen.submit(batch)
    return verify_fuel_ticket_receipt(batch, screen.read_receipt())
