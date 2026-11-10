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
        self.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%H:%M:%S"))

    def emit(self, record):
        self.bridge.log(self.format(record))


class _AppSession:
    def __init__(self, client, bridge):
        self.client = client
        self.bridge = bridge

    def request(self, command, **params):
        from utils.pause import RunStopRequested

        if self.bridge.isCancelled() and params.get("action") != "up":
            raise RunStopRequested()
        response, payload = self.client.request(command, **params)
        if command == "events":
            for event in response["events"]:
                self.bridge.gameEvent(event["event"], event.get("to") if event.get("to") is not None else -1)
        return response, payload

    def is_game_running(self):
        status, _ = self.request("status")
        return status["watchdog"].get("pid", -1) > 0

    def close(self):
        try:
            if not self.client.closed:
                self.client.request("shutdown", timeout=2)
        finally:
            self.client.close()


def run(workdir, token, sdk, version, model, is_emulator, task, config, language, bridge):
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
    try:
        if bridge.isCancelled():
            raise RunStopRequested()
        settings = {
            "control_backend": "adb",
            "ui_profile": "touch_720",
            "notification_enable": False,
            "reward_enable": True,
            "reward_quest_enable": config.getCollectRewards(),
            "reward_dispatch_enable": config.getDispatch(),
            "reward_mail_enable": config.getMail(),
            "reward_assist_enable": config.getAssist(),
        }
        if task == "POWER":
            settings.update(
                power_plan=[["拟造花萼（金）", config.getCalyx().getInstanceName(), config.getWaves()]],
                use_reserved_trailblaze_power=False,
                use_fuel=False,
            )
        cfg.set_values(settings)
        load_language(language)

        from module.game import get_game_controller
        from module.game.adb_ready import wait_for_game
        from module.game.adb_transport import AdbDevice, AdbEnvironment, ServiceClient, check_service_hello
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
        controller.attach_virtual_session(environment, session)
        display_id = controller.prepare_display()
        bridge.displayReady(display_id)
        log.info(f"已创建 1280×720 虚拟屏，display {display_id}")
        started = time.monotonic()
        controller.start_game_process()
        wait_for_game(controller, min(cfg.start_game_timeout * 60, 180))
        log.info(f"游戏画面就绪，用时 {time.monotonic() - started:.1f} 秒")
        bridge.gameReady()
        if config.getPanelOff():
            result, _ = session.request("screen_power", on=False)
            bridge.panelChanged(result["panel_off"])
            log.info("已关闭实体面板，保持系统唤醒")
        action = {"DAILY": daily.run, "REWARDS": rewards.run, "POWER": power.run}[task]
        if action():
            return "stopped" if bridge.isCancelled() else "success"
        return "stopped" if bridge.isCancelled() else "task_failed"
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
