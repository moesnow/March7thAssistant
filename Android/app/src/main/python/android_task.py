"""Chaquopy 入口。游戏任务、界面图、OCR 和 Android 控制器都来自仓库。"""
from functools import lru_cache
from hashlib import file_digest
import importlib
import json
import logging
import os
from pathlib import Path
import sys
import time
import traceback


_MODELS = {
    "Det": ("ch_PP-OCRv4_det_infer.onnx", "d2a7720d45a54257208b1e13e36a8479894cb74155a5efe29462512d42f49da9"),
    "Rec": ("ch_PP-OCRv4_rec_infer.onnx", "48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b"),
    "Cls": ("ch_ppocr_mobile_v2.0_cls_infer.onnx", "e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c"),
}

# 与 main.py 的 touch_actions 保持一致，tests/test_tasks/test_android_entry.py 会对照。
TASK_TARGETS = {
    "ROUTINE": ("tasks.touch.rewards", "routine"),
    "DAILY": ("tasks.touch.rewards", "run_daily_training"),
    "POWER": ("tasks.touch.power", "run_standalone"),
}
# 单任务入口的步骤名，与 routine 里的步骤名相同。
SINGLE_STEPS = {"DAILY": "每日实训", "POWER": "清体力"}
PROGRESS_KEYS = ("power_plan", "last_run_timestamp", "echo_of_war_timestamp")
# 手机上固定的配置。game_optimization_enable 只用来放行自动战斗检测。
FIXED_SETTINGS = {
    "control_backend": "adb",
    "ui_profile": "touch_720",
    "notification_enable": False,
    "game_optimization_enable": True,
}
# Kotlin 的 TaskConfig.toSettings() 每轮都写全这些键，界面契约里有对照表。
SETTING_KEYS = frozenset({
    "power_enable", "power_plan", "power_plan_keep", "power_plan_continue",
    "instance_type", "instance_names", "use_reserved_trailblaze_power", "use_fuel",
    "instance_team_enable", "instance_team_number", "instance_teams",
    "borrow_enable", "borrow_character_enable", "borrow_friends", "borrow_scroll_times",
    "echo_of_war_enable", "echo_of_war_start_day_of_week",
    "tp_before_instance", "relic_bag_cleanup_enable", "instance_names_challenge_count", "auto_battle_detect_enable",
    "reward_enable", "reward_dispatch_enable", "reward_mail_enable", "reward_assist_enable",
    "reward_quest_enable", "reward_srpass_enable", "reward_message_enable",
    "daily_enable", "daily_material_enable",
})


def build_settings(payload):
    """校验 Kotlin 传来的设置，多键或少键都报错，再叠加固定配置。"""
    values = json.loads(payload)
    if not isinstance(values, dict):
        raise ValueError("任务设置应为 JSON 对象")
    missing = SETTING_KEYS - values.keys()
    extra = values.keys() - SETTING_KEYS
    if missing or extra:
        raise ValueError(f"任务设置的键与约定不符：缺少 {sorted(missing)}，多出 {sorted(extra)}")
    return {**values, **FIXED_SETTINGS}


@lru_cache(maxsize=1)
def _ocr_parameters():
    import rapidocr

    model_dir = Path(rapidocr.__file__).parent / "models"
    params = {
        "Global.model_root_dir": str(model_dir),
        "EngineConfig.onnxruntime.intra_op_num_threads": 2,
        "EngineConfig.onnxruntime.inter_op_num_threads": 1,
    }
    for task, (name, expected) in _MODELS.items():
        path = model_dir / name
        with path.open("rb") as model:
            if file_digest(model, "sha256").hexdigest() != expected:
                raise ValueError(f"OCR 模型校验失败：{name}")
        params[f"{task}.model_path"] = str(path)
    return params


class _TaskLog(logging.Handler):
    """把任务日志转给 Kotlin，并记下当前步骤里最后一条错误，作为这一步失败的原因。"""

    def __init__(self, bridge):
        super().__init__(logging.INFO)
        self.bridge = bridge
        self.step = None
        self.last_error = None

    def begin_step(self, name):
        self.step = name
        self.last_error = None

    def emit(self, record):
        title = getattr(record, "section_title", None)
        message = title if title is not None else self.format(record)
        if record.levelno >= logging.ERROR:
            level = "ERROR"
            # run_steps 补的「<步骤名>未完成」不含原因，保留它之前的那条。
            if title is None and message != f"{self.step}未完成":
                self.last_error = message
        elif record.levelno >= logging.WARNING:
            level = "WARNING"
        else:
            level = "INFO"
        self.bridge.log(int(record.created * 1000), level, "TASK", message, title is not None)


class _AppSession:
    def __init__(self, client, bridge):
        self.client = client
        self.bridge = bridge

    def request(self, command, **params):
        from utils.pause import RunStopRequested

        if self.bridge.isCancelled() and params.get("action") != "up":
            raise RunStopRequested()
        return self.client.request(command, **params)

    def record_event(self, event):
        name = event["event"]
        if name in {"game_exited", "recovery_failed"} or (name == "move_back_failed" and event.get("final")):
            level = "ERROR"
        elif name in {"watchdog_error", "manual_action_required", "move_back_failed",
                      "move_back_frame_timeout", "frames_stalled", "relaunch_failed"}:
            level = "WARNING"
        else:
            level = "INFO"
        self.bridge.log(int(time.time() * 1000), level, "DEVICE", f"ADB 看门狗 {name}：{event}", False)
        if name == "watchdog_started":
            display = (event.get("task") or {}).get("display_id")
        elif name == "task_display_changed":
            display = event.get("to")
        else:
            display = event.get("display_id")
        self.bridge.gameEvent(name, display if display is not None else -1)

    def is_game_running(self):
        status, _ = self.request("status")
        return status["watchdog"].get("pid", -1) > 0

    def close(self):
        try:
            if not self.client.closed:
                self.client.request("shutdown", timeout=2)
        finally:
            self.client.close()


