
"""ADB 冷启动与开菜单自检，复用 B0 的 720p 素材。"""
from datetime import datetime
from pathlib import Path
import time

from PIL import ImageDraw

from module.game.adb_ready import _load_template, _match, wait_for_game
from module.game.adb_transport import AdbError, resolve_adb_path
from module.localization import tr
from utils.pause import pause_ctl


_UID_REGIONS = ((725, 0, 1279, 195), (0, 644, 540, 719), (980, 671, 1279, 719))


def _measure_frames(controller, seconds=3):
    started = time.monotonic()
    frames = updates = 0
    previous = controller.frame_sequence
    while time.monotonic() - started < seconds:
        pause_ctl.checkpoint()
        if controller.capture_frame():
            frames += 1
            sequence = controller.frame_sequence
            if sequence != previous:
                updates += 1
                previous = sequence
    return frames, updates, time.monotonic() - started


def _confirm_menu(controller, screen_name, point):
    if screen_name == "main" and not controller.get_input_handler().mouse_click(*point):
        raise AdbError("menu_input", tr("未能点开 Android 手机菜单，请检查游戏是否处于主界面"))
    template = _load_template("menu")
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        pause_ctl.checkpoint()
        if (frame := controller.capture_frame()) and _match(frame[0], "menu", template):
            return frame[0]
        time.sleep(0.15)
    raise AdbError("menu_timeout", tr("ADB 自检未能在输入后的画面中确认手机菜单"))


def run(controller):
    """执行 ADB 自检，保存已遮盖 UID 的截图并释放本次会话。"""
    adb_path = resolve_adb_path(controller.cfg.adb_path)
    print(tr("ADB 路径：{path}").format(path=adb_path), flush=True)
    stop_game = False
    try:
        environment = controller.connect(adb_path=adb_path)
        device = environment.device
        print(tr("ADB 设备：{serial} · {model} · Android {version}（API {sdk}）").format(
            serial=device.serial, model=device.model or device.serial, version=environment.android_version,
            sdk=environment.sdk,
        ), flush=True)
        status = controller.get_runtime_status()
        print(tr("ADB 设备端服务版本：{version}").format(version=status.service_version), flush=True)
        display_id = controller.prepare_display()
        if display_id == 0:
            print(tr("使用模拟器 display 0（1280×720 横屏）"), flush=True)
        else:
            print(tr("已创建 1280×720 虚拟屏，display {display}").format(display=display_id), flush=True)

        stop_game = not controller.is_game_running()
        started = time.monotonic()
        controller.start_game_process()
        print(tr("已在 display {display} 启动游戏，等待进入主界面").format(display=display_id), flush=True)
        name, point = wait_for_game(controller, timeout=min(controller.cfg.start_game_timeout * 60, 180))
        print(tr("游戏界面就绪，用时 {seconds:.1f} 秒").format(seconds=time.monotonic() - started), flush=True)

        frames, updates, elapsed = _measure_frames(controller)
        if not frames:
            raise AdbError("no_frames", tr("ADB 自检未取得游戏画面"))
        print(tr("取帧速率：{fps:.1f} FPS（{frames} 次取样 / {seconds:.1f} 秒，{updates} 次更新）").format(
            fps=frames / elapsed, frames=frames, seconds=elapsed, updates=updates
        ), flush=True)
        moved = sum(event["event"] == "move_back_succeeded" for event in controller.events)
        if moved:
            print(tr("已确认自动回迁 {count} 次").format(count=moved), flush=True)
        elif display_id == 0:
            print(tr("模拟器使用 display 0，无需回迁"), flush=True)
        else:
            print(tr("本次启动未发生回迁"), flush=True)

        # 测速前的 HUD 坐标仍对应固定菜单按钮，点击后必须重新识别菜单。
        image = _confirm_menu(controller, name, point)
        draw = ImageDraw.Draw(image)
        for region in _UID_REGIONS:
            draw.rectangle(region, fill="black")
        output = Path("logs/screenshots") / f"adb-check-{datetime.now():%Y%m%d-%H%M%S-%f}.png"
        output.parent.mkdir(parents=True, exist_ok=True)
        image.save(output)
        print(tr("已确认手机菜单，截图：{path}").format(path=output.resolve()), flush=True)
        return True
    except AdbError as error:
        # 留着需要人工登录的 SDK 窗口，用户完成登录后可以再次运行。
        if error.code in {"manual_action_required", "disconnected", "adb_server_restarted"}:
            stop_game = False
        raise
    finally:
        if stop_game:
            try:
                controller.stop_game()
            except AdbError as error:
                controller.log_warning(f"ADB 自检停止游戏失败：{error}")
        controller.close()
