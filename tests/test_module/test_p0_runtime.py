"""P0 运行开销改动的回归测试。

覆盖：截图帧缓存（含外部改写 screenshot 自动失效）、界面匹配线程数上限、
OCR 周期 full GC 间隔、关闭 pyautogui 默认停顿、mss 实例复用、后台截图
GDI 资源释放。
"""
import sys
import threading
import time
from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")
Image = pytest.importorskip("PIL.Image")


def _make_automation(screenshot):
    from module.automation import automation as automation_module

    auto = object.__new__(automation_module.Automation)
    auto.screenshot = screenshot
    auto.logger = Mock()
    auto.img_cache = {}
    auto.screenshot_pos = (0, 0)
    auto.screenshot_scale_factor = 1
    return auto


class TestFrameCache:
    def test_bgr_and_gray_match_legacy_conversions(self):
        image = Image.new("RGB", (64, 48), (7, 11, 13))
        image.putpixel((3, 4), (10, 20, 30))
        auto = _make_automation(image)

        rgb = auto._frame_rgb_array()
        assert rgb.shape == (48, 64, 3)
        assert list(rgb[4, 3]) == [10, 20, 30]  # 与 PIL 帧同序（RGB）
        assert list(auto.frame_bgr()[4, 3]) == [30, 20, 10]
        assert np.array_equal(
            auto.frame_gray(),
            cv2.cvtColor(np.array(image), cv2.COLOR_BGR2GRAY),
        )

    def test_conversions_are_reused_for_same_frame(self):
        auto = _make_automation(Image.new("RGB", (32, 32), "white"))

        bgr = auto.frame_bgr()
        gray = auto.frame_gray()
        assert auto.frame_bgr() is bgr
        assert auto.frame_gray() is gray
        assert auto._frame_rgb_array() is auto._frame_rgb

    def test_external_screenshot_change_invalidates_cache(self):
        auto = _make_automation(Image.new("RGB", (32, 32), "white"))
        first = auto.frame_bgr()
        auto.screenshot = Image.new("RGB", (40, 20), "black")

        second = auto.frame_bgr()
        assert second is not first
        assert second.shape == (20, 40, 3)
        assert auto._frame_screenshot is auto.screenshot

    def test_missing_screenshot_reports_error(self):
        auto = _make_automation(None)
        with pytest.raises(RuntimeError, match="尚未获取游戏截图"):
            auto.frame_bgr()

    def test_find_image_element_converts_frame_once_per_screenshot(self, monkeypatch, tmp_path):
        from module.automation import automation as automation_module

        template_path = tmp_path / "template.png"
        template = np.zeros((20, 30, 3), dtype=np.uint8)
        template[:10, :, 1] = 255  # 上半绿色、下半蓝色，避免常量模板让相似度退化
        template[10:, :, 0] = 255
        assert cv2.imwrite(str(template_path), template)

        frame = Image.new("RGB", (320, 200), "white")
        frame.paste(Image.fromarray(template[:, :, ::-1]), (40, 30))
        auto = _make_automation(frame)
        monkeypatch.setattr(
            automation_module,
            "get_ui_profile",
            lambda cfg: SimpleNamespace(name="pc_1080", resolve_image_path=lambda path: path),
        )
        real_cvt_color = automation_module.cv2.cvtColor
        frame_conversions = []

        def counting_cvt_color(src, code, *args, **kwargs):
            if src.shape[:2] == (200, 320):
                frame_conversions.append(code)
            return real_cvt_color(src, code, *args, **kwargs)

        monkeypatch.setattr(automation_module.cv2, "cvtColor", counting_cvt_color)

        first = auto.find_image_element(str(template_path), 0.9, None)
        second = auto.find_image_element(str(template_path), 0.9, None)

        assert first[0] is not None and second[0] is not None
        assert first[0] == second[0] == (40, 30)
        assert len(frame_conversions) == 1  # 同一帧只转换一次

        auto.screenshot = Image.new("RGB", (320, 200), "white")
        auto.find_image_element(str(template_path), 0.9, None)
        assert len(frame_conversions) == 2  # 新截图重新转换