def run(workdir, token, sdk, version, model, is_emulator, task, settings, panel_off, mute_game, language, bridge):
    os.chdir(workdir)
    if workdir not in sys.path:
        sys.path.insert(0, workdir)
    os.environ["MARCH7TH_NON_INTERACTIVE"] = "1"

    from module.config import cfg
    from module.localization import load_language
    from module.logger import log
    from utils.pause import RunStopRequested

    handler = _TaskLog(bridge)
    loggers = (log.logger, log.logger_title)
    for logger in loggers:
        logger.addHandler(handler)
    controller = session = ocr = None
    configured = False

    def report_progress():
        try:
            bridge.reportProgress(json.dumps({key: getattr(cfg, key) for key in PROGRESS_KEYS}, ensure_ascii=False))
        except Exception as error:
            log.warning(f"未能把任务进度交回 App：{error}")

    try:
        if bridge.isCancelled():
            raise RunStopRequested()
        module_name, entry = TASK_TARGETS[task]
        cfg.set_values(build_settings(settings))

        # 每批结算先写入配置，再交回 App，缩短任务进程被杀时的进度丢失窗口。
        set_value = cfg.set_value
        had_set_value_override = "set_value" in vars(cfg)

        def set_value_and_report(key, value):
            result = set_value(key, value)
            if key in PROGRESS_KEYS:
                report_progress()
            return result

        cfg.set_value = set_value_and_report
        configured = True
        load_language(language)

        from module.game import get_game_controller
        from module.game.adb_ready import wait_for_game
        from module.game.adb_transport import (
            GAME_PACKAGE, AdbDevice, AdbEnvironment, AdbError, ServiceClient, check_service_hello)
        from module.ocr import ocr
        target = getattr(importlib.import_module(module_name), entry)

        # 等 Python 模块可用再请 Kotlin 启动设备端服务，避免冷导入耗尽握手期限。
        started = time.monotonic()
        ocr.instance_ocr(force_onnx=True, runtime_params=_ocr_parameters())
        log.info(f"OCR 运行时就绪，用时 {time.monotonic() - started:.2f} 秒")

        port = bridge.openDevice()
        if bridge.isCancelled():
            raise RunStopRequested()
        session = _AppSession(ServiceClient(port, token), bridge)
        check_service_hello(session.client.hello)
        environment = AdbEnvironment(None, AdbDevice("android", "device", model), sdk, version,
                                     "physical", (0, 0), True, is_emulator)
        controller = get_game_controller("adb")
        controller.attach_virtual_session(environment, session, on_event=session.record_event)
        display_id = controller.prepare_display()
        bridge.displayReady(display_id)
        log.info(f"已创建 1280×720 虚拟屏，display {display_id}")
        if "keep_awake" in session.client.hello.get("features", ()):
            try:
                session.request("keep_awake", on=True)
            except AdbError as error:
                log.warning(f"未能保持系统唤醒：{error}")
        else:
            log.warning("设备端服务不支持保持系统唤醒")
        # 关闭时也发一次，让设备端修复旧版本留下的静音记录。静音失败不影响任务。
        try:
            result, _ = session.request("mute", package=GAME_PACKAGE, on=mute_game)
            if mute_game:
                log.info("已静音游戏，任务结束后恢复")
            elif result["original_mode"] == "ignore":
                log.warning("系统设置里游戏的声音已被关闭，小助手不会改动它")
        except AdbError as error:
            log.warning(f"未能设置游戏静音：{error}")
        started = time.monotonic()
        controller.start_game_process()
        wait_for_game(controller, min(cfg.start_game_timeout * 60, 180))
        log.info(f"游戏画面就绪，用时 {time.monotonic() - started:.1f} 秒")
        bridge.gameReady()
        if panel_off:
            result, _ = session.request("screen_power", on=False)
            bridge.panelChanged(result["panel_off"])
            log.info("已关闭实体面板，保持系统唤醒")

        summary = None

        def keep_summary(text):
            nonlocal summary
            summary = text

        def report_step(name, state, step_summary=None):
            if state == "started":
                handler.begin_step(name)
                detail = None
            elif state == "succeeded":
                detail = step_summary
            else:
                detail = handler.last_error
            bridge.reportStep(name, state, detail)

        # 与 Windows 的触屏入口相同：返回值不是 False 就算成功。
        if task == "ROUTINE":
            succeeded = target(on_summary=keep_summary, on_step=report_step)
        else:
            # Windows 的单任务入口不经过 run_steps，这里只在前后各报一次。
            step = SINGLE_STEPS[task]
            report_step(step, "started")
            succeeded = target(on_summary=keep_summary)
            report_step(step, "failed" if succeeded is False else "succeeded", summary)
        if bridge.isCancelled():
            return "stopped"
        if succeeded is False:
            return "task_failed"
        if summary:
            bridge.reportSummary(summary)
        return "success"
    except RunStopRequested:
        log.info("任务已停止")
        return "stopped"
    except Exception as error:
        if bridge.isCancelled():
            return "stopped"
        log.error(traceback.format_exc())
        return getattr(error, "code", "runtime_error")
    finally:
        if configured:
            if had_set_value_override:
                cfg.set_value = set_value
            else:
                del cfg.set_value
            report_progress()
        bridge.cleaning()
        try:
            if controller is not None:
                controller.close()
            if session is not None and not session.client.closed:
                session.close()
        except Exception as error:
            log.warning(f"设备端连接结束：{error}")
        finally:
            if ocr is not None:
                ocr.exit_ocr()
            for logger in loggers:
                logger.removeHandler(handler)
