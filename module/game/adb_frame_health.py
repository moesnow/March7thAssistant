"""虚拟屏启动及运行共用的低频健康检查；截图缓存不能替代生产端帧序号。"""
import time

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
_FOCUS_STALL_MS = 10000
_RECOVERY_COOLDOWN_MS = 10000


class VirtualFrameHealth:
    def __init__(self):
        self.next_sample = 0.0
        self.context = None
        self.last_poll_ms = 0
        self.recovery_checked = False
        self.recovery_at = 0
        self.recovery_seq = -1
        self.recovery_reason = None
        self.recovered = False
        self.healthy_since = None
        self.healthy_samples = 0
        self.healthy_seq = -1
        self.unrecovered_since = None
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
        self._record_black(black, seq, now, changed=delta is not None and delta > 1.5)
        self.previous = luma
        log.debug(f"ADB 虚拟屏画面 seq={seq} mean={mean:.2f} nonblack={nonblack:.5f} peak={peak} "
                  f"delta={None if delta is None else round(float(delta), 2)} black_samples={self.black_samples}")

    def _record_black(self, black, seq, now, *, changed=False):
        if not black or now - self.last_image_ms > _MAX_FRAME_GAP_MS or changed:
            self.black_since = None
            self.black_samples = 0
        if black:
            if self.black_since is None:
                self.black_since = now
            self.black_samples += 1
        self.image_seq, self.last_black, self.last_image_ms = seq, black, now

    def _observe(self, snapshot, image, seq):
        now = snapshot["device_ms"]
        dog, source = snapshot["watchdog"], snapshot["frame"]
        task = dog.get("task") or {}
        log.debug(f"ADB 虚拟屏取帧 device_ms={now} display={snapshot['display_id']} pid={dog.get('pid')} "
                  f"task={task} checked_ms={dog.get('task_checked_ms')} interactive={dog.get('interactive')} "
                  f"locked={dog.get('keyguard_locked')} sdk_window={dog.get('sdk_window')} reader={source}")
        if (dog["target_display_id"] != snapshot["display_id"] or task.get("display_id") != snapshot["display_id"]
                or dog["pid"] <= 0 or task.get("task_id", -1) < 0 or not task.get("top_activity")
                or dog["interactive"] is not True or dog["keyguard_locked"] is not False or dog["sdk_window"]
                or not 0 <= now - dog["task_checked_ms"] <= 3000 or source["capturing"] is not True):
            self.context = None
            self.healthy_since = None
            self.healthy_samples = 0
            self.unrecovered_since = None
            return None
        context = (snapshot["display_id"], dog["pid"], task["task_id"], task["top_activity"], snapshot["last_transition"])
        if context != self.context or not 0 < now - self.last_poll_ms <= _MAX_GAP_MS:
            self._reset_frames()
            self.healthy_since = None
            self.healthy_samples = 0
            self.unrecovered_since = None
        self.context, self.last_poll_ms = context, now

        if source["seq"] != self.source_seq:
            self.source_seq, self.source_since = source["seq"], now
        # 新服务对完整原帧取样，因此运行期只截取一小块区域也不会误把黑色裁剪当成整屏黑帧。
        if type(source.get("black")) is bool and source["seq"] != self.image_seq:
            self._record_black(source["black"], source["seq"], now)
        elif image is not None and seq != self.image_seq and 0 < seq <= self.source_seq:
            self._sample(image, seq, now)
        self._observe_recovery(source, now)
        if self.unrecovered_since is not None and now - self.unrecovered_since >= _CONFIRM_MS:
            return "frame_timeout" if source["age_ms"] == -1 or source["age_ms"] >= _FOCUS_STALL_MS else "virtual_display_black"
        if (self.black_since is not None and now - self.black_since >= _CONFIRM_MS
                and self.black_samples >= 6 and 0 <= source["age_ms"] <= _MAX_GAP_MS):
            return "virtual_display_black"
        # 静止的有效 SDK 页面也会复用缓存；只有缺画面并且生产端确实停帧才报错。
        if ((self.last_black is not False or (image is None and type(source.get("black")) is not bool))
                and now - self.source_since >= _CONFIRM_MS
                and (source["age_ms"] == -1 or source["age_ms"] >= _CONFIRM_MS)):
            return "frame_timeout"
        return None

    def _observe_recovery(self, source, now):
        if not self.recovery_checked and self.unrecovered_since is None:
            return
        fresh = 0 <= source["age_ms"] <= 3000 and source["seq"] > self.recovery_seq
        if self.recovery_reason in {"frame_timeout", "move_back"} and fresh:
            self.recovered = True
        if not fresh or self.last_black is not False:
            self.healthy_since = None
            self.healthy_samples = 0
        elif source["seq"] != self.healthy_seq:
            if self.healthy_since is None:
                self.healthy_since = now
            self.healthy_samples += 1
            self.healthy_seq = source["seq"]
            if now - self.healthy_since >= 6000 and self.healthy_samples >= 3:
                self.recovered = True
                self.unrecovered_since = None
        if self.recovery_checked and self.recovered and now - self.recovery_at >= _RECOVERY_COOLDOWN_MS:
            self.recovery_checked = False
            log.info("后台虚拟屏已有新帧，继续确认游戏画面")

    def check(self, controller, frame, now, deadline, *, startup=False):
        if now < self.next_sample or deadline - now < 4:
            return
        self.next_sample = now + _SAMPLE_SECONDS
        try:
            snapshot = controller.frame_health_snapshot(deadline)
            if not isinstance(snapshot, dict):
                self.context = None
                return
            reason = self._observe(snapshot, frame[0] if frame else None, controller.frame_sequence)
        except AdbError:
            # 同一份 events 应答还会交付人工登录、退出和断线等运行错误。
            raise
        except Exception as error:
            self.context = None
            log.debug(f"ADB 虚拟屏画面取样不可用：{error}")
            return
        stalled = (self.context is not None
                   and (not startup or self.last_black is not False or frame is None
                        or snapshot["watchdog"].get("auto_focus") is True)
                   and (snapshot["device_ms"] - self.source_since >= _FOCUS_STALL_MS
                        or snapshot["watchdog"].get("frames_stalled") is True)
                   and (snapshot["frame"]["age_ms"] == -1 or snapshot["frame"]["age_ms"] >= _FOCUS_STALL_MS))
        # 运行期页面等待通常比冷启动短，先尝试恢复，失败判定仍沿用连续 45 秒的证据。
        black_during_run = (not startup and self.context is not None and self.black_since is not None
                            and snapshot["device_ms"] - self.black_since >= _FOCUS_STALL_MS
                            and self.black_samples >= 4)
        move = controller.pending_move_focus(snapshot) if self.context is not None else False
        expired = self.unrecovered_since is not None and snapshot["device_ms"] - self.unrecovered_since >= _CONFIRM_MS
        if (move or (not self.recovery_checked and not expired)) and (move or reason or stalled or black_during_run):
            kind = "move_back" if move else reason or ("virtual_display_black" if black_during_run else "frame_timeout")
            self.recovery_checked = True
            self.recovered = False
            self.recovery_at = snapshot["device_ms"]
            self.recovery_seq = snapshot["frame"]["seq"]
            self.recovery_reason = kind
            self.healthy_since = None
            self.healthy_samples = 0
            pause_ctl.check_stop()
            continued = controller.recover_display_focus(snapshot, kind, deadline)
            pause_ctl.check_stop()
            if time.monotonic() >= deadline:
                return
            if continued:
                if continued == "deferred":
                    self.recovery_checked = False
                    self.next_sample = time.monotonic() + _RECOVERY_COOLDOWN_MS / 1000
                elif self.unrecovered_since is None:
                    self.unrecovered_since = snapshot["device_ms"]
                self._reset_frames()
                return
        if reason:
            pause_ctl.check_stop()
            controller.log_startup_evidence(deadline)
            pause_ctl.check_stop()
            if reason == "virtual_display_black":
                raise AdbError(reason, tr("游戏已启动，但后台虚拟屏持续输出黑帧，请导出本轮日志反馈"))
            raise AdbError(reason, tr("游戏已启动，但后台虚拟屏持续没有新帧，请导出本轮日志反馈"))