class TestScreenMatchWorkers:
    def test_worker_count_is_capped_and_never_below_one(self):
        from module.screen.screen import _screen_match_workers

        assert _screen_match_workers(61) == 8
        assert _screen_match_workers(8) == 8
        assert _screen_match_workers(3) == 3
        assert _screen_match_workers(0) == 1

    def test_get_current_screen_passes_capped_worker_count(self, monkeypatch):
        import concurrent.futures
        import importlib

        import psutil

        screen_module = importlib.import_module("module.screen.screen")

        created = []

        class FakeExecutor:
            def __init__(self, max_workers=None):
                created.append(max_workers)

            def submit(self, fn, *args, **kwargs):
                future = Future()
                future.set_result(fn(*args, **kwargs))
                return future

            def shutdown(self, wait=True, cancel_futures=False):
                pass

        screens = {
            f"screen_{index}": {"name": f"screen_{index}", "image_path": f"./screen_{index}.png", "actions": []}
            for index in range(61)
        }
        page = object.__new__(screen_module.Screen)
        page.screen_map = screens
        page.current_screen = None
        page.current_screen_threshold = 0
        page.lock = threading.Lock()
        page.logger = Mock()
        page.wait_screen_change_time = 0.5
        page._find_image = lambda *args, **kwargs: None

        monkeypatch.setattr(concurrent.futures, "ThreadPoolExecutor", FakeExecutor)
        monkeypatch.setattr(screen_module.auto, "take_screenshot", lambda *args, **kwargs: None)
        monkeypatch.setattr(psutil, "virtual_memory", lambda: SimpleNamespace(available=4 * 1024 ** 3))

        assert page.get_current_screen(autotry=False, max_retries=1) is False
        assert created == [8]

    def test_get_current_screen_classifies_with_shared_frame(self, monkeypatch, tmp_path):
        import importlib

        from PIL import ImageDraw

        screen_module = importlib.import_module("module.screen.screen")
        automation_module = importlib.import_module("module.automation.automation")

        def write_template(path):
            image = Image.new("RGB", (40, 30), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 0, 39, 14), fill=(0, 200, 0))
            draw.rectangle((0, 15, 19, 29), fill="black")
            draw.rectangle((20, 15, 39, 29), fill=(40, 40, 40))
            image.save(path)

        def write_other(path):
            image = Image.new("RGB", (40, 30), "red")
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 0, 9, 9), fill="white")
            draw.rectangle((30, 20, 39, 29), fill="blue")
            image.save(path)

        main_path = tmp_path / "main.png"
        menu_path = tmp_path / "menu.png"
        write_template(main_path)
        write_other(menu_path)

        frame = Image.new("RGB", (320, 200), "gray")
        frame.paste(Image.open(main_path), (10, 10))

        auto = screen_module.auto
        previous_screenshot = auto.screenshot
        previous_cache = auto.img_cache
        auto.screenshot = frame
        auto.screenshot_pos = (0, 0)
        auto.screenshot_scale_factor = 1
        auto.img_cache = {}
        monkeypatch.setattr(
            automation_module,
            "get_ui_profile",
            lambda cfg: SimpleNamespace(name="pc_1080", resolve_image_path=lambda path: path),
        )
        monkeypatch.setattr(auto, "take_screenshot", lambda *args, **kwargs: None)

        page = object.__new__(screen_module.Screen)
        page.screen_map = {
            "main": {"name": "主界面", "image_path": str(main_path), "actions": []},
            "menu": {"name": "菜单", "image_path": str(menu_path), "actions": []},
        }
        page.current_screen = None
        page.current_screen_threshold = 0
        page.lock = threading.Lock()
        page.logger = Mock()
        page.wait_screen_change_time = 0.5

        try:
            assert page.get_current_screen(autotry=False, max_retries=1) is True
            assert page.current_screen == "main"
            assert auto._frame_screenshot is frame  # 整轮扫描共用一个帧缓存
        finally:
            auto.screenshot = previous_screenshot
            auto.img_cache = previous_cache
            auto._frame_screenshot = None
            auto._frame_rgb = auto._frame_bgr = auto._frame_gray = None


