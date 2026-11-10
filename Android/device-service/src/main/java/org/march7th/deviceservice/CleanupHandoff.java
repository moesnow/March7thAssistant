package org.march7th.deviceservice;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.channels.OverlappingFileLockException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.concurrent.TimeUnit;

/** 主进程的单实例锁之外，串行交接仍可能修改设备状态的子进程。 */
final class CleanupHandoff {
    static final Path LOCK_PATH = Paths.get("/data/local/tmp/m7a-device-service.cleanup.lock");

    private CleanupHandoff() {
    }

    private static FileChannel open(Path path) throws IOException {
        return FileChannel.open(path, StandardOpenOption.CREATE, StandardOpenOption.READ, StandardOpenOption.WRITE);
    }

    /** 善后和备用恢复进程可以并存，新实例需要等两者都结束。 */
    static void runWorker(Path path, Runnable action) throws IOException {
        try (FileChannel channel = open(path)) {
            FileLock lock = channel.lock(0, Long.MAX_VALUE, true);
            try {
                action.run();
            } finally {
                lock.release();
            }
        }
    }

    /** 调用者持有主进程的单实例锁，取到排他锁后就可接管。 */
    static boolean awaitIdle(Path path, long deadlineNs) throws IOException, InterruptedException {
        try (FileChannel channel = open(path)) {
            while (true) {
                FileLock lock;
                try {
                    lock = channel.tryLock();
                } catch (OverlappingFileLockException e) {
                    lock = null;
                }
                if (lock != null) {
                    lock.release();
                    return true;
                }
                if (!pauseUntil(deadlineNs)) {
                    return false;
                }
            }
        }
    }

    static boolean pauseUntil(long deadlineNs) throws InterruptedException {
        long remaining = deadlineNs - System.nanoTime();
        if (remaining <= 0) {
            return false;
        }
        TimeUnit.NANOSECONDS.sleep(Math.min(remaining, 100_000_000L));
        return true;
    }
}
