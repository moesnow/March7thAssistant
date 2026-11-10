package org.march7th.deviceservice.core;

import android.graphics.PixelFormat;
import android.hardware.display.DisplayManager;
import android.hardware.display.VirtualDisplay;
import android.media.Image;
import android.media.ImageReader;
import android.os.Build;
import android.os.Handler;
import android.os.SystemClock;

import org.march7th.deviceservice.protocol.FrameEncoder;
import org.march7th.deviceservice.protocol.FrameSequencer;

import java.lang.reflect.Constructor;

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

    /** 拷出来的一帧。 */
    static final class Captured {
        long seq;
        /** Image.getTimestamp()，只适合和同一块屏上的其他帧比较。 */
        long imageNs;
        /** 采集线程拿到这一帧时的 SystemClock.elapsedRealtime()。 */
        long acquiredMs;
    }

    final String name;
    final int width;
    final int height;
    final int dpi;
    final boolean destroyContent;
    final int flags;
    final int displayId;

    private final FrameSequencer sequencer;
    private final ImageReader reader;
    private final VirtualDisplay display;
    private final Object lock = new Object();
    private Image latest;
    private long latestSeq;
    private long latestNs;
    private long latestAcquiredMs;
    private boolean released;
    /** 已经收到通知但还没取走的帧数，只在采集线程上读写。 */
    private int pending;

    VirtualScreen(String name, int width, int height, int dpi, boolean destroyContent,
                  FrameSequencer sequencer, Handler captureHandler) throws ReflectiveOperationException {
        this.name = name;
        this.width = width;
        this.height = height;
        this.dpi = dpi;
        this.destroyContent = destroyContent;
        this.sequencer = sequencer;
        this.flags = flagsFor(destroyContent);
        reader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, MAX_IMAGES);
        reader.setOnImageAvailableListener(this::onImageAvailable, captureHandler);
        VirtualDisplay created = null;
        try {
            Constructor<DisplayManager> constructor = DisplayManager.class.getDeclaredConstructor(android.content.Context.class);
            constructor.setAccessible(true);
            DisplayManager manager = constructor.newInstance(ShellContext.get());
            created = manager.createVirtualDisplay(name, width, height, dpi, reader.getSurface(), flags);
            if (created == null) {
                throw new IllegalStateException("createVirtualDisplay returned null");
            }
        } finally {
            if (created == null) {
                reader.close();
            }
        }
        display = created;
        displayId = display.getDisplay().getDisplayId();
        sequencer.setActive(true);
    }

    /**
     * 标志位沿用原型：公开、独立内容、支持触摸、移除时销毁内容。
     * Android 13、14 追加的几项照 scrcpy 的新建虚拟屏写法补上（未在实机验证）。
     */
    private static int flagsFor(boolean destroyContent) {
        int flags = DisplayManager.VIRTUAL_DISPLAY_FLAG_PUBLIC
                | DisplayManager.VIRTUAL_DISPLAY_FLAG_PRESENTATION
                | DisplayManager.VIRTUAL_DISPLAY_FLAG_OWN_CONTENT_ONLY
                | FLAG_SUPPORTS_TOUCH
                | FLAG_ROTATES_WITH_CONTENT;
        if (destroyContent) {
            flags |= FLAG_DESTROY_CONTENT_ON_REMOVAL;
        }
        if (Build.VERSION.SDK_INT >= 33) {
            flags |= FLAG_TRUSTED | FLAG_OWN_DISPLAY_GROUP | FLAG_ALWAYS_UNLOCKED | FLAG_TOUCH_FEEDBACK_DISABLED;
        }
        if (Build.VERSION.SDK_INT >= 34) {
            flags |= FLAG_OWN_FOCUS | FLAG_DEVICE_DISPLAY_GROUP;
        }
        return flags;
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
            Image previous;
            synchronized (lock) {
                if (released) {
                    image.close();
                    return;
                }
                previous = latest;
                latest = image;
                latestNs = image.getTimestamp();
                latestAcquiredMs = SystemClock.elapsedRealtime();
                latestSeq = sequencer.publish();
            }
            if (previous != null) {
                previous.close();
            }
        }
    }

    /** 最新一帧距离现在多久，还没有帧时为 -1。 */
    long frameAgeMs() {
        synchronized (lock) {
            return latest == null ? -1 : SystemClock.elapsedRealtime() - latestAcquiredMs;
        }
    }

    /**
     * 把最新一帧的一块区域拷到 out。
     *
     * @return 这一帧的序号和时间；还没有帧或者屏已经释放时返回 null
     */
    Captured copyLatest(int x, int y, int w, int h, int channels, byte[] out) {
        synchronized (lock) {
            if (released || latest == null) {
                return null;
            }
            Image.Plane plane = latest.getPlanes()[0];
            if (plane.getPixelStride() != 4) {
                throw new IllegalStateException("unexpected pixel stride " + plane.getPixelStride());
            }
            FrameEncoder.copyRegion(plane.getBuffer(), plane.getRowStride(), x, y, w, h, channels, out);
            Captured captured = new Captured();
            captured.seq = latestSeq;
            captured.imageNs = latestNs;
            captured.acquiredMs = latestAcquiredMs;
            return captured;
        }
    }

    void release() {
        synchronized (lock) {
            if (released) {
                return;
            }
            released = true;
        }
        sequencer.setActive(false);
        try {
            display.release();
        } catch (RuntimeException e) {
            Logger.w("virtual display release failed", e);
        }
        synchronized (lock) {
            if (latest != null) {
                latest.close();
                latest = null;
            }
        }
        reader.close();
    }
}
