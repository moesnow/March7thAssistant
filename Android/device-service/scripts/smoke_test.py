"""设备端服务冒烟测试。

依次：推送 jar → 启动服务 → 鉴权反例 → 建虚拟屏 → 开看门狗 → 启动应用 → 等回迁 → 取帧并测速
→ 注入滑动、按住拖动、点按 → 关闭服务 → 核对现场。每一步打印结果，最后输出一份 JSON 汇总。

用法（先在 Android/ 下执行 gradlew :device-service:assemble）：

    python smoke_test.py --serial <序列号>

    # 星铁：回迁后点两次“点击进入”进到车厢再测速，最后点开手机菜单
    python smoke_test.py --serial <序列号> --pre-tap 640,665:20 --pre-tap 640,665:45 --tap 35,67 --out out/phone

只依赖标准库和 PATH 里的 adb（装了 numpy 会多测带预测的压缩）。
会启动并在结束时停止游戏，运行前确认设备和账号归你使用。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

from device_client import (DEFAULT_JAR, Adb, DeviceClient, DeviceError, ServiceHandle, changed_ratio,
                           measure_frame_encoding, start_service, write_png)

GAME = "com.miHoYo.hkrpg/com.mihoyo.combosdk.ComboSDKActivity"

# 取帧测速的编码组合。带预测的那一种解码要用 numpy，没装就跳过。
ENCODINGS = [
    {"encoding": "rgba"},
    {"encoding": "rgb"},
    {"encoding": "rgb-zlib", "level": 1},
    {"encoding": "rgb-zlib", "level": 1, "chunks": 4},
]
if importlib.util.find_spec("numpy"):
    ENCODINGS.append({"encoding": "rgb-zlib", "level": 1, "chunks": 4, "predictor": "left"})
    ENCODINGS.append({"encoding": "rgb-zlib", "level": 1, "chunks": 4, "predictor": "up"})
ENCODINGS += [{"encoding": "rgba-zlib", "level": 1, "chunks": 4},
              {"encoding": "rgb", "crop": [0, 0, 320, 180]}]

results: dict = {"steps": []}
started = time.monotonic()


def step(name: str, ok: bool, **info) -> None:
    results["steps"].append({"step": name, "ok": ok, "t": round(time.monotonic() - started, 2), **info})
    detail = " ".join(f"{key}={value}" for key, value in info.items())
    print(f"[{time.monotonic() - started:7.2f}s] {'PASS' if ok else 'FAIL'} {name} {detail}", flush=True)


def encoding_label(options: dict) -> str:
    label = options["encoding"]
    if "chunks" in options:
        label += f"×{options['chunks']}"
    if options.get("predictor"):
        label += f"+{options['predictor']}"
    if "crop" in options:
        _, _, width, height = options["crop"]
        label += f" {width}×{height}"
    return label


def display_ids(adb: Adb) -> list[int]:
    output = adb.shell("dumpsys display | grep mDisplayId=")
    return sorted({int(line.split("=")[1]) for line in output.split() if line.startswith("mDisplayId=")})


def check_auth(handle: ServiceHandle) -> None:
    """没有令牌、令牌不对、协议版本不对的连接都必须被拒绝。"""
    cases = {
        "wrong_token": dict(token="x" * 32),
        "empty_token": dict(token=""),
        "wrong_protocol": dict(token=handle.token, protocol=999),
    }
    for name, kwargs in cases.items():
        try:
            DeviceClient("127.0.0.1", handle.port, kwargs.pop("token"), timeout=5, **kwargs).close()
            step(f"auth/{name}", False, note="connection was accepted")
        except DeviceError as error:
            step(f"auth/{name}", name == "wrong_protocol" and error.code == "protocol_mismatch", rejected=error.code)
        except (ConnectionError, OSError) as error:
            step(f"auth/{name}", name != "wrong_protocol", rejected=type(error).__name__)
    # 不握手直接发别的命令
    import socket
    import struct
    raw = socket.create_connection(("127.0.0.1", handle.port), timeout=5)
    try:
        body = json.dumps({"id": 1, "cmd": "status"}).encode()
        raw.sendall(struct.pack(">II", len(body), 0) + body)
        step("auth/no_hello", raw.recv(1) == b"", rejected="closed")
    except OSError as error:
        step("auth/no_hello", True, rejected=type(error).__name__)
    finally:
        raw.close()


def measure_frames(client: DeviceClient, seconds: float) -> list[dict]:
    table = []
    for options in ENCODINGS:
        label = encoding_label(options)
        try:
            row = measure_frame_encoding(client, seconds, options)
        except (DeviceError, ConnectionError) as error:
            step(f"frame/{label}", False, error=str(error))
            continue
        table.append({"encoding": label, "options": options, **row})
        step(f"frame/{label}", True, **{key: value for key, value in row.items() if key != "samples"})
    return table


def check_input(client: DeviceClient, args, out: Path | None) -> None:
    """滑动、按住拖动、点按各做一次，确认用的帧严格晚于输入完成。"""
    _, before = client.frame()
    x0, y0, x1, y1 = args.swipe
    response, _ = client.request("swipe", points=[[x0, y0], [x1, y1]], duration_ms=600, timeout=20)
    time.sleep(args.settle)
    after_header, after = client.frame_after(response)
    step("input/swipe", response["delivered"], input_seq=response["seq"], next_frame_seq=after_header["seq"],
         input_ns=response["input_ns"], image_ns=after_header["image_ns"],
         changed=round(changed_ratio(before, after, 3), 3))
    if out:
        write_png(out / "after-swipe.png", after_header["width"], after_header["height"], 3, after)

    # 按住拖动：按下，分多步移动，停一下再抬起
    before = after
    down, _ = client.request("touch", action="down", x=x1, y=y1)
    for i in range(1, 21):
        client.request("touch", action="move", x=x1 + (x0 - x1) * i / 20, y=y1 + (y0 - y1) * i / 20)
        time.sleep(0.02)
    time.sleep(0.3)
    up, _ = client.request("touch", action="up")
    time.sleep(args.settle)
    after_header, after = client.frame_after(up)
    step("input/drag", down["delivered"] and up["delivered"],
         down_seq=down["seq"], up_seq=up["seq"], next_frame_seq=after_header["seq"],
         input_ns=up["input_ns"], image_ns=after_header["image_ns"],
         changed=round(changed_ratio(before, after, 3), 3))
    if out:
        write_png(out / "after-drag.png", after_header["width"], after_header["height"], 3, after)

    before = after
    x, y = args.tap
    response, _ = client.request("tap", x=x, y=y, duration_ms=args.tap_ms)
    time.sleep(args.settle)
    after_header, after = client.frame_after(response)
    step("input/tap", response["delivered"], x=x, y=y,
         input_seq=response["seq"], next_frame_seq=after_header["seq"],
         input_ns=response["input_ns"], image_ns=after_header["image_ns"],
         changed=round(changed_ratio(before, after, 3), 3))
    if out:
        write_png(out / "after-tap.png", after_header["width"], after_header["height"], 3, after)

    # 实体屏默认碰不到：不给 display_id 时只会落到虚拟屏
    try:
        client.request("key", keycode="HOME")
        step("input/key_allowlist", False, note="HOME was accepted")
    except DeviceError as error:
        step("input/key_allowlist", error.code == "bad_request", rejected=error.code)


def parse_pre_tap(text: str) -> tuple[int, int, float]:
    point, _, wait = text.partition(":")
    x, y = (int(v) for v in point.split(","))
    return x, y, float(wait or 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--serial", help="adb 序列号；只连着一台设备时可以不给")
    parser.add_argument("--jar", type=Path, default=DEFAULT_JAR)
    parser.add_argument("--component", default=GAME, help="要启动的组件，形如 包名/类名")
    parser.add_argument("--size", default="1280x720/240", help="虚拟屏 宽x高/dpi")
    parser.add_argument("--migration-timeout", type=float, default=90,
                        help="启动后等登录 SDK 把任务带走再回迁的最长时间（秒）；0 表示不等")
    parser.add_argument("--warmup", type=float, default=8, help="回迁之后、测速之前等画面稳定的时间（秒）")
    parser.add_argument("--bench-seconds", type=float, default=5, help="每种编码测多久")
    parser.add_argument("--pre-tap", type=parse_pre_tap, action="append", default=[], metavar="X,Y:秒",
                        help="测速之前先点一下再等若干秒，可以给多次，用来从标题页进到游戏里")
    parser.add_argument("--tap", type=lambda s: tuple(int(v) for v in s.split(",")), default=(640, 360),
                        help="点按坐标 x,y")
    parser.add_argument("--tap-ms", type=int, default=50)
    parser.add_argument("--swipe", type=lambda s: tuple(int(v) for v in s.split(",")), default=(960, 437, 780, 437),
                        help="滑动的起点和终点 x0,y0,x1,y1")
    parser.add_argument("--settle", type=float, default=1.5, help="每次输入后等画面变化的时间（秒）")
    parser.add_argument("--auto-focus", action="store_true",
                        help="由看门狗在任务移回和停帧时切焦点（MuMu 的 Android 12 需要）")
    parser.add_argument("--skip-input", action="store_true")
    parser.add_argument("--keep-app", action="store_true", help="结束时不停止应用")
    parser.add_argument("--out", type=Path, help="保存截图（已遮住 UID 区域）和 result.json 的目录")
    args = parser.parse_args()

    adb = Adb(args.serial)
    out = args.out
    if out:
        out.mkdir(parents=True, exist_ok=True)
    package = args.component.split("/")[0]
    main_activity = args.component.split("/")[1]
    size, dpi = args.size.split("/")
    width, height = (int(v) for v in size.split("x"))

    baseline = {
        "displays": display_ids(adb),
        "wm_size": adb.shell("wm size").strip(),
        "wm_density": adb.shell("wm density").strip(),
    }
    results["device"] = {"serial": args.serial, **baseline}
    print(f"baseline: {baseline}", flush=True)

    handle = start_service(adb, args.jar)
    step("start", True, pid=handle.pid, port=handle.port, socket=handle.socket_name)
    client = None
    try:
        check_auth(handle)
        client = handle.connect(events=True)
        hello = client.hello
        results["hello"] = hello
        step("hello", hello["protocol"] == 1, version=hello["version"], model=hello["device"]["model"],
             sdk=hello["device"]["sdk"], displays=[d["id"] for d in hello["displays"]])

        try:
            client.request("tap", x=1, y=1)
            step("input/no_display", False, note="tap without a display was accepted")
        except DeviceError as error:
            step("input/no_display", error.code == "no_display", rejected=error.code)

        display, _ = client.request("create_display", width=width, height=height, dpi=int(dpi))
        display_id = display["display_id"]
        step("create_display", display_id in display_ids(adb), display_id=display_id,
             size=f"{display['width']}x{display['height']}/{display['dpi']}")

        watchdog, _ = client.request("watchdog", package=package, main_activity=main_activity,
                                     auto_focus=args.auto_focus)
        step("watchdog", watchdog["watchdog"]["enabled"], inspector=watchdog["watchdog"]["inspector"])

        client.request("stop_app", package=package)
        launched_at = time.monotonic()
        launch, _ = client.request("launch", component=args.component, timeout=60)
        step("launch", True, display_id=launch["display_id"], seconds=round(time.monotonic() - launched_at, 1))

        first, _ = client.frame(min_seq=launch["seq"] + 1, timeout_ms=20000)
        step("first_frame", True, seq=first["seq"], seconds=round(time.monotonic() - launched_at, 1))

        if args.migration_timeout > 0:
            moved = client.wait_event(
                lambda e: e["event"] in ("move_back_succeeded", "manual_action_required", "game_exited")
                or (e["event"] == "move_back_failed" and e["final"]), args.migration_timeout)
            if moved is None:
                attempted = any(e["event"] == "move_back_started" for e in client.events)
                step("migration", not attempted, note=f"no completed migration within {args.migration_timeout:.0f} s")
            else:
                shown = next((e for e in client.events if e["event"] == "sdk_window_shown"), None)
                gone = next((e for e in client.events if e["event"] == "sdk_window_gone"), None)
                step("migration", moved["event"] == "move_back_succeeded", event=moved["event"],
                     sdk_shown_s=round((shown["device_ms"] - launch["device_ms"]) / 1000, 1) if shown else None,
                     sdk_ms=gone.get("duration_ms") if gone else None,
                     move_ms=moved.get("elapsed_ms"), attempt=moved.get("attempt"),
                     first_frame_seq=moved.get("first_frame_seq"), reason=moved.get("reason"))
        results["events"] = list(client.events)

        time.sleep(args.warmup)
        for x, y, wait in args.pre_tap:
            response, _ = client.request("tap", x=x, y=y, duration_ms=args.tap_ms)
            step("pre_tap", response["delivered"], x=x, y=y, seq=response["seq"], wait=wait)
            time.sleep(wait)
        status, _ = client.request("status")
        task = status["watchdog"].get("task") or {}
        step("on_display", task.get("display_id") == display_id, task_display=task.get("display_id"),
             top=task.get("top_activity"), frame_seq=status["frame"]["seq"])
        header, pixels = client.frame()
        if out:
            write_png(out / "before-input.png", header["width"], header["height"], 3, pixels)

        results["frames"] = measure_frames(client, args.bench_seconds)

        crop_header, crop = client.frame(crop=[0, 0, 200, 100], encoding="rgba")
        full_header, full = client.frame(min_seq=crop_header["seq"], encoding="rgba")
        step("frame/crop", len(crop) == 200 * 100 * 4 and crop_header["crop"] == [0, 0, 200, 100],
             size=len(crop), seq=crop_header["seq"])
        try:
            client.frame(min_seq=full_header["seq"] + 100000, timeout_ms=300)
            step("frame/timeout", False, note="future seq was served")
        except DeviceError as error:
            step("frame/timeout", error.code == "timeout", latest_seq=error.details.get("latest_seq"))

        if not args.skip_input:
            check_input(client, args, out)

        results["events"] = list(client.events)
        if not args.keep_app:
            client.request("stop_app", package=package)
        client.request("shutdown")
        client.close()
        client = None
        deadline = time.monotonic() + 10
        while handle.running() and time.monotonic() < deadline:
            time.sleep(0.3)
        step("shutdown", not handle.running())
    except (DeviceError, OSError) as error:
        step("service", False, error=str(error))
    finally:
        if client is not None:
            results["events"] = list(client.events)
            if not args.keep_app:
                try:
                    client.request("stop_app", package=package)
                except (DeviceError, OSError):
                    pass
            try:
                client.request("shutdown")
            except (DeviceError, OSError):
                pass
            client.close()
        handle.remove_forward()

    time.sleep(1)
    after = {
        "displays": display_ids(adb),
        "wm_size": adb.shell("wm size").strip(),
        "wm_density": adb.shell("wm density").strip(),
    }
    step("restored", after == baseline, **after)
    step("adb_online", "device" in adb.run("get-state").strip())
    results["log"] = adb.shell("cat /data/local/tmp/m7a-device-service.log", check=False)

    failed = [item["step"] for item in results["steps"] if not item["ok"]]
    results["failed"] = failed
    if out:
        (out / "result.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    if results.get("frames"):
        print("\n编码           帧率   大小KB  服务端ms  取最新帧请求 p50/p95    采集到收完 p50/p95")
        for row in results["frames"]:
            print(f"{row['encoding']:<14} {row['fps']:>5} {row['size_kb']:>7} {row['server_ms']:>9} "
                  f"{row['latest_request_ms_p50']:>8} {row['latest_request_ms_p95']:>8} {row['end_to_end_ms_p50']:>10} "
                  f"{row['end_to_end_ms_p95']:>10}")
    print(f"\n{'全部通过' if not failed else '失败：' + ', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