class TestOcrGcInterval:
    def test_interval_is_five(self):
        from module.ocr.ocr import OCR_PERIODIC_FULL_GC_INTERVAL

        assert OCR_PERIODIC_FULL_GC_INTERVAL == 5

    def test_full_gc_runs_every_five_recognitions(self, monkeypatch):
        import importlib

        ocr_module = importlib.import_module("module.ocr.ocr")

        collected = []
        monkeypatch.setattr(ocr_module.gc, "collect", lambda: collected.append(1))
        detector = object.__new__(ocr_module.OCR)
        detector._periodic_gc_interval = ocr_module.OCR_PERIODIC_FULL_GC_INTERVAL
        detector.ocr_count = 0

        for count in range(1, 21):
            detector.ocr_count = count
            detector._maybe_collect_garbage()

        assert len(collected) == 4  # 第 5、10、15、20 次


class TestLocalInputPause:
    def test_default_pyautogui_pause_disabled(self):
        from module.automation import local_input

        assert local_input.pyautogui.PAUSE == 0
        assert local_input._CLICK_HOLD > 0

    def test_mouse_click_keeps_press_gap_and_order(self, monkeypatch):
        from module.automation import local_input

        events = []
        platform = local_input.pyautogui.platformModule
        monkeypatch.setattr(platform, "_moveTo", lambda *args, **kwargs: events.append("move"))
        monkeypatch.setattr(platform, "_mouseDown", lambda *args, **kwargs: events.append("down"))
        monkeypatch.setattr(platform, "_mouseUp", lambda *args, **kwargs: events.append("up"))

        backend = local_input.LocalInput(Mock())
        started = time.monotonic()
        backend.mouse_click(5, 6)
        elapsed = time.monotonic() - started

        assert events.count("down") == 1
        assert events.count("up") == 1
        assert events.index("down") < events.index("up")
        assert elapsed >= local_input._CLICK_HOLD * 0.9

    def test_mouse_scroll_keeps_per_notch_gap(self, monkeypatch):
        from module.automation import local_input

        events = []
        platform = local_input.pyautogui.platformModule
        monkeypatch.setattr(platform, "_scroll", lambda *args, **kwargs: events.append("scroll"))

        backend = local_input.LocalInput(Mock())
        started = time.monotonic()
        backend.mouse_scroll(2, 1, pause=True)
        elapsed = time.monotonic() - started

        assert events == ["scroll", "scroll"]
        assert elapsed >= 0.2 * 0.9

    def test_windows_input_scroll_keeps_its_own_gap(self, monkeypatch):
        import importlib

        pyautogui = importlib.import_module("pyautogui")
        windows_input = importlib.import_module("module.automation.windows_input")
        calls = []
        monkeypatch.setattr(pyautogui, "scroll", lambda *args, **kwargs: calls.append((args, kwargs)))

        api = object.__new__(windows_input.WindowsInputApi)
        started = time.monotonic()
        api.scroll(-1, True)
        elapsed = time.monotonic() - started

        assert calls == [((-1,), {"_pause": False})]  # 不依赖全局 PAUSE
        assert elapsed >= 0.1 * 0.9


