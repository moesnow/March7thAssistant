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
                  FrameSequencer sequencer, Handler captureHandler) throws ReflectiveOperationException {
        this.name = name;
        this.width = width;
        this.height = height;
        this.dpi = dpi;
        this.destroyContent = destroyContent;
        this.sequencer = sequencer;
        this.flags = flagsFor(destroyContent);
        reader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, MAX_IMAGES);
        synchronized (sequencer) {
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
                    released = true;
                    reader.close();
                }
            }
            display = created;
            displayId = display.getDisplay().getDisplayId();
            generation = sequencer.setActive(true);
        }
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
        Image.Plane plane = latest.getPlanes()[0];
        if (plane.getPixelStride() != 4) {
            throw new IllegalStateException("unexpected pixel stride " + plane.getPixelStride());
        }
        FrameEncoder.copyRegion(plane.getBuffer(), plane.getRowStride(), x, y, w, h, channels, out);
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
        try {
            display.release();
        } catch (RuntimeException e) {
            Logger.w("virtual display release failed", e);
        }
        if (last != null) {
            last.close();
        }
        reader.close();
    }
}
