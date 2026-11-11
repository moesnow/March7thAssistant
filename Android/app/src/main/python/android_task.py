"""Chaquopy 入口。游戏任务、界面图、OCR 和 Android 控制器都来自仓库。"""
from functools import lru_cache
from hashlib import file_digest
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
    def __init__(self, bridge):
        super().__init__(logging.INFO)
        self.bridge = bridge

    def emit(self, record):
        title = getattr(record, "section_title", None)
        if record.levelno >= logging.ERROR:
            level = "ERROR"
        elif record.levelno >= logging.WARNING:
            level = "WARNING"
        else:
            level = "INFO"
        self.bridge.log(int(record.created * 1000), level, "TASK",
                        title if title is not None else self.format(record), title is not None)


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


def run(workdir, token, sdk, version, model, is_emulator, tasks, config, language, bridge):
    os.chdir(workdir)
    if workdir not in sys.path:
        sys.path.insert(0, workdir)
    os.environ["MARCH7TH_NON_INTERACTIVE"] = "1"

    from module.config import cfg
    from module.localization import load_language, tr
    from module.logger import log
    from utils.pause import RunStopRequested

    handler = _TaskLog(bridge)
    loggers = (log.logger, log.logger_title)
    for logger in loggers:
        logger.addHandler(handler)
    controller = session = ocr = None
    try:
        if bridge.isCancelled():
            raise RunStopRequested()
        supports = [[str(key), ""] for key in config.supportKeys()]
        settings = {
            "control_backend": "adb",
            "ui_profile": "touch_720",
            "notification_enable": False,
            "reward_enable": True,
            "reward_quest_enable": config.getCollectRewards(),
            "reward_dispatch_enable": config.getDispatch(),
            "reward_mail_enable": config.getMail(),
            "reward_assist_enable": config.getAssist(),
            "reward_srpass_enable": config.getSrpass(),
            "reward_message_enable": config.getMessage(),
            "daily_enable": True,
            "daily_material_enable": config.getSynthesis(),
            "power_enable": True,
            "instance_team_enable": False,
            # 没选支援角色时不进支援列表，也不为支援实训多查一次任务卡。
            "borrow_enable": bool(supports),
            "borrow_character_enable": config.getBorrowAlways(),
            "borrow_friends": supports,
        }
        selected = set(tasks.split(","))
        if "POWER" in selected:
            settings.update(
                power_plan=[[config.getInstanceType().getTypeName(), config.getInstanceName(), config.getWaves()]],
                use_reserved_trailblaze_power=config.getReserve(),
                use_fuel=config.getFuel(),
            )
        cfg.set_values(settings)
        load_language(language)

        from module.game import get_game_controller
        from module.game.adb_ready import wait_for_game
        from module.game.adb_transport import (
            GAME_PACKAGE, AdbDevice, AdbEnvironment, AdbError, ServiceClient, check_service_hello)
        from module.ocr import ocr
        from tasks.touch import daily, power, rewards

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
        # 关闭时也发一次，让设备端修复旧版本留下的静音记录。静音失败不影响任务。
        mute = config.getMuteGame()
        try:
            result, _ = session.request("mute", package=GAME_PACKAGE, on=mute)
            if mute:
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
        if config.getPanelOff():
            result, _ = session.request("screen_power", on=False)
            bridge.panelChanged(result["panel_off"])
            log.info("已关闭实体面板，保持系统唤醒")
        # 顺序固定：先清体力，实训里消耗开拓力和支援的任务才能在最后一并领取。
        summaries = []
        succeeded = True
        if "POWER" in selected:
            support_pending = ("DAILY" in selected and cfg.borrow_enable and not cfg.borrow_character_enable
                               and daily.needs_support())
            succeeded = power.run(borrow_for_daily=support_pending, on_summary=summaries.append)
        if succeeded and "REWARDS" in selected:
            succeeded = rewards.claim()
        if succeeded and "DAILY" in selected:
            succeeded = daily.run(complete_training=True, on_summary=summaries.append)
        if bridge.isCancelled():
            return "stopped"
        if not succeeded:
            return "task_failed"
        if summaries:
            bridge.reportSummary(tr("；").join(summaries))
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