class TestScreenshotResources:
    def test_capture_screen_reuses_mss_instance_per_thread(self, monkeypatch):
        from module.automation import screenshot as screenshot_module

        created = []

        def factory():
            created.append(threading.get_ident())
            return SimpleNamespace(
                grab=lambda region: SimpleNamespace(size=(2, 3), rgb=b"\x00" * 18),
                close=lambda: None,
            )

        monkeypatch.setattr(screenshot_module, "_MSS_LOCAL", threading.local())
        monkeypatch.setitem(sys.modules, "mss", SimpleNamespace(MSS=factory, mss=factory))

        region = {"left": 0, "top": 0, "width": 2, "height": 3}
        screenshot_module.Screenshot.capture_screen_with_mss(region)
        screenshot_module.Screenshot.capture_screen_with_mss(region)
        assert len(created) == 1  # 同一线程复用

        thread = threading.Thread(target=lambda: screenshot_module.Screenshot.capture_screen_with_mss(region))
        thread.start()
        thread.join()
        assert len(created) == 2  # mss 实例不跨线程共享

        screenshot_module.reset_mss_cache()

    def test_capture_screen_rebuilds_stale_mss_instance(self, monkeypatch):
        from module.automation import screenshot as screenshot_module

        created = []

        def factory():
            created.append(1)
            if len(created) == 1:
                def failing_grab(region):
                    raise OSError("设备上下文失效")
                return SimpleNamespace(grab=failing_grab, close=lambda: None)
            return SimpleNamespace(
                grab=lambda region: SimpleNamespace(size=(2, 3), rgb=b"\x00" * 18),
                close=lambda: None,
            )

        monkeypatch.setattr(screenshot_module, "_MSS_LOCAL", threading.local())
        monkeypatch.setitem(sys.modules, "mss", SimpleNamespace(MSS=factory, mss=factory))

        image = screenshot_module.Screenshot.capture_screen_with_mss(
            {"left": 0, "top": 0, "width": 2, "height": 3}
        )
        assert image.size == (2, 3)
        assert len(created) == 2  # 失效实例被丢弃并重建一次

    def test_capture_window_background_releases_gdi_on_failure(self, monkeypatch):
        import ctypes

        from module.automation import screenshot as screenshot_module

        events = []

        class DeviceContext:
            def __init__(self, name):
                self.name = name

            def CreateCompatibleDC(self):
                return DeviceContext("save")

            def DeleteDC(self):
                events.append(f"delete_dc:{self.name}")

            def SelectObject(self, bitmap):
                events.append("select")

            def GetSafeHdc(self):
                return 7

        class Bitmap:
            def CreateCompatibleBitmap(self, dc, width, height):
                events.append("create_bitmap")

            def GetHandle(self):
                return 21

            def GetInfo(self):
                return {"bmWidth": 4, "bmHeight": 4}

            def GetBitmapBits(self, flag):
                return b"\x00" * 64

        fake_win32gui = SimpleNamespace(
            GetWindowDC=lambda hwnd: events.append("get_dc") or 11,
            SendMessage=lambda *args: events.append("paint"),
            DeleteObject=lambda handle: events.append(f"delete_object:{handle}"),
            ReleaseDC=lambda hwnd, dc: events.append(f"release_dc:{hwnd}:{dc}"),
        )
        fake_win32ui = SimpleNamespace(
            CreateDCFromHandle=lambda dc: DeviceContext("mfc"),
            CreateBitmap=lambda: Bitmap(),
        )
        monkeypatch.setitem(sys.modules, "win32gui", fake_win32gui)
        monkeypatch.setitem(sys.modules, "win32ui", fake_win32ui)
        monkeypatch.setitem(sys.modules, "win32con", SimpleNamespace(WM_PAINT=0x000F))
        monkeypatch.setattr(
            ctypes,
            "windll",
            SimpleNamespace(user32=SimpleNamespace(PrintWindow=lambda *args: 0)),
        )

        result = screenshot_module.Screenshot.capture_window_background(1, (0, 0, 4, 4), (0, 0, 1, 1))

        assert result is None
        assert "delete_object:21" in events
        assert events[-1] == "release_dc:1:11"
