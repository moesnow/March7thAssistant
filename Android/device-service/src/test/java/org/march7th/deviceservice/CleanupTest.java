package org.march7th.deviceservice;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.PipedReader;
import java.io.PipedWriter;
import java.io.PrintWriter;
import java.io.StringReader;
import java.io.StringWriter;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.FutureTask;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

public class CleanupTest {
    @Rule
    public final TemporaryFolder folder = new TemporaryFolder();

    @Test(timeout = 5000)
    public void parentDisconnectDuringMuteRestoresOnlyAfterTheWriteCompletes() throws Exception {
        List<String> writes = new CopyOnWriteArrayList<>();
        CountDownLatch writingMute = new CountDownLatch(1);
        CountDownLatch completeMute = new CountDownLatch(1);
        PipedWriter commands = new PipedWriter();
        PipedReader replyPipe = new PipedReader();
        try (BufferedReader incoming = new BufferedReader(new PipedReader(commands));
             PrintWriter outgoing = new PrintWriter(new PipedWriter(replyPipe), true)) {
            FutureTask<Void> cleanup = new FutureTask<>(() -> {
                Cleanup.run(incoming, outgoing, () -> { }, (pkg, on) -> {
                    assertTrue(on);
                    writingMute.countDown();
                    assertTrue(completeMute.await(2, TimeUnit.SECONDS));
                    writes.add("ignore");
                    return "allow";
                }, () -> writes.add("allow"), (message, error) -> { throw new AssertionError(message, error); });
                return null;
            });
            Thread worker = new Thread(cleanup, "cleanup-test");
            worker.setDaemon(true);
            worker.start();

            try (PipedWriter requestPipe = commands) {
                requestPipe.write("mute example.game\n");
                requestPipe.flush();
                assertTrue(writingMute.await(2, TimeUnit.SECONDS));
                // 主进程在 cmd 尚未返回时退出，收发两条管道都断开。
                replyPipe.close();
            }
            assertTrue(writes.isEmpty());
            completeMute.countDown();
            cleanup.get(2, TimeUnit.SECONDS);
            assertEquals(List.of("ignore", "allow"), writes);
        } finally {
            completeMute.countDown();
        }
    }

    @Test
    public void reportsACompletedWriteFailureAndKeepsTheRecoveryRecord() {
        StringWriter replies = new StringWriter();
        List<String> writes = new ArrayList<>();
        List<Exception> failures = new ArrayList<>();
        Cleanup.run(new BufferedReader(new StringReader("mute example.game\n")),
                new PrintWriter(replies), () -> { }, (pkg, on) -> {
                    writes.add("ignore");
                    throw new IOException("rejected");
                }, () -> writes.add("allow"), (message, error) -> failures.add(error));

        assertEquals(List.of("M7A_CLEANUP_FAILED mute example.game IOException: rejected"),
                replies.toString().lines().collect(java.util.stream.Collectors.toList()));
        assertEquals(List.of("ignore", "allow"), writes);
        assertEquals(1, failures.size());
    }

    @Test(timeout = 8000)
    public void replacementWaitsForOldWriteAndEofRestoreBeforeReadingOriginalMode() throws Exception {
        Path lock = folder.getRoot().toPath().resolve("cleanup.lock");
        AtomicReference<String> mode = new AtomicReference<>("allow");
        CountDownLatch applying = new CountDownLatch(1);
        CountDownLatch finishApply = new CountDownLatch(1);
        CountDownLatch restoring = new CountDownLatch(1);
        CountDownLatch finishRestore = new CountDownLatch(1);
        FutureTask<Void> oldCleanup = new FutureTask<>(() -> {
            CleanupHandoff.runWorker(lock, () -> {
                Cleanup.run(new BufferedReader(new StringReader("mute example.game\n")),
                        new PrintWriter(new StringWriter()), () -> { }, (pkg, on) -> {
                            applying.countDown();
                            assertTrue(finishApply.await(3, TimeUnit.SECONDS));
                            return mode.getAndSet("ignore");
                        }, () -> {
                            restoring.countDown();
                            assertTrue(finishRestore.await(3, TimeUnit.SECONDS));
                            mode.set("allow");
                        }, (message, error) -> { throw new AssertionError(message, error); });
            });
            return null;
        });
        Thread worker = new Thread(oldCleanup, "old-cleanup-test");
        worker.setDaemon(true);
        worker.start();
        try {
            assertTrue(applying.await(2, TimeUnit.SECONDS));
            assertFalse(CleanupHandoff.awaitIdle(lock, System.nanoTime()));

            FutureTask<String> replacement = new FutureTask<>(() -> {
                assertTrue(CleanupHandoff.awaitIdle(lock, System.nanoTime() + TimeUnit.SECONDS.toNanos(5)));
                return mode.getAndSet("ignore");
            });
            Thread next = new Thread(replacement, "replacement-test");
            next.setDaemon(true);
            next.start();

            finishApply.countDown();
            assertTrue(restoring.await(2, TimeUnit.SECONDS));
            assertFalse(CleanupHandoff.awaitIdle(lock, System.nanoTime()));
            assertFalse(replacement.isDone());
            finishRestore.countDown();
            oldCleanup.get(2, TimeUnit.SECONDS);
            assertEquals("allow", replacement.get(2, TimeUnit.SECONDS));
            assertEquals("ignore", mode.get());
        } finally {
            finishApply.countDown();
            finishRestore.countDown();
        }
    }

    @Test
    public void repliesWithOriginalModeAfterExplicitRestore() {
        StringWriter replies = new StringWriter();
        Cleanup.run(new BufferedReader(new StringReader(
                        "mute example.game\nrestore_audio example.game\n")),
                new PrintWriter(replies), () -> { }, (pkg, on) -> "allow",
                () -> { }, (message, error) -> { throw new AssertionError(message, error); });
        assertEquals(List.of("M7A_CLEANUP_OK mute example.game allow",
                        "M7A_CLEANUP_OK restore_audio example.game allow"),
                replies.toString().lines().collect(java.util.stream.Collectors.toList()));
    }
}
