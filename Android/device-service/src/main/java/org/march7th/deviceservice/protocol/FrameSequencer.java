package org.march7th.deviceservice.protocol;

import java.util.concurrent.TimeoutException;

/**
 * 帧序号。
 *
 * 序号从 1 开始，每发布一帧加一，在服务进程的生命周期内单调递增，重建虚拟屏也不归零。
 * 输入命令返回注入完成时的序号 s，客户端随后请求 min_seq = s + 1，拿到的一定是注入之后才合成的帧。
 */
public final class FrameSequencer {
    private long latest;
    private boolean active;

    /** 采集开始或停止。停止后正在等待的调用方会立刻收到 IllegalStateException。 */
    public synchronized void setActive(boolean active) {
        this.active = active;
        notifyAll();
    }

    public synchronized boolean isActive() {
        return active;
    }

    /** 发布一帧，返回它的序号。 */
    public synchronized long publish() {
        latest++;
        notifyAll();
        return latest;
    }

    /** 最新一帧的序号，还没有帧时为 0。 */
    public synchronized long latest() {
        return latest;
    }

    /**
     * 等到最新序号不小于 minSeq。
     *
     * @return 返回时的最新序号
     * @throws TimeoutException      超时仍没有等到
     * @throws IllegalStateException 采集没有开始，或者等待期间被停止
     */
    public synchronized long await(long minSeq, long timeoutMs) throws InterruptedException, TimeoutException {
        long wanted = Math.max(minSeq, 1);
        long deadline = System.nanoTime() + Math.max(timeoutMs, 0) * 1_000_000L;
        while (true) {
            if (!active) {
                throw new IllegalStateException("capture is not active");
            }
            if (latest >= wanted) {
                return latest;
            }
            long remaining = deadline - System.nanoTime();
            if (remaining <= 0) {
                throw new TimeoutException("latest=" + latest + " wanted=" + wanted);
            }
            long millis = remaining / 1_000_000L;
            wait(millis, (int) (remaining - millis * 1_000_000L));
        }
    }
}
