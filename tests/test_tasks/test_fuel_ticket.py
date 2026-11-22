from dataclasses import replace
from unittest.mock import Mock

import pytest

from tasks.power.fuel_ticket import (
    FuelTicketBatch, FuelTicketReceipt, FuelTicketSettlementUnknown,
    execute_fuel_ticket_batch, parse_clear_progress, plan_fuel_ticket_batch,
    verify_fuel_ticket_receipt,
)

GOLD = "拟造花萼（金）"
RED = "拟造花萼（赤）"
SHADOW = "凝滞虚影"
NAME = "测试副本"


@pytest.mark.parametrize("kind,requested,power,tickets,expected", [
    (GOLD, 24, 300, 50, (24, 240, 24)),
    (RED, 7, 25, 100, (2, 20, 2)),
    (RED, 7, 120, 4, (4, 40, 4)),
    (SHADOW, 8, 300, 8, (2, 60, 6)),
    (SHADOW, 8, 59, 20, (1, 30, 3)),
    (SHADOW, 1, 300, 50, (1, 30, 3)),
    (GOLD, 99, 300, 99, (24, 240, 24)),
    (SHADOW, 99, 300, 99, (8, 240, 24)),
])
def test_ticket_batches_respect_plan_power_stock_and_instance_limits(kind, requested, power, tickets, expected):
    batch = plan_fuel_ticket_batch(kind, NAME, requested, power, tickets, enabled=True)
    assert (batch.waves, batch.power, batch.tickets) == expected
    assert batch.instance_type == kind and batch.name == NAME


@pytest.mark.parametrize("kind,power,tickets,enabled,support_pending", [
    ("历战余响", 300, 50, True, False),
    ("侵蚀隧洞", 300, 50, True, False),
    ("饰品提取", 300, 50, True, False),
    (SHADOW, 300, 2, True, False),
    (GOLD, 9, 100, True, False),
    (GOLD, 300, 0, True, False),
    (GOLD, 300, None, True, False),
    (GOLD, 300, True, True, False),
    (GOLD, 300, 50, False, False),
    (GOLD, 300, 50, True, True),
])
def test_no_tickets_for_ineligible_or_unconfirmed_cases(kind, power, tickets, enabled, support_pending):
    assert plan_fuel_ticket_batch(kind, NAME, 6, power, tickets,
                                 enabled=enabled, support_pending=support_pending) is None


@pytest.mark.parametrize("text,expected", [
    ("61/500\n117/300\n刷取次数 10/10", (10, 10)),
    ("刷取次数\n２／４", (2, 4)),
    ("刷取次数 0/6", (0, 6)),
    ("117/300\n61/500", None),
    ("刷取次数 7/6", None),
    ("刷取次数 1/2\n刷取次数 2/2", None),
])
def test_progress_is_not_a_stock_readout(text, expected):
    assert parse_clear_progress(text) == expected


def test_verified_partial_result_keeps_the_remaining_plan():
    batch = FuelTicketBatch(SHADOW, NAME, 4, 120, 12)
    receipt = FuelTicketReceipt(SHADOW, NAME, 2, 4, 60, 6)
    assert verify_fuel_ticket_receipt(batch, receipt) == 2


@pytest.mark.parametrize("change", [
    {"name": "其他副本"}, {"instance_type": RED}, {"completed": 5},
    {"completed": 0}, {"requested": 3}, {"spent_power": 30},
    {"spent_tickets": 2}, {"completed": True},
])
def test_conflicting_receipt_never_decrements_plan(change):
    batch = FuelTicketBatch(SHADOW, NAME, 4, 120, 12)
    receipt = FuelTicketReceipt(SHADOW, NAME, 4, 4, 120, 12)
    with pytest.raises(FuelTicketSettlementUnknown):
        verify_fuel_ticket_receipt(batch, replace(receipt, **change))


def test_only_preflight_miss_can_fall_back():
    batch = FuelTicketBatch(GOLD, NAME, 3, 30, 3)
    screen = Mock()
    screen.prepare.return_value = False
    assert execute_fuel_ticket_batch(screen, batch) == 0
    screen.submit.assert_not_called()
    screen.read_receipt.assert_not_called()


@pytest.mark.parametrize("where", ["submit", "read_receipt"])
def test_ambiguous_submission_is_never_retried(where):
    batch = FuelTicketBatch(GOLD, NAME, 3, 30, 3)
    screen = Mock()
    screen.prepare.return_value = True
    getattr(screen, where).side_effect = TimeoutError("unknown")
    with pytest.raises(TimeoutError, match="unknown"):
        execute_fuel_ticket_batch(screen, batch)
    screen.submit.assert_called_once_with(batch)


def test_full_receipt_commits_only_once():
    batch = FuelTicketBatch(GOLD, NAME, 3, 30, 3)
    screen = Mock()
    screen.prepare.return_value = True
    screen.read_receipt.return_value = FuelTicketReceipt(GOLD, NAME, 3, 3, 30, 3)
    assert execute_fuel_ticket_batch(screen, batch) == 3
    screen.submit.assert_called_once_with(batch)
    screen.read_receipt.assert_called_once_with()
