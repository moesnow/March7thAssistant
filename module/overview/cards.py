from module.localization import get_current_language, tr
from . import plan
from .types import PlanItem

STATUS_TEXT = {
    "pending": "将执行", "running": "进行中", "done_day": "今日已完成", "done_week": "本周已完成",
    "done_month": "本月已完成", "disabled": "未开启", "not_due": "未到执行日",
    "unsupported": "当前环境不支持", "claim_only": "仅检查奖励", "zero_count": "计划次数为零",
}
SUMMARY_TEXT = {
    "redemption": "检查新兑换码", "build_target": "读取培养目标", "support": "检查支援角色需求",
    "activity": "检查已开启的活动", "resin": "每月合成", "ember": "每月购买所选物品",
    "fight": "按配置路线运行", "lc3": "叠加三星光锥", "reward": "领取已开启的奖励",
    "daily": "检查实训活跃度",
}


OPTIONS = {
    "activity": {"activity_dailycheckin_enable": "每日签到", "activity_gardenofplenty_enable": "花藏繁生",
                 "activity_realmofthestrange_enable": "异器盈界", "activity_planarfissure_enable": "位面分裂",
                 "activity_journey_highlights_notification_enable": "活动热点通知"},
    "reward": {"reward_dispatch_enable": "委托", "reward_mail_enable": "邮件", "reward_assist_enable": "支援礼盒",
               "reward_srpass_enable": "无名勋礼", "reward_message_enable": "短信", "reward_achievement_enable": "成就"},
    "daily": {"daily_material_enable": "合成材料", "daily_memory_one_enable": "回忆一", "daily_himeko_try_enable": "试用姬子"},
}


def summary(key, cfg):
    if key in OPTIONS:
        selected = [tr(label) for switch, label in OPTIONS[key].items() if cfg.get_value(switch, False)]
        if selected:
            return " · ".join(selected[:2]) + ("…" if len(selected) > 2 else "")
    if key in SUMMARY_TEXT:
        return tr(SUMMARY_TEXT[key])
    if key == "power":
        if cfg.power_plan:
            return tr("体力计划 · {count} 项").format(count=len(cfg.power_plan))
        name = cfg.instance_names.get(cfg.instance_type, "")
        return tr(name) if name else tr(cfg.instance_type)
    if key in ("echo", "relic_cleanup"):
        day = cfg.echo_of_war_start_day_of_week if key == "echo" else cfg.weekly_relic_cleanup_day_of_week
        return tr("周{day}起执行").format(day=day)
    if key == "currencywars":
        return tr("速通模式") if cfg.currencywars_fast_mode else tr("每周积分奖励")
    if key == "weekly_divergent":
        return tr("难度 {level} · 周积分").format(level=cfg.weekly_divergent_level)
    if key in ("divergent_count", "universe"):
        label = tr("每周 {count} 次") if cfg.universe_frequency == "weekly" else tr("每天 {count} 次")
        return label.format(count=cfg.universe_count)
    levels = getattr(cfg, key + "_level")
    return tr("挑战第 {level} 层").format(level="–".join(map(str, levels)) if isinstance(levels, (tuple, list)) else levels)


def preview(config, now, *, touch=False, backend="local", current_step=None):
    rows = []
    for key in plan.plan_order(config, touch):
        step = plan.STEPS[key]
        state = plan.entry_state(key, config, touch=touch, now=now)
        if state == "pending":
            state = plan.detail_state(key, config, now=now, backend=backend, headless=lambda: config.browser_headless_enable)
        if key == current_step:
            state = "running"
        detail = summary(key, config)
        if get_current_language() in ("zh_CN", "zh_TW") and len(detail) > 16:
            detail = detail[:15] + "…"
        rows.append(PlanItem(key, tr(plan.STEP_NAMES[key]), step.icon, detail, state,
                             tr(STATUS_TEXT[state]), "setting:" + step.setting))
    return tuple(rows)
