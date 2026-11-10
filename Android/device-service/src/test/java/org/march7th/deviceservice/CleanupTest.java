package org.march7th.deviceservice;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.PipedReader;
import java.io.PipedWriter;
import java.io.PrintWriter;
import java.io.StringReader;
import java.io.StringWriter;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.FutureTask;
import java.util.concurrent.TimeUnit;

public class CleanupTest {
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
                Cleanup.run(incoming, outgoing, () -> { }, (pkg, mode) -> {
                    if ("ignore".equals(mode)) {
                        writingMute.countDown();
                        assertTrue(completeMute.await(2, TimeUnit.SECONDS));
                    }
                    writes.add(mode);
                }, (message, error) -> { throw new AssertionError(message, error); });
                return null;
            });
            Thread worker = new Thread(cleanup, "cleanup-test");
            worker.setDaemon(true);
            worker.start();

            try (PipedWriter requestPipe = commands; BufferedReader replies = new BufferedReader(replyPipe)) {
                requestPipe.write("mute example.game default\n");
                requestPipe.flush();
                assertEquals("M7A_CLEANUP_OK mute example.game default", replies.readLine());
                assertTrue(writes.isEmpty());
                requestPipe.write("apply_mute example.game\n");
                requestPipe.flush();
                assertTrue(writingMute.await(2, TimeUnit.SECONDS));
                // 主进程在 cmd 尚未返回时退出，收发两条管道都断开。
            }
            assertTrue(writes.isEmpty());
            completeMute.countDown();
            cleanup.get(2, TimeUnit.SECONDS);
            assertEquals(List.of("ignore", "default"), writes);
        } finally {
            completeMute.countDown();
        }
    }

    @Test
    public void reportsACompletedWriteFailureAndKeepsTheRecoveryRecord() {
        StringWriter replies = new StringWriter();
        List<String> writes = new ArrayList<>();
        List<Exception> failures = new ArrayList<>();
        Cleanup.run(new BufferedReader(new StringReader("mute example.game default\napply_mute example.game\n")),
                new PrintWriter(replies), () -> { }, (pkg, mode) -> {
                    writes.add(mode);
                    if ("ignore".equals(mode)) {
                        throw new IOException("rejected");
                    }
                }, (message, error) -> failures.add(error));

        assertEquals(List.of("M7A_CLEANUP_OK mute example.game default", "M7A_CLEANUP_FAILED apply_mute example.game"),
                replies.toString().lines().collect(java.util.stream.Collectors.toList()));
        assertEquals(List.of("ignore", "default"), writes);
        assertEquals(1, failures.size());
    }
}
