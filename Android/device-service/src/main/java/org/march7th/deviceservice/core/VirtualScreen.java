package org.march7th.deviceservice.core;

import android.content.Context;
import android.graphics.PixelFormat;
import android.hardware.display.DisplayManager;
import android.hardware.display.VirtualDisplay;
import android.media.Image;
import android.media.ImageReader;
import android.os.Build;
import android.os.Handler;
import android.os.Process;
import android.os.SystemClock;
import android.view.Display;
import android.view.Surface;

import org.json.JSONException;
import org.json.JSONObject;
import org.march7th.deviceservice.protocol.FrameEncoder;
import org.march7th.deviceservice.protocol.FrameSequencer;
import org.march7th.deviceservice.protocol.Protocol;

import java.lang.reflect.Constructor;
import java.util.Arrays;
import java.util.StringJoiner;
import java.util.concurrent.TimeoutException;

/**
 * 一块独立的虚拟屏，加上从它取帧的 ImageReader。
 *
 * 取帧不逐帧拷贝：采集线程只把最新的 Image 留在手里并给它编号，等客户端要帧时才把像素拷出来。
 */
final class VirtualScreen {
    // DisplayManager 里的隐藏标志位
    private static final int FLAG_SUPPORTS_TOUCH = 1 << 6;
    private static final int FLAG_ROTATES_WITH_CONTENT = 1 << 7;
    private static final int FLAG_DESTROY_CONTENT_ON_REMOVAL = 1 << 8;
    private static final int FLAG_TRUSTED = 1 << 10;
    private static final int FLAG_OWN_DISPLAY_GROUP = 1 << 11;
    private static final int FLAG_ALWAYS_UNLOCKED = 1 << 12;
    private static final int FLAG_TOUCH_FEEDBACK_DISABLED = 1 << 13;
    private static final int FLAG_OWN_FOCUS = 1 << 14;
    private static final int FLAG_DEVICE_DISPLAY_GROUP = 1 << 15;

    /** 手里始终留着最新的一帧，新帧到来时会短暂同时持有两帧，再留两个空位给合成方周转。 */
    private static final int MAX_IMAGES = 4;

    final String name;
    final int width;
    final int height;
    final int dpi;
    final boolean destroyContent;
    final int flags;
    final int displayId;

    private final FrameSequencer sequencer;
    private final long generation;
    private final ImageReader reader;
    private final VirtualDisplay display;
    // 用 sequencer 的锁同时保护 Image 和帧元数据，等待结束后可以原子地选帧和复制。
    private Image latest;
    private boolean released;
    /** 已经收到通知但还没取走的帧数，只在采集线程上读写。 */
    private int pending;

