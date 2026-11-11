from module.logger import log
from module.config import cfg
from module.screen import screen
from utils.date import Date
from tasks.base.task_steps import run_steps
from tasks.daily.photo import Photo
from tasks.weekly.currency_wars import CurrencyWars
from tasks.weekly.divergent_universe import DivergentUniverse
from tasks.daily.fight import Fight
from tasks.weekly.universe import Universe
import tasks.reward as reward
import tasks.activity as activity
from tasks.daily.synthesis import Synthesis
import tasks.challenge as challenge
from tasks.power.power import Power
from tasks.power.policy import SupportDemand
from tasks.daily.training import SUPPORT_TASK, MATERIAL_TASK, can_complete, needs_action
from tasks.reward.quest import Quest
from tasks.daily.himekotry import HimekoTry
from tasks.weekly.echoofwar import Echoofwar
from tasks.daily.buildtarget import BuildTarget
from tasks.daily.redemption import Redemption
from tasks.daily.ember_exchange import EmberExchange


class Daily:
    @staticmethod
    def support_demand(*, full_run=False):
        if not can_complete(cfg, full_run=full_run) or not cfg.borrow_enable or cfg.borrow_character_enable:
            return SupportDemand()
        activity, tasks, _ = Quest.scan(collect=False)
        return SupportDemand(needs_action(activity, tasks) and tasks.get(SUPPORT_TASK, False))

    @staticmethod
    def prepare_daily(ignore_refresh=False):
        steps = []
        demand = SupportDemand()

        def lookup():
            demand.pending = Daily.support_demand(full_run=not ignore_refresh).pending

        if cfg.reward_enable and cfg.reward_redemption_code_enable:
            steps.append(("兑换码", Redemption.get))
        if cfg.power_enable:
            steps.append(("每周遗器清理", Power.run_weekly_relic_cleanup))
        if cfg.build_target_enable:
            steps.append(("培养目标", BuildTarget.init_build_targets))
        has_power_activity = cfg.activity_enable and (cfg.activity_gardenofplenty_enable
                                                      or cfg.activity_realmofthestrange_enable
                                                      or cfg.activity_planarfissure_enable)
        if cfg.power_enable or has_power_activity:
            steps.append(("查询支援实训", lookup))

        steps.append(("活动", lambda: activity.start(support=demand)))
        if cfg.power_enable:
            if cfg.echo_of_war_enable and (ignore_refresh or Date.is_next_mon_x_am(cfg.echo_of_war_timestamp, cfg.refresh_hour)):
                steps.append(("历战余响", lambda: Echoofwar.start(support=demand)))
            steps.append(("清体力", lambda: Power.run(skip_weekly_cleanup=True, support=demand)))
        return run_steps(steps)

    @staticmethod
    def routine():
        return run_steps((
            ("日常准备", lambda: Daily.prepare_daily(ignore_refresh=True)),
            ("日常领奖", reward.start),
            ("每日实训", Daily.run),
        ))

    @staticmethod
    def _run_scheduled_divergent_universe(divergent: DivergentUniverse):
        target_count = int(cfg.universe_count)
        cycle = "weekly" if cfg.universe_frequency == "weekly" else "daily"
        cycle_label = "本周" if cycle == "weekly" else "今日"

        if target_count <= 0:
            log.info("差分宇宙固定次数为 0，跳过执行并记录本轮时间")
            cfg.save_timestamp("universe_timestamp")
            return

        completed_count = DivergentUniverse.get_recorded_run_count(cycle)
        if completed_count >= target_count:
            log.info(f"差分宇宙固定次数（{cycle_label}）已完成 {completed_count}/{target_count}，跳过执行")
            cfg.save_timestamp("universe_timestamp")
            return

        remaining_runs = target_count - completed_count
        log.info(f"差分宇宙固定次数进度（{cycle_label}）：{completed_count}/{target_count}，继续运行剩余 {remaining_runs} 次")

        for _ in range(remaining_runs):
            if not divergent.start(universe_type=cfg.divergent_type):
                log.warning(f"差分宇宙本轮未完成，不计入固定次数，下次将从 {cycle_label} {completed_count}/{target_count} 继续")
                return False

            completed_count = DivergentUniverse.get_recorded_run_count(cycle)
            log.info(f"差分宇宙固定次数（{cycle_label}）已完成 {completed_count}/{target_count}")

        cfg.save_timestamp("universe_timestamp")
        log.info("差分宇宙固定次数已全部完成，记录本轮执行时间")

    @staticmethod
    def start():
        steps = [("日常准备", Daily.prepare_daily)]

        if cfg.asset_manager_enable:
            if cfg.asset_self_molding_resin_enable and Date.is_next_month_x_am(cfg.asset_self_molding_resin_timestamp, cfg.refresh_hour):
                steps.append(("合成自塑尘脂", Synthesis.self_molding_resin))
            if any(cfg.get_value(item.enable_key, False) for item in EmberExchange.ITEMS):
                steps.append(("余烬兑换", EmberExchange.start))

        if cfg.currencywars_enable and Date.is_next_mon_x_am(cfg.currencywars_timestamp, cfg.refresh_hour):
            steps.append(("货币战争", Daily._run_currency_wars))

        if cfg.weekly_divergent_enable and Date.is_next_mon_x_am(cfg.weekly_divergent_timestamp, cfg.refresh_hour):
            steps.append(("差分宇宙积分奖励", Daily._run_weekly_divergent))

        if cfg.fight_enable and Date.is_next_x_am(cfg.fight_timestamp, cfg.refresh_hour):
            steps.append(("锄大地", Fight.start))

        if cfg.universe_enable:
            due = Date.is_next_mon_x_am if cfg.universe_frequency == "weekly" else Date.is_next_x_am
            if due(cfg.universe_timestamp, cfg.refresh_hour):
                if cfg.universe_category == "divergent":
                    steps.append(("差分宇宙固定次数", lambda: Daily._run_scheduled_divergent_universe(DivergentUniverse())))
                else:
                    steps.append(("模拟宇宙", Universe.start))

        for name, mode, enabled, timestamp in (
            ("混沌回忆", "memoryofchaos", cfg.forgottenhall_enable, cfg.forgottenhall_timestamp),
            ("虚构叙事", "purefiction", cfg.purefiction_enable, cfg.purefiction_timestamp),
            ("末日幻影", "apocalyptic", cfg.apocalyptic_enable, cfg.apocalyptic_timestamp),
        ):
            if enabled and Date.is_next_mon_x_am(timestamp, cfg.refresh_hour):
                steps.append((name, lambda mode=mode: challenge.start(mode)))

        if cfg.asset_manager_enable and cfg.asset_lc3_star_superimpose_enable:
            steps.append(("三星光锥叠加", Synthesis.lc3star_superimpose))

        steps.extend((("日常领奖", reward.start), ("每日实训", lambda: Daily.run(full_run=True))))
        return run_steps(steps)

    @staticmethod
    def _run_currency_wars():
        war = CurrencyWars()
        screen.change_to("currency_wars_homepage")
        return war.check_currency_wars_score() or war.start()

    @staticmethod
    def _run_weekly_divergent():
        divergent = DivergentUniverse()
        screen.change_to("divergent_main")
        for _ in range(3):
            if divergent.check_divergent_universe_score():
                return True
            if divergent.start() is False:
                return False
            if not Date.is_next_mon_x_am(cfg.weekly_divergent_timestamp, cfg.refresh_hour):
                return True
        log.warning("尝试运行了多轮差分宇宙，但积分奖励仍未完成")
        return False

    @staticmethod
    def run(*, full_run=False):
        actions = []
        if cfg.daily_memory_one_enable:
            actions.extend((
                ("累计消灭20个敌人", lambda: challenge.start_memory_one(2)),
                ("完成1次「忘却之庭」", challenge.start_memory_one),
                ("单场战斗中，触发3种不同属性的弱点击破", challenge.start_memory_one),
                ("累计触发弱点击破效果5次", challenge.start_memory_one),
                ("利用弱点进入战斗并获胜3次", lambda: challenge.start_memory_one(3)),
                ("施放终结技造成制胜一击1次", challenge.start_memory_one),
            ))
        if cfg.daily_material_enable:
            actions.append((MATERIAL_TASK, Synthesis.material))
        actions.append(("拍照1次", Photo.photograph))
        if cfg.daily_himeko_try_enable:
            actions.extend((("累计施放2次秘技", HimekoTry.technique), ("累计击碎3个可破坏物", HimekoTry.item)))
        return Quest.settle(complete=can_complete(cfg, full_run=full_run), actions=actions)
