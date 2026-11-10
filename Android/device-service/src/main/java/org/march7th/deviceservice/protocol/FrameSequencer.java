package org.march7th.deviceservice.protocol;

import java.util.concurrent.TimeoutException;

/**
 * 帧序号。
 *
 * 序号记录发布顺序，在服务进程内单调递增。等待只接受本次采集的帧，可另外限制生产时间。
 */
public final class FrameSequencer {
    // ImageReader 的时钟由生产方决定。拒绝缺失、在未来或明显偏离本机单调时钟的时间戳。
    private static final long MAX_ACQUIRE_LAG_NS = 1_000_000_000L;

    public static final class Frame {
        public final long seq;
        public final long imageNs;
        public final long acquiredNs;
        public final long acquiredMs;
        public final boolean timestampComparable;

        private Frame(long seq, long imageNs, long acquiredNs, long acquiredMs) {
            this.seq = seq;
            this.imageNs = imageNs;
            this.acquiredNs = acquiredNs;
            this.acquiredMs = acquiredMs;
            timestampComparable = imageNs > 0 && acquiredNs >= imageNs && acquiredNs - imageNs <= MAX_ACQUIRE_LAG_NS;
        }

        public boolean isAfter(long afterNs) {
            return timestampComparable && imageNs > afterNs;
        }
    }

    private long latest;
    private long generation;
    private boolean active;
    private Frame current;

    /** 开始或停止采集，返回这次采集的代号。旧屏上的等待不会被重建后的帧满足。 */
    public synchronized long setActive(boolean active) {
        if (this.active != active) {
            this.active = active;
            generation++;
            current = null;
            notifyAll();
        }
        return generation;
    }

    public synchronized boolean isActive() {
        return active;
    }

    public synchronized Frame publish(long imageNs, long acquiredNs, long acquiredMs) {
        if (!active) {
            throw new IllegalStateException("capture is not active");
        }
        current = new Frame(++latest, imageNs, acquiredNs, acquiredMs);
        notifyAll();
        return current;
    }

    /** 最新一帧的序号，还没有帧时为 0。 */
    public synchronized long latest() {
        return latest;
    }

    /** 当前屏上的最新帧，首帧到来前为 null。 */
    public synchronized Frame current() {
        return current;
    }

    /**
     * 等到当前屏上最新帧的序号不小于 minSeq、生产时间严格晚于可选的 afterNs。
     *
     * @throws TimeoutException      超时仍没有等到
     * @throws IllegalStateException 采集没有开始，或者等待期间被停止
     */
    public synchronized Frame await(long expectedGeneration, long minSeq, Long afterNs, long timeoutMs)
            throws InterruptedException, TimeoutException {
        long deadline = System.nanoTime() + Math.max(timeoutMs, 0) * 1_000_000L;
        while (true) {
            if (!active || generation != expectedGeneration) {
                throw new IllegalStateException("capture is not active");
            }
            if (current != null && current.seq >= minSeq && (afterNs == null || current.isAfter(afterNs))) {
                return current;
            }
            long remaining = deadline - System.nanoTime();
            if (remaining <= 0) {
                throw new TimeoutException("latest=" + latest + " wanted=" + minSeq);
            }
            long millis = remaining / 1_000_000L;
            wait(millis, (int) (remaining - millis * 1_000_000L));
        }
    }
}
