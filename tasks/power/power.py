from module.automation import auto
from module.config import cfg
from module.localization import get_raw_instance_names
from module.logger import log
from module.screen import screen
from tasks.daily.buildtarget import BuildTarget
from tasks.power.instance import Instance, TeamPresetUnavailable
from tasks.power.policy import (
    ECHO, ORNAMENT, INSTANCE_LIMITS, BattleDefeat, RelicBagFull, PowerError, SupportDemand,
    DEFEAT_RETRIES, batch_limit, check_balance, parse_power, run_plan,
)
from tasks.power.readout import read_number
from tasks.power.supplement import supplement
from tasks.power.weekly_relic_cleanup import WeeklyRelicCleanup
from utils.date import Date
import time


MAP_POWER = (1588 / 1920, 35 / 1080, 198 / 1920, 56 / 1080)


class Power:
    @staticmethod
    def run(skip_weekly_cleanup=False, *, support=None):
        if not skip_weekly_cleanup:
            Power.run_weekly_relic_cleanup()
        if support is None:
            from tasks.daily.daily import Daily

            support = Daily.support_demand()

        log.hr("开始清体力", 0)
        plan = cfg.power_plan
        if plan:
            complete = Power.execute_power_plan(support=support)
            if not complete or not cfg.power_plan_continue:
                return True

        instance_type = cfg.instance_type
        instance_name = cfg.instance_names.get(instance_type)
        if cfg.build_target_enable:
            try:
                if target := BuildTarget.get_target_instance():
                    instance_type, instance_name = target
                    log.info(f"使用培养目标副本：{instance_type} · {instance_name}")
            except Exception as error:
                log.warning(f"获取培养目标副本失败，使用配置的副本：{error}")
        if instance_name == "无":
            log.info(f"{instance_type}未开启")
            return True
        Power.process(instance_type, instance_name, support=support)
        log.hr("完成", 2)
        return True

    @staticmethod
    def run_weekly_relic_cleanup():
        if (cfg.get_value("break_down_level_four_relicset", False)
                and Date.is_weekly_day_due(
                    cfg.get_value("weekly_relic_cleanup_timestamp", 0),
                    cfg.get_value("weekly_relic_cleanup_day_of_week", 1),
                    cfg.refresh_hour,
                )):
            if not WeeklyRelicCleanup.run():
                raise RuntimeError("每周遗器清理未完成")
            cfg.save_timestamp("weekly_relic_cleanup_timestamp")

    @staticmethod
    def execute_power_plan(*, support=None):
        plan = cfg.power_plan
        if not plan:
            return False
        return run_plan(cfg, plan, lambda kind, name, count: Power._run_instance(kind, name, count, support=support))

    @staticmethod
    def process(instance_type, instance_name, planned_attempts=0, immersifier_only=False, *, support=None):
        """供活动、周常和默认刷取使用，返回确认完成的挑战次数。"""
        if instance_name == "无":
            return 0
        return sum(Power._run_instance(
            instance_type, instance_name, planned_attempts or None, support=support, immersifier_only=immersifier_only,
        ))

    @staticmethod
    def _run_instance(instance_type, name, planned, *, support=None, immersifier_only=False):
        if (instance_type not in INSTANCE_LIMITS
                or not name or name not in get_raw_instance_names().get(instance_type, {}) or name == "无"):
            raise PowerError(f"未配置有效的副本：{instance_type} · {name}")

        support = support if support is not None else SupportDemand()
        cost_per_wave, _ = INSTANCE_LIMITS[instance_type]
        limit = batch_limit(cfg, instance_type)
        is_echo = instance_type == ECHO
        is_ornament = instance_type == ORNAMENT
        rewards = Instance.read_echo_rewards() if is_echo else None
        if rewards == 0:
            cfg.save_timestamp("echo_of_war_timestamp")
            if planned is None:
                log.info("历战余响本周奖励次数已用完")
                return
        practice = rewards == 0
        balance = Power.get(use_supplement=not practice and not immersifier_only)
        if not practice and not is_ornament and balance < cost_per_wave:
            log.info("开拓力不足，结束本副本项")
            return

        world_team = False
        if cfg.tp_before_instance:
            # 锚点恢复作用于主世界出战队伍，沿用 PC 已有的先切队再恢复顺序。
            if cfg.instance_team_enable and not is_ornament:
                Instance.select_world_team(instance_type, name)
                world_team = True
            Instance.heal_teams()

        def enter():
            if not Instance.prepare_instance(instance_type, name):
                raise PowerError(f"未能进入副本 {name}")

        enter()
        remaining = planned
        previous = 0
        borrowed = False
        available = Instance.read_balance(instance_type)
        retries = 0
        cleaned = False
        while remaining is None or remaining > 0:
            practice = rewards == 0
            requested = limit if remaining is None else min(limit, remaining)
            if not is_ornament:
                if not practice:
                    requested = min(requested, available // cost_per_wave)
                    if is_echo:
                        requested = min(requested, rewards)
                elif planned is None:
                    break
                else:
                    requested = 1
            if not requested:
                log.info("开拓力不足，结束本副本项")
                break

            started = time.monotonic()
            repeated = False
            try:
                if previous == requested and (not support.pending or borrowed):
                    payment = Instance.repeat_payment(instance_type, requested, practice)
                    if payment is not None and payment <= available and (not immersifier_only or payment == 0):
                        Instance.start_instance_again(practice)
                        waves, cost = requested, payment
                        repeated = True

                if not repeated:
                    if previous:
                        Instance.complete_run(instance_type)
                        enter()
                        previous = 0
                        available = Instance.read_balance(instance_type)
                    waves, cost = Instance.prepare_payment(
                        instance_type, requested, available, practice=practice, immersifier_only=immersifier_only,
                    )
                    if not waves:
                        break
                    borrowed = Instance.start_instance(
                        instance_type, name, support, practice=practice, world_team=world_team,
                    )
                if not Instance.wait_fight(repeated=repeated):
                    Instance.exit_defeat()
                    raise BattleDefeat("副本挑战失败")
            except TeamPresetUnavailable:
                log.info("改用主世界切换配置的队伍")
                screen.change_to("main", max_recursion=1)
                Instance.select_world_team(instance_type, name)
                world_team = True
                enter()
                available = Instance.read_balance(instance_type)
                continue
            except BattleDefeat:
                after = Power.get(use_supplement=False)
                check_balance(available, after, 0, time.monotonic() - started)
                if retries >= DEFEAT_RETRIES:
                    raise
                retries += 1
                log.warning(f"已确认战败且未扣费，重试 {retries}/{DEFEAT_RETRIES}")
                enter()
                previous = 0
                available = Instance.read_balance(instance_type)
                continue
            except RelicBagFull:
                if cleaned or not Instance.clean_full_bag():
                    raise
                cleaned = True
                enter()
                previous = 0
                available = Instance.read_balance(instance_type)
                continue

            completed = Instance.completed_waves(instance_type, waves)
            support.won(borrowed)
            yield completed
            after = Instance.read_balance(instance_type, result=True)
            if completed != waves:
                raise PowerError(f"实际结算 {completed}/{waves} 次，已保留确认的进度")
            check_balance(available, after, cost, time.monotonic() - started)
            log.info(f"已结算 {completed} 次，剩余开拓力 {after}/300")
            available, previous, retries = after, waves, 0
            if remaining is not None:
                remaining -= completed
            if is_echo and not practice:
                # 奖励额度读数取自游戏，不能仅凭胜场写入周常时间。
                Instance.complete_run(instance_type)
                previous = 0
                rewards = Instance.read_echo_rewards()
                if rewards == 0:
                    cfg.save_timestamp("echo_of_war_timestamp")
                    if planned is None:
                        return
                if remaining is None or remaining > 0:
                    enter()
                    available = Instance.read_balance(instance_type)

        if previous:
            Instance.complete_run(instance_type)
        else:
            screen.change_to("main")

    @staticmethod
    def get(use_supplement=False):
        screen.change_to("map")

        def read():
            return read_number(auto, MAP_POWER, parse_power, "未能确认当前开拓力")

        balance = read()
        if use_supplement:
            balance = supplement(auto, screen, cfg, balance, lambda: auto.click_element(
                "./assets/images/share/power/trailblaze_power/trailblaze_power.png", "image", 0.9, crop=MAP_POWER,
            ), read, return_screen="map")
        log.info(f"开拓力：{balance}/300")
        return balance
