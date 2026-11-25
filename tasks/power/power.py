from module.automation import auto
from module.config import cfg
from module.localization import get_raw_instance_names
from module.logger import log
from module.screen import screen
from tasks.base.task_steps import FATAL_GAME_ERRORS, run_steps
from tasks.daily.buildtarget import BuildTarget
from tasks.power.instance import ChallengePageUnavailable, Instance, TeamPresetUnavailable
from tasks.power.policy import (
    ECHO, ORNAMENT, INSTANCE_LIMITS, BattleDefeat, InstanceTeamUnavailable, InstanceUnavailable, RelicBagFull,
    PowerError, SupportDemand,
    DEFEAT_RETRIES, batch_limit, parse_pc_power, plan_paid_batch, remaining_plan, run_plan,
)
from tasks.power.readout import read_immersifier_stock, read_number
from tasks.power.supplement import supplement
from tasks.power.team import restore_main
from tasks.power.weekly_relic_cleanup import WeeklyRelicCleanup
from utils.date import Date
from module.overview.plan import relic_due
from module.overview.readings import save_reading


MAP_POWER = (1588 / 1920, 35 / 1080, 198 / 1920, 56 / 1080)
GUIDE_IMMERSIFIERS = (1623 / 1920, 40 / 1080, 162 / 1920, 52 / 1080)


