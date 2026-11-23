"""Android 虚拟屏启动期间的低频取样。帧序号来自 ImageReader，截图可以命中缓存。"""
import numpy as np
from PIL import Image

from module.game.adb_transport import AdbError
from module.localization import tr
from module.logger import log
from utils.pause import pause_ctl


_SAMPLE_SECONDS = 3
_MAX_GAP_MS = 8000
_MAX_FRAME_GAP_MS = 15000
_CONFIRM_MS = 45000


class StartupFrameHealth:
    def __init__(self):
        self.next_sample = 0.0
        self.context = None
        self.last_poll_ms = 0
        self._reset_frames()

    def _reset_frames(self):
        self.source_seq = None
        self.source_since = 0
        self.image_seq = None
        self.previous = None
        self.last_black = None
        self.black_since = None
        self.black_samples = 0
        self.last_image_ms = 0

    def _sample(self, image, seq, now):
        thumb = image.resize((80, 45), Image.Resampling.NEAREST)
        rgb = np.asarray(thumb)
        luma = np.asarray(thumb.convert("L"), dtype=np.int16)
        mean = luma.mean()
        nonblack = (rgb.max(axis=2) > 8).mean()
        peak = int(rgb.max())
        delta = None if self.previous is None else np.abs(luma - self.previous).mean()
        # 抽样全暗时再查整张 RGB 图，保护细小的加载文字、光标或进度点。
        if mean <= 3 and nonblack <= 0.001 and peak <= 16:
            peak = max(high for _, high in image.getextrema())
        black = mean <= 3 and nonblack <= 0.001 and peak <= 16
        if not black or now - self.last_image_ms > _MAX_FRAME_GAP_MS or (delta is not None and delta > 1.5):
            self.black_since = None
            self.black_samples = 0
        if black:
            if self.black_since is None:
                self.black_since = now
            self.black_samples += 1
        self.image_seq, self.previous, self.last_black, self.last_image_ms = seq, luma, black, now
        log.debug(f"ADB 启动画面 seq={seq} mean={mean:.2f} nonblack={nonblack:.5f} peak={peak} "
                  f"delta={None if delta is None else round(float(delta), 2)} black_samples={self.black_samples}")

    def _observe(self, snapshot, image, seq):
        now = snapshot["device_ms"]
        dog, source = snapshot["watchdog"], snapshot["frame"]
        task = dog.get("task") or {}
        log.debug(f"ADB 启动取帧 device_ms={now} display={snapshot['display_id']} pid={dog.get('pid')} "
                  f"task={task} checked_ms={dog.get('task_checked_ms')} interactive={dog.get('interactive')} "
                  f"locked={dog.get('keyguard_locked')} sdk_window={dog.get('sdk_window')} reader={source}")
        if (dog["target_display_id"] != snapshot["display_id"] or task.get("display_id") != snapshot["display_id"]
                or dog["pid"] <= 0 or task.get("task_id", -1) < 0 or not task.get("top_activity")
                or dog["interactive"] is not True or dog["keyguard_locked"] is not False or dog["sdk_window"]
                or not 0 <= now - dog["task_checked_ms"] <= 3000 or source["capturing"] is not True):
            self.context = None
            return None
        context = (snapshot["display_id"], dog["pid"], task["task_id"], task["top_activity"], snapshot["last_transition"])
        if context != self.context or not 0 < now - self.last_poll_ms <= _MAX_GAP_MS:
            self._reset_frames()
        self.context, self.last_poll_ms = context, now

        if source["seq"] != self.source_seq:
            self.source_seq, self.source_since = source["seq"], now
        if image is not None and seq != self.image_seq and 0 < seq <= self.source_seq:
            self._sample(image, seq, now)
            if (self.black_since is not None and now - self.black_since >= _CONFIRM_MS
                    and self.black_samples >= 6 and 0 <= source["age_ms"] <= _MAX_GAP_MS):
                return "virtual_display_black"
        # 静止的有效 SDK 页面也会复用缓存；只有缺画面并且生产端确实停帧才报错。
        if ((self.last_black is not False or image is None) and now - self.source_since >= _CONFIRM_MS
                and (source["age_ms"] == -1 or source["age_ms"] >= _CONFIRM_MS)):
            return "frame_timeout"
        return None

    def check(self, controller, frame, now, deadline):
        if now < self.next_sample or deadline - now < 4:
            return
        self.next_sample = now + _SAMPLE_SECONDS
        try:
            snapshot = controller.startup_frame_snapshot()
            if not isinstance(snapshot, dict):
                self.context = None
                return
            reason = self._observe(snapshot, frame[0] if frame else None, controller.frame_sequence)
        except AdbError:
            # 同一份 events 应答还会交付人工登录、退出和断线等运行错误。
            raise
        except Exception as error:
            self.context = None
            log.debug(f"ADB 启动画面取样不可用：{error}")
            return
        if reason:
            pause_ctl.check_stop()
            controller.log_startup_evidence(deadline)
            pause_ctl.check_stop()
            if reason == "virtual_display_black":
                raise AdbError(reason, tr("游戏已启动，但后台虚拟屏持续输出黑帧，请导出本轮日志反馈"))
            raise AdbError(reason, tr("游戏已启动，但后台虚拟屏持续没有新帧，请导出本轮日志反馈"))
