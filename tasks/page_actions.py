"""Manual task details run inside the existing exclusive routine process."""
from module.overview import plan
from module.task_catalog import BY_ID
from utils.runs import observe_step


def run_page(page_id, config, *, touch=False):
    from tasks.base.task_steps import run_steps

    switches = BY_ID[page_id].switches
    if page_id == "echo":
        switches += ("power_enable",)
    with config.standalone_switches(switches):
        if touch:
            from tasks.touch import rewards
            if page_id == "reward":
                return observe_step("reward", rewards.run)()
            if page_id == "daily":
                return observe_step("daily", rewards.run_daily_training)()
            if page_id == "echo":
                return rewards.routine(only="echo")
            return False
        from tasks.daily.daily import Daily
        if page_id in ("echo", "activity"):
            return Daily.prepare_daily(ignore_refresh=True, only=page_id)
        if page_id == "daily":
            return observe_step("daily", Daily.run_standalone)()
        if page_id == "reward":
            from tasks.daily.redemption import Redemption
            from tasks.reward import start
            from tasks.reward.quest import Quest
            steps = []
            if config.reward_redemption_code_enable:
                steps.append(("兑换码", observe_step("redemption", Redemption.get)))
            steps.append(("日常领奖", observe_step("reward", start)))
            if config.reward_quest_enable:
                steps.append(("每日实训奖励", Quest.settle))
            return run_steps(steps)
        if page_id == "assets":
            from tasks.daily.synthesis import Synthesis
            from tasks.daily.ember_exchange import EmberExchange
            from tasks.power.power import Power
            actions = {"relic_cleanup": Power.run_weekly_relic_cleanup, "resin": Synthesis.self_molding_resin,
                       "ember": EmberExchange.start, "lc3": Synthesis.lc3star_superimpose}
            return run_steps(plan.select_steps(tuple(actions), config, actions))
    return False
