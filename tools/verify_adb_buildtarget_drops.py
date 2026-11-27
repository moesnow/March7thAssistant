"""实机遍历桌面 ADB 支持的副本，验证培养目标两种方案的 OCR，逐项保存断点。

运行：uv run python tools/verify_adb_buildtarget_drops.py --serial <设备序列号>
异常时立即退出；修复后用同一命令继续。截图、识别原文与进度保存在 temp/adb-buildtarget/all-drops。
"""
import argparse
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils import paths


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(value):
    return "".join(unicodedata.normalize("NFKC", value).split())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--state-dir", type=Path, default=ROOT / paths.ADB_BUILDTARGET_DROPS)
    args = parser.parse_args()
    folder = args.state_dir.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    checkpoint = folder / "checkpoint.json"
    os.chdir(ROOT)

    # 在切换到隔离配置前查询桌面运行记录，避免抢占现有任务。
    status = json.loads(subprocess.check_output([sys.executable, "main.py", "--status"], cwd=ROOT))
    if status.get("active_run") is not None:
        raise RuntimeError("已有小助手任务正在运行，未开始副本遍历")
    if not status.get("first_run_completed"):
        raise RuntimeError("小助手尚未完成首次使用确认，未开始副本遍历")
    os.environ["M7A_DATA_DIR"] = str(folder / "userdata")

    from module.config import cfg
    cfg.set_values({
        "control_backend": "adb", "ui_profile": "touch_720", "adb_serial": args.serial,
        "adb_service_jar": str(ROOT / "Android/device-service/build/outputs/m7a-device-service.jar"),
        "notification_enable": False, "debug_mode_enable": False, "build_target_enable": False,
        "power_plan": [], "after_finish": "None",
    })
    from module.automation import auto
    from module.automation.automation import screenshot_retry_timeout
    from module.automation.input_base import limit_input_deadline
    from module.game import get_game_controller
    from module.game.adb_ready import wait_for_game
    from module.localization import get_raw_instance_names
    from module.screen import screen
    from tasks.touch import buildtarget as target, power
    from utils.pause import RunStopRequested, pause_ctl

    catalog = get_raw_instance_names()
    drop_index = read_json(ROOT / "assets/config/instance_drops.json")
    instances = [(kind, name) for kind, names in catalog.items() for name in names if name != "无"]
    total_drops = sum(len(drop_index[kind][name]) for kind, name in instances)
    fingerprint = sha256(json.dumps([instances, drop_index], ensure_ascii=False).encode()).hexdigest()
    state = read_json(checkpoint) if checkpoint.exists() else {
        "catalog_sha256": fingerprint, "serial": args.serial, "passed": {}, "instances": {}, "runs": [],
    }
    if state["catalog_sha256"] != fingerprint or state["serial"] != args.serial:
        raise RuntimeError("副本目录或设备已改变，请为本轮指定新的 --state-dir，原断点予以保留")
    run = {"started_at": datetime.now().isoformat(), "status": "running"}
    state["runs"].append(run)
    state.update(status="running", total_instances=len(instances), total_drops=total_drops)
    recognition_hash = sha256(Path(target.__file__).read_bytes()).hexdigest()
    events = folder / "events.jsonl"

    def save():
        temporary = checkpoint.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(checkpoint)

    def emit(event, **fields):
        record = {"time": datetime.now().isoformat(), "event": event, **fields}
        with events.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(json.dumps(record, ensure_ascii=False), flush=True)

    def screenshot(name):
        frame, _, _ = auto.take_screenshot()
        path = folder / f"{name}.png"
        frame.save(path)
        return str(path)

    game = get_game_controller()
    original_send = game.send_input

    def read_only_input(command, **params):
        # 遍历仅查看详情，所有副本共用的右下挑战区禁止点按。
        if command == "tap" and params.get("x", 0) >= 780 and params.get("y", 0) >= 630:
            raise RuntimeError(f"遍历脚本拒绝向挑战区域点按：{params['x']}, {params['y']}")
        return original_send(command, **params)

    game.send_input = read_only_input
    pause_ctl.start(str(folder / "control.json"))
    handler = target.TouchDefaultHandler()
    drop_handler = target.TouchDropHandler()
    save()
    emit("started", instances=len(instances), drops=total_drops, already_passed=len(state["passed"]),
         checkpoint=str(checkpoint))

    def startup_recover():
        if modal := target._modal():
            target._close_modal(modal[0])
        if screen.get_current_screen(autotry=False, max_retries=1):
            screen.change_to("main", max_recursion=1)

    try:
        game.start_game_process()
        with screenshot_retry_timeout(5):
            wait_for_game(game, 180, recover=startup_recover)
        for index, (kind, name) in enumerate(instances):
            instance_id = f"{index + 1:03d}"
            expected = drop_index[kind][name]
            case_ids = [f"{instance_id}-{slot + 1:02d}" for slot in range(len(expected))]
            if all(case_id in state["passed"] for case_id in case_ids):
                continue
            state["current"] = {"instance": index + 1, "kind": kind, "name": name, "phase": "enter"}
            save()
            emit("instance_started", index=index + 1, total=len(instances), kind=kind, name=name)
            with limit_input_deadline(time.monotonic() + 240), screenshot_retry_timeout(5):
                power._reenter_instance(kind, name)
                title_image = screenshot(f"{instance_id}-instance")
                identified = handler._get_instance_info()
                validated = handler._is_valid_instance(identified) if identified else None
                if validated != (kind, name):
                    raise RuntimeError(f"副本标题或材料来源识别不符：预期 {(kind, name)}，识别 {identified}，校验 {validated}")
                state["instances"][instance_id] = {
                    "kind": kind, "name": name, "identified": identified, "screenshot": title_image,
                }
                save()
                # 普通副本掉落物横排位于右栏，饰品提取位于中上方。
                x0, y = (550, 338) if kind == power.ORNAMENT else (845, 421)
                if kind == power.ECHO:
                    label = target._wait(lambda: auto.find_element("可能获取", "text",
                                         crop=(804 / 1280, 300 / 720, 400 / 1280, 230 / 720)),
                                         "未找到历战余响掉落物区域")
                    y = (label[0][1] + label[1][1]) / 2 + 60
                observed = {normalize(state["passed"][case_id].get("read_name", state["passed"][case_id]["raw"]))
                            for case_id in case_ids if case_id in state["passed"]}
                for slot, case_id in enumerate(case_ids):
                    if case_id in state["passed"]:
                        continue
                    pause_ctl.check_stop()
                    state["current"].update(phase="drop", slot=slot + 1, case_id=case_id, expected=expected)
                    save()
                    target._tap(x0 + slot * 76, y)
                    coords, text_crop = target._wait(target._modal, f"{kind} · {name} 第 {slot + 1} 个掉落物弹窗未出现")
                    read_name = drop_handler.read_drop_name(text_crop)
                    reading = drop_handler.last_drop_reading
                    raw = reading["text"]
                    crop_path = folder / f"{case_id}-title.png"
                    auto.screenshot.save(crop_path)
                    modal_image = screenshot(f"{case_id}-modal")
                    matched = drop_handler._match_instance(read_name) if read_name else None
                    record = {
                        "kind": kind, "name": name, "slot": slot + 1, "raw": raw, "read_name": read_name,
                        "reading": reading, "matched": matched,
                        "title_crop": str(crop_path), "screenshot": modal_image,
                        "recognition_sha256": recognition_hash,
                    }
                    emit("recognized", case_id=case_id, **record)
                    if not read_name or normalize(read_name) not in {normalize(value) for value in expected}:
                        raise RuntimeError(f"掉落物 OCR 不符：{kind} · {name} 第 {slot + 1} 项，识别 {raw!r}，预期 {expected}")
                    if not matched or matched[:2] != (kind, name):
                        raise RuntimeError(f"掉落物匹配错误：{raw!r} -> {matched}，预期 {(kind, name)}")
                    if normalize(read_name) in observed:
                        raise RuntimeError(f"重复识别到同一个掉落物：{raw!r}，尚未覆盖 {expected}")
                    target._close_modal(coords)
                    target._wait(lambda: auto.find_element(("挑战", "开始挑战"), "text", crop=target.CHALLENGE),
                                 "关闭掉落物弹窗后未返回副本详情")
                    state["passed"][case_id] = record
                    observed.add(normalize(read_name))
                    save()
                    emit("passed", case_id=case_id, count=len(state["passed"]), total=total_drops,
                         kind=kind, name=name, drop=read_name, raw=raw)
                if observed != {normalize(value) for value in expected}:
                    raise RuntimeError(f"{kind} · {name} 的掉落物覆盖不完整：{observed} / {expected}")
        with screenshot_retry_timeout(5):
            screen.change_to("main", max_recursion=1)
        state.update(status="completed", current=None)
        run.update(status="completed", ended_at=datetime.now().isoformat())
        save()
        emit("completed", instances=len(instances), drops=len(state["passed"]), battle_started=False)
        return 0
    except BaseException as error:
        run.update(status="stopped" if isinstance(error, RunStopRequested) else "failed",
                   ended_at=datetime.now().isoformat(), error=str(error), traceback=traceback.format_exc())
        state["status"] = run["status"]
        try:
            with screenshot_retry_timeout(2):
                run["failure_screenshot"] = screenshot(f"failure-{len(state['runs']):02d}")
        except BaseException as capture_error:
            run["capture_error"] = str(capture_error)
        save()
        emit(run["status"], current=state.get("current"), passed=len(state["passed"]), error=str(error),
             failure_screenshot=run.get("failure_screenshot"))
        traceback.print_exc()
        return 6 if isinstance(error, RunStopRequested) else 1
    finally:
        game.send_input = original_send
        game.close()
        pause_ctl.stop()


if __name__ == "__main__":
    raise SystemExit(main())
