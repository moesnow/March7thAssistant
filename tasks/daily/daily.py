from module.logger import log
from module.config import cfg
from module.config.platform import get_control_backend
from module.game import cloud_game
from utils.date import Date
from module.overview import plan
from tasks.base.task_steps import optional_reward, run_steps
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


def _run_desktop_extra(name, action):
    if not plan.desktop_extra_supported(lambda: get_control_backend(cfg), cloud_game.is_headless):
        log.info(f"当前环境不支持{name}，本轮跳过")
        return
    return action()


class Daily:
    @staticmethod
    def support_demand(*, full_run=False):
        if not plan.support_query_enabled(cfg, full_run=full_run):
            return SupportDemand()
        with optional_reward("支援实训查询"):
            activity, tasks, _ = Quest.scan(collect=False)
            return SupportDemand(needs_action(activity, tasks) and tasks.get(SUPPORT_TASK, False))
        return SupportDemand()

    @staticmethod
    def prepare_daily(ignore_refresh=False, *, only=None):
        demand = SupportDemand()

        def lookup():
            demand.pending = Daily.support_demand(full_run=not ignore_refresh).pending

        actions = {
            "redemption": Redemption.get,
            "relic_cleanup": Power.run_weekly_relic_cleanup,
            "build_target": BuildTarget.init_build_targets,
            "support": lookup,
            "activity": lambda: activity.start(support=demand),
            "echo": lambda: Echoofwar.start(support=demand),
            "power": lambda: Power.run(skip_weekly_cleanup=True, support=demand),
        }
        steps = plan.select_steps(plan.PREPARATION, cfg, actions, full_run=not ignore_refresh, only=only)
        return run_steps(steps) if steps or only is None else False

    @staticmethod
    def routine():
        from utils.runs import observe_step
        return run_steps((
            ("日常准备", lambda: Daily.prepare_daily(ignore_refresh=True)),
            ("日常领奖", observe_step("reward", reward.start)),
            ("每日实训", observe_step("daily", Daily.run)),
        ))

    @staticmethod
    def run_standalone():
        return run_steps((
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
        remaining_runs = plan.remaining_runs(target_count, completed_count)
        if not remaining_runs:
            log.info(f"差分宇宙固定次数（{cycle_label}）已完成 {completed_count}/{target_count}，跳过执行")
            cfg.save_timestamp("universe_timestamp")
            return

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
    def start(*, only=None):
        actions = {
            "prepare": Daily.prepare_daily if only is None else lambda: Daily.prepare_daily(only=only),
            "resin": Synthesis.self_molding_resin,
            "ember": EmberExchange.start,
            "currencywars": Daily._run_currency_wars,
            "weekly_divergent": Daily._run_weekly_divergent,
            "fight": lambda: _run_desktop_extra("锄大地", Fight.start),
            "divergent_count": lambda: Daily._run_scheduled_divergent_universe(DivergentUniverse()),
            "universe": lambda: _run_desktop_extra("模拟宇宙", Universe.start),
            "forgottenhall": lambda: challenge.start("memoryofchaos"),
            "purefiction": lambda: challenge.start("purefiction"),
            "apocalyptic": lambda: challenge.start("apocalyptic"),
            "lc3": Synthesis.lc3star_superimpose,
            "reward": reward.start,
            "daily": lambda: Daily.run(full_run=True),
        }
        steps = plan.select_steps(plan.main_order(cfg), cfg, actions, only=only)
        return run_steps(steps) if steps or only is None else False

    @staticmethod
    def _run_currency_wars():
        return CurrencyWars().start(weekly=True)

    @staticmethod
    def _run_weekly_divergent():
        divergent = DivergentUniverse()
        for _ in range(3):
            if divergent.check_divergent_universe_score():
                return True
            # 未完成对局也可能结算本周积分。按周奖励状态判断是否继续补打。
            divergent.start()
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