class Power:
    @staticmethod
    def run(skip_weekly_cleanup=False, *, support=None):
        if not skip_weekly_cleanup:
            Power.run_weekly_relic_cleanup()
        lookup_ok = True
        if support is None:
            from tasks.daily.daily import Daily

            support = SupportDemand()

            def query_support():
                support.pending = Daily.support_demand().pending

            lookup_ok = run_steps((("查询支援实训", query_support),))

        log.hr("开始清体力", 0)
        plan = remaining_plan(cfg)
        if plan:
            complete = Power.execute_power_plan(support=support)
            if not complete or not cfg.power_plan_continue:
                return lookup_ok

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
            return lookup_ok
        Power.process(instance_type, instance_name, support=support)
        log.hr("完成", 2)
        return lookup_ok

    @staticmethod
    def run_weekly_relic_cleanup():
        if relic_due(cfg):
            if not WeeklyRelicCleanup.run():
                raise RuntimeError("每周遗器清理未完成")
            cfg.save_timestamp("weekly_relic_cleanup_timestamp")

    @staticmethod
    def execute_power_plan(*, support=None):
        plan = remaining_plan(cfg)
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
    def process_immersifier_only():
        name = cfg.instance_names[ORNAMENT]
        try:
            if cfg.build_target_enable:
                for target_type, target_name in BuildTarget.get_target_instances():
                    if target_type == ORNAMENT:
                        name = target_name
                        break
        except Exception as error:
            log.warning(f"获取培养目标副本失败，使用配置的副本：{error}")
        return Power.process(ORNAMENT, name, immersifier_only=True)

    @staticmethod
    def _run_instance(instance_type, name, planned, *, support=None, immersifier_only=False):
        """逐批挑战。结束时记下剩余的开拓力，总览从这个数估算恢复。"""
        balance = []
        try:
            yield from Power._run_batches(instance_type, name, planned, balance, support=support,
                                          immersifier_only=immersifier_only)
        finally:
            if balance:
                save_reading(cfg, "overview_power", balance[-1])

    @staticmethod
    def _run_batches(instance_type, name, planned, balance, *, support=None, immersifier_only=False):
        if (instance_type not in INSTANCE_LIMITS
                or not name or name not in get_raw_instance_names().get(instance_type, {}) or name == "无"):
            raise PowerError(f"未配置有效的副本：{instance_type} · {name}")

        support = support if support is not None else SupportDemand()
        cost_per_wave, _ = INSTANCE_LIMITS[instance_type]
        limit = batch_limit(cfg, instance_type)
        is_echo = instance_type == ECHO
        is_ornament = instance_type == ORNAMENT
        only_immersifiers = is_ornament and immersifier_only
        rewards = Instance.read_echo_rewards() if is_echo else None
        if rewards == 0:
            cfg.save_timestamp("echo_of_war_timestamp")
            if planned is None:
                log.info("历战余响本周奖励次数已用完")
                return
        immersifiers = Power.get_immersifier_count() if is_ornament else 0
        available = 0
        if rewards != 0 and not only_immersifiers:
            available = Power.get(use_supplement=not immersifier_only)
        if rewards != 0 and not immersifiers and available < cost_per_wave:
            log.info("饰品提取资源不足，结束本副本项" if is_ornament else "开拓力不足，结束本副本项")
            return

        remaining = planned
        completed = 0
        # Opt-in PC feature. Explicitly pending support training still needs a
        # real battle; afterwards the remaining paid waves may use tickets.
        quick_enabled = (getattr(cfg, "prefer_fuel_tickets", False) is True
                         and not immersifier_only
                         and instance_type in ("拟造花萼（金）", "拟造花萼（赤）", "凝滞虚影"))

        def quick_batches():
            nonlocal available, remaining, quick_enabled, completed
            if not quick_enabled or support.pending:
                return
            from tasks.power.fuel_ticket_ui import PCFuelTicketScreen
            display_name = (get_raw_instance_names()[instance_type][name].replace("2", "")
                            if instance_type == "拟造花萼（赤）" else name)
            ui = PCFuelTicketScreen(auto, Instance, display_name)
            while available >= cost_per_wave and (remaining is None or remaining > 0):
                requested = available // cost_per_wave if remaining is None else min(remaining, available // cost_per_wave)
                from utils.runs import DETAIL_TEXT, publish_detail
                publish_detail(DETAIL_TEXT["instance"], name=name, index=completed + 1, total=planned or completed + requested)
                done = (ui.run_batch(instance_type, name, available, requested)
                        if getattr(cfg, "fuel_ticket_batch_enable", False) is True
                        else ui.run_one(instance_type, name, available))
                if not done:
                    quick_enabled = False
                    log.info("助燃券速刷不可用，保留剩余计划并回退普通战斗")
                    break
                completed += done
                available -= done * cost_per_wave
                balance.append(available)
                if remaining is not None:
                    remaining -= done
                log.info(f"助燃券已确认结算 {done} 次")
                # Persist the confirmed paid run before closing the result UI.
                yield done
                ui.close_receipt()

        yield from quick_batches()
        if remaining == 0 or (rewards != 0 and not immersifiers and available < cost_per_wave):
            screen.change_to("main")
            return

        world_team = False
        team_failure = None
        if cfg.tp_before_instance:
            # 锚点恢复作用于主世界出战队伍，沿用 PC 已有的先切队再恢复顺序。
            if cfg.instance_team_enable and not is_ornament:
                team_failure = Instance.select_world_team(instance_type, name)
                world_team = team_failure is None
            Instance.heal_teams()

        def enter():
            for attempt in range(1, 4):
                try:
                    if Instance.prepare_instance(instance_type, name):
                        return
                    raise PowerError(f"未能进入副本 {name}")
                except FATAL_GAME_ERRORS:
                    raise
                except RuntimeError as error:
                    if isinstance(error, InstanceUnavailable) or attempt == 3:
                        if team_failure and isinstance(error, PowerError):
                            Instance.check_team_connection()
                            restore_main(screen, name)
                            raise InstanceTeamUnavailable(f"{name}：未确认进入原定副本，已跳过本项（{error}）") from error
                        raise
                    log.warning(f"进入副本失败，重试 {attempt}/2：{error}")

        previous = 0
        borrowed = False
        enter()
        retries = 0
        cleaned = False
        while remaining is None or remaining > 0:
            from utils.runs import DETAIL_TEXT, publish_detail
            practice = rewards == 0
            total = planned or (completed + min(rewards, available // cost_per_wave) if is_echo else
                                completed + immersifiers + available // cost_per_wave)
            if total > completed:
                publish_detail(DETAIL_TEXT["instance"], name=name, index=completed + 1, total=total)
            requested = limit if remaining is None else min(limit, remaining)
            if quick_enabled and support.pending and getattr(cfg, "borrow_enable", False):
                # Only one real battle is needed for support training. The
                # rest of the paid plan should remain eligible for tickets.
                requested = min(requested, 1)
            if practice:
                if planned is None:
                    break
                waves, cost, used_immersifiers = 1, 0, 0
            else:
                if is_echo:
                    requested = min(requested, rewards)
                waves, cost, used_immersifiers = plan_paid_batch(requested, available, cost_per_wave, immersifiers=immersifiers)
            if not waves:
                log.info("饰品提取资源不足，结束本副本项" if is_ornament else "开拓力不足，结束本副本项")
                break

            repeated = not practice and previous == waves and (not support.pending or borrowed)
            try:
                if repeated:
                    Instance.start_instance_again()
                else:
                    if previous:
                        Instance.complete_run(instance_type)
                        enter()
                        previous = 0
                    for attempt in range(1, 4):
                        try:
                            selected = Instance.select_waves(instance_type, waves)
                            if selected != waves:
                                # 支持只提供单场挑战的历战余响界面。
                                waves, cost = selected, selected * cost_per_wave
                            borrowed = Instance.start_instance(
                                instance_type, name, support, practice=practice, world_team=world_team,
                                team_failure=team_failure,
                            )
                        except ChallengePageUnavailable as error:
                            if attempt == 3:
                                if team_failure:
                                    raise InstanceTeamUnavailable(f"{name}：{error}，已跳过本项") from error
                                raise
                            log.warning(f"开打前准备失败，重新进入副本 {attempt}/2：{error}")
                            # 先退出当前页面，重新进入后从默认一场设置波次。
                            screen.change_to("main", max_recursion=1)
                            enter()
                        else:
                            break
                if not Instance.wait_fight(repeated=repeated):
                    Instance.exit_defeat()
                    raise BattleDefeat("副本挑战失败")
            except TeamPresetUnavailable as error:
                log.info(f"{name}：{error}，改用主世界切队")
                restore_main(screen, name, leave_team=Instance.leave_challenge_team)
                team_failure = Instance.select_world_team(instance_type, name)
                world_team = team_failure is None
                enter()
                continue
            except InstanceTeamUnavailable:
                restore_main(screen, name, leave_team=Instance.leave_challenge_team)
                raise
            except BattleDefeat:
                if retries >= DEFEAT_RETRIES:
                    raise
                retries += 1
                log.warning(f"已确认战败，重试 {retries}/{DEFEAT_RETRIES}")
                enter()
                previous = 0
                continue
            except RelicBagFull:
                if cleaned or not Instance.clean_full_bag():
                    raise
                cleaned = True
                enter()
                previous = 0
                continue

            was_support_pending = support.pending
            support.won(borrowed)
            available -= cost
            if cost:
                balance.append(available)
            immersifiers -= used_immersifiers
            completed += waves
            yield waves
            log.info(f"已结算 {waves} 次")
            previous, retries = waves, 0
            if remaining is not None:
                remaining -= waves
            if (quick_enabled and was_support_pending and not support.pending
                    and (remaining is None or remaining > 0) and available >= cost_per_wave):
                Instance.complete_run(instance_type)
                previous = 0
                yield from quick_batches()
                if remaining == 0 or available < cost_per_wave:
                    break
                enter()
            if is_echo and not practice:
                rewards -= waves
                if rewards == 0:
                    cfg.save_timestamp("echo_of_war_timestamp")
                Instance.complete_run(instance_type)
                previous = 0
                if rewards == 0 and planned is None:
                    return
                if remaining != 0 and (rewards == 0 or available >= cost_per_wave):
                    enter()

        if previous:
            Instance.complete_run(instance_type)
        else:
            screen.change_to("main")

    @staticmethod
    def get_immersifier_count():
        screen.change_to("guide3")
        return read_immersifier_stock(auto, GUIDE_IMMERSIFIERS)

    @staticmethod
    def get(use_supplement=False):
        screen.change_to("map")

        def read():
            return read_number(auto, MAP_POWER, parse_pc_power, "未能确认当前开拓力")

        balance = read()
        if use_supplement:
            balance = supplement(auto, screen, cfg, balance, lambda: auto.find_element(
                "./assets/images/share/power/trailblaze_power/trailblaze_power.png", "image", 0.9, crop=MAP_POWER,
            ), read, return_screen="map", desktop=True)
        save_reading(cfg, "overview_power", balance)
        log.info(f"开拓力：{balance}/300")
        return balance