    VirtualScreen(String name, int width, int height, int dpi, boolean destroyContent,
                  FrameSequencer sequencer, Handler captureHandler) throws CommandException, JSONException {
        this.name = name;
        this.width = width;
        this.height = height;
        this.dpi = dpi;
        this.destroyContent = destroyContent;
        this.sequencer = sequencer;
        this.flags = flagsFor(destroyContent, Build.VERSION.SDK_INT);
        String stage = "ShellContext";
        ShellContext context = null;
        try {
            context = ShellContext.get();
            stage = "DisplayManager.<init>";
            Logger.i(stage + " start");
            Constructor<DisplayManager> constructor = DisplayManager.class.getDeclaredConstructor(Context.class);
            constructor.setAccessible(true);
            DisplayManager manager = constructor.newInstance(context);
            Logger.i(stage + " ready");
            stage = "ImageReader.newInstance";
            reader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, MAX_IMAGES);
            synchronized (sequencer) {
                VirtualDisplay created = null;
                try {
                    stage = "ImageReader.setOnImageAvailableListener";
                    reader.setOnImageAvailableListener(this::onImageAvailable, captureHandler);
                    stage = "ImageReader.getSurface";
                    Surface surface = reader.getSurface();
                    stage = "DisplayManager.createVirtualDisplay";
                    Logger.i(stage + " start");
                    created = manager.createVirtualDisplay(name, width, height, dpi, surface, flags);
                    if (created == null) {
                        throw new IllegalStateException("returned null");
                    }
                    stage = "VirtualDisplay.getDisplay";
                    displayId = created.getDisplay().getDisplayId();
                    display = created;
                    generation = sequencer.setActive(true);
                } catch (RuntimeException | Error e) {
                    released = true;
                    try {
                        closeResources(created, null);
                    } catch (RuntimeException cleanup) {
                        e.addSuppressed(cleanup);
                    }
                    throw e;
                }
            }
        } catch (ReflectiveOperationException | RuntimeException | LinkageError e) {
            String message = stage + ": " + Logger.describe(e);
            String device = "sdk=" + Build.VERSION.SDK_INT + " release=" + Build.VERSION.RELEASE
                    + " incremental=" + Build.VERSION.INCREMENTAL + " manufacturer=" + Build.MANUFACTURER
                    + " model=" + Build.MODEL + " device=" + Build.DEVICE
                    + " pid=" + Process.myPid() + " uid=" + Process.myUid() + " package=" + ShellContext.PACKAGE
                    + " flags=" + flagDescription(flags)
                    + " base=" + (context != null && context.getBaseContext() != null);
            Logger.e(message + " (" + device + ")", e);
            String diagnostic = stage + " " + device + "\n" + ShellContext.initializationTrace() + "\n" + Logger.stackTrace(e);
            String code = context == null ? Protocol.E_SHELL_CONTEXT_INIT_FAILED : Protocol.E_DISPLAY_FAILED;
            throw new CommandException(code, message, new JSONObject().put("diagnostic", diagnostic));
        }
    }

    /**
     * 标志位沿用原型：公开、独立内容、支持触摸、移除时销毁内容。
     * Android 13、14 追加的几项照 scrcpy 的新建虚拟屏写法补上（未在实机验证）。
     */
    static int flagsFor(boolean destroyContent, int sdk) {
        int flags = DisplayManager.VIRTUAL_DISPLAY_FLAG_PUBLIC
                | DisplayManager.VIRTUAL_DISPLAY_FLAG_PRESENTATION
                | DisplayManager.VIRTUAL_DISPLAY_FLAG_OWN_CONTENT_ONLY
                | FLAG_SUPPORTS_TOUCH
                | FLAG_ROTATES_WITH_CONTENT;
        if (destroyContent) {
            flags |= FLAG_DESTROY_CONTENT_ON_REMOVAL;
        }
        if (sdk >= 33) {
            flags |= FLAG_TRUSTED | FLAG_OWN_DISPLAY_GROUP | FLAG_ALWAYS_UNLOCKED | FLAG_TOUCH_FEEDBACK_DISABLED;
        }
        if (sdk >= 34) {
            flags |= FLAG_OWN_FOCUS | FLAG_DEVICE_DISPLAY_GROUP;
        }
        return flags;
    }

    static String flagDescription(int flags) {
        String[] names = {"PUBLIC", "PRESENTATION", "SECURE", "OWN_CONTENT_ONLY", "AUTO_MIRROR",
                "CAN_SHOW_WITH_INSECURE_KEYGUARD", "SUPPORTS_TOUCH", "ROTATES_WITH_CONTENT",
                "DESTROY_CONTENT_ON_REMOVAL", "SHOULD_SHOW_SYSTEM_DECORATIONS", "TRUSTED", "OWN_DISPLAY_GROUP",
                "ALWAYS_UNLOCKED", "TOUCH_FEEDBACK_DISABLED", "OWN_FOCUS", "DEVICE_DISPLAY_GROUP"};
        StringJoiner enabled = new StringJoiner("|");
        for (int i = 0; i < names.length; i++) {
            if ((flags & (1 << i)) != 0) enabled.add(names[i]);
        }
        return "0x" + Integer.toHexString(flags) + " " + enabled;
    }

    /** 在建屏和启动失败时采样。ROM 缺失的字段单独记录，已创建的屏可以继续使用。 */
    JSONObject diagnostics() {
        JSONObject info = new JSONObject();
        try {
            info.put("creation_flags", flagDescription(flags));
            info.put("service_pid", Process.myPid());
            info.put("service_uid", Process.myUid());
            info.put("service_package", ShellContext.PACKAGE);
            info.put("display_info", SystemApis.displayInfo(displayId));
        } catch (Exception | LinkageError e) {
            Logger.w("cannot read virtual DisplayInfo", e);
        }
        try {
            Display screen = display.getDisplay();
            info.put("supported_modes", Arrays.toString(screen.getSupportedModes()));
            info.put("mode", String.valueOf(screen.getMode()));
            info.put("refresh_rate", screen.getRefreshRate());
        } catch (Exception | LinkageError e) {
            Logger.w("cannot read virtual display modes", e);
        }
        return info;
    }

    /**
     * 每来一帧回调一次，来几帧就取几帧，不多取。
     *
     * 不能用 acquireLatestImage()，也不能循环取到空为止：队列已空时再取一次，在 Redmi Note 7（Android 10）上
     * 会让虚拟屏里的游戏从约 27 帧每秒掉到 6 到 14 帧每秒。所以这里自己数还有几帧没取。
     */
    private void onImageAvailable(ImageReader source) {
        pending++;
        while (pending > 0) {
            Image image;
            try {
                image = source.acquireNextImage();
            } catch (IllegalStateException e) {
                // 读取器已经关闭，或者暂时没有空位；欠着的这一帧留到下次回调再取
                return;
            }
            if (image == null) {
                pending = 0;
                return;
            }
            pending--;
            long acquiredNs = System.nanoTime();
            long acquiredMs = SystemClock.elapsedRealtime();
            Image previous;
            synchronized (sequencer) {
                if (released) {
                    image.close();
                    return;
                }
                previous = latest;
                latest = image;
                sequencer.publish(image.getTimestamp(), acquiredNs, acquiredMs);
            }
            if (previous != null) {
                previous.close();
            }
        }
    }

    FrameSequencer.Frame latestFrame() {
        synchronized (sequencer) {
            return released ? null : sequencer.current();
        }
    }

    FrameSequencer.Frame awaitFrame(long minSeq, Long afterNs, long timeoutMs)
            throws InterruptedException, TimeoutException {
        return sequencer.await(generation, minSeq, afterNs, timeoutMs);
    }

    /** 必须在选中帧的同一个 synchronized (sequencer) 内调用。 */
    void copyLatest(int x, int y, int w, int h, int channels, byte[] out) {
        Image.Plane plane = rgbaPlane();
        FrameEncoder.copyRegion(plane.getBuffer(), plane.getRowStride(), x, y, w, h, channels, out);
    }

    /** 与任务截图共用已采集的 Image，调用方持有 sequencer 锁。 */
    void copyThumbnail(int w, int h, byte[] out) {
        Image.Plane plane = rgbaPlane();
        FrameEncoder.copyThumbnail(plane.getBuffer(), plane.getRowStride(), width, height, w, h, out);
    }

    private Image.Plane rgbaPlane() {
        Image.Plane plane = latest.getPlanes()[0];
        if (plane.getPixelStride() != 4) {
            throw new IllegalStateException("unexpected pixel stride " + plane.getPixelStride());
        }
        return plane;
    }

    void release() {
        Image last;
        synchronized (sequencer) {
            if (released) {
                return;
            }
            released = true;
            last = latest;
            latest = null;
            sequencer.setActive(false);
        }
        closeResources(display, last);
    }

    private void closeResources(VirtualDisplay created, Image last) {
        if (created != null) {
            try {
                created.release();
            } catch (RuntimeException e) {
                Logger.w("virtual display release failed", e);
            }
        }
        try {
            if (last != null) {
                last.close();
            }
        } finally {
            reader.close();
        }
    }
}
