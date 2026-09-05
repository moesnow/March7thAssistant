from types import SimpleNamespace
from unittest.mock import patch

from tasks.daily import buildtarget
from tasks.daily.buildtarget import BuildTarget, DefaultHandler


def test_default_handler_continues_collecting_after_ornament():
    handler = DefaultHandler.__new__(DefaultHandler)
    instances = [
        ("饰品提取", "永恒笑剧"),
        ("拟造花萼（金）", "回忆之蕾"),
        ("凝滞虚影", "嗔怒之形"),
    ]

    with (
        patch.object(handler, "_iter_scroll_windows", return_value=instances),
        patch.object(handler, "_capture_items_in_window"),
        patch.object(handler, "_is_valid_instance", side_effect=lambda instance: instance),
    ):
        assert handler.collect() == instances


def test_material_instance_is_prioritized_even_when_ornament_is_first():
    targets = {
        "饰品提取": ["永恒笑剧"],
        "拟造花萼（金）": ["回忆之蕾"],
        "凝滞虚影": ["嗔怒之形"],
    }
    cfg = SimpleNamespace(
        build_target_use_user_instance_when_only_erosion_and_ornament=True,
        build_target_ornament_weekly_count=7,
    )

    with (
        patch.object(buildtarget, "cfg", cfg),
        patch.object(BuildTarget, "_initialized", True),
        patch.object(BuildTarget, "_target_instances", targets),
    ):
        assert BuildTarget.get_target_instance() == ("拟造花萼（金）", "回忆之蕾")


def test_only_erosion_and_ornament_returns_to_custom_instance_when_enabled():
    targets = {
        "饰品提取": ["永恒笑剧"],
        "侵蚀隧洞": ["睿治之径"],
    }
    cfg = SimpleNamespace(
        build_target_use_user_instance_when_only_erosion_and_ornament=True,
        build_target_ornament_weekly_count=7,
    )

    with (
        patch.object(buildtarget, "cfg", cfg),
        patch.object(BuildTarget, "_initialized", True),
        patch.object(BuildTarget, "_target_instances", targets),
    ):
        assert BuildTarget.get_target_instance() is None


def test_cavern_is_used_before_ornament_when_weekly_count_is_zero():
    targets = {
        "饰品提取": ["永恒笑剧"],
        "侵蚀隧洞": ["睿治之径"],
    }
    cfg = SimpleNamespace(
        build_target_use_user_instance_when_only_erosion_and_ornament=False,
        build_target_ornament_weekly_count=0,
    )

    with (
        patch.object(buildtarget, "cfg", cfg),
        patch.object(BuildTarget, "_initialized", True),
        patch.object(BuildTarget, "_target_instances", targets),
    ):
        assert BuildTarget.get_target_instance() == ("侵蚀隧洞", "睿治之径")
