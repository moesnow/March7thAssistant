package org.march7th.deviceservice.protocol;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertThrows;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import org.junit.Test;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;

public class FrameSequencerTest {
    private static long publish(FrameSequencer sequencer) {
        return sequencer.publish(0, 0, 0).seq;
    }

    private static long await(FrameSequencer sequencer, long generation, long minSeq, long timeoutMs)
            throws InterruptedException, TimeoutException {
        return sequencer.await(generation, minSeq, null, timeoutMs).seq;
    }
    @Test
    public void sequenceStartsAtOneAndIncreasesByOne() {
        FrameSequencer sequencer = new FrameSequencer();
        sequencer.setActive(true);
        assertEquals(0, sequencer.latest());
        assertEquals(1, publish(sequencer));
        assertEquals(2, publish(sequencer));
        assertEquals(2, sequencer.latest());
    }

    @Test
    public void awaitReturnsImmediatelyWhenTheFrameExists() throws Exception {
        FrameSequencer sequencer = new FrameSequencer();
        long generation = sequencer.setActive(true);
        publish(sequencer);
        publish(sequencer);
        assertEquals(2, await(sequencer, generation, 0, 0));
        assertEquals(2, await(sequencer, generation, 1, 0));
        assertEquals(2, await(sequencer, generation, 2, 0));
    }

    @Test
    public void minSeqZeroStillNeedsAFirstFrame() throws Exception {
        FrameSequencer sequencer = new FrameSequencer();
        long generation = sequencer.setActive(true);
        try {
            await(sequencer, generation, 0, 20);
            fail();
        } catch (TimeoutException expected) {
            // 还没有任何帧
        }
    }

    @Test
    public void awaitTimesOutWhenNoNewerFrameArrives() throws Exception {
        FrameSequencer sequencer = new FrameSequencer();
        long generation = sequencer.setActive(true);
        long inputSeq = publish(sequencer);
        long begin = System.nanoTime();
        try {
            await(sequencer, generation, inputSeq + 1, 50);
            fail("an old frame satisfied a request for a newer one");
        } catch (TimeoutException expected) {
            assertTrue(System.nanoTime() - begin >= 45_000_000L);
        }
    }

    @Test
    public void awaitWakesUpOnTheFrameAfterTheInput() throws Exception {
        FrameSequencer sequencer = new FrameSequencer();
        long generation = sequencer.setActive(true);
        publish(sequencer);
        long inputSeq = sequencer.latest();

        AtomicLong result = new AtomicLong(-1);
        CountDownLatch waiting = new CountDownLatch(1);
        Thread waiter = new Thread(() -> {
            try {
                waiting.countDown();
                result.set(await(sequencer, generation, inputSeq + 1, 5000));
            } catch (Exception e) {
                result.set(-2);
            }
        });
        waiter.start();
        assertTrue(waiting.await(1, TimeUnit.SECONDS));
        Thread.sleep(30);
        assertEquals(-1, result.get());
        publish(sequencer);
        waiter.join(2000);
        assertEquals(inputSeq + 1, result.get());
    }

    @Test
    public void awaitReturnsTheLatestWhenSeveralFramesArrived() throws Exception {
        FrameSequencer sequencer = new FrameSequencer();
        long generation = sequencer.setActive(true);
        for (int i = 0; i < 5; i++) {
            publish(sequencer);
        }
        assertEquals(5, await(sequencer, generation, 3, 0));
    }

    @Test
    public void awaitFailsWhenCaptureIsNotActive() throws Exception {
        FrameSequencer sequencer = new FrameSequencer();
        try {
            await(sequencer, 0, 0, 1000);
            fail();
        } catch (IllegalStateException expected) {
            assertFalse(sequencer.isActive());
        }
    }

    @Test
    public void stoppingCaptureReleasesWaiters() throws Exception {
        FrameSequencer sequencer = new FrameSequencer();
        long generation = sequencer.setActive(true);
        AtomicReference<Throwable> thrown = new AtomicReference<>();
        Thread waiter = new Thread(() -> {
            try {
                await(sequencer, generation, 1, 5000);
            } catch (Throwable e) {
                thrown.set(e);
            }
        });
        waiter.start();
        Thread.sleep(30);
        sequencer.setActive(false);
        waiter.join(2000);
        assertFalse(waiter.isAlive());
        assertTrue(thrown.get() instanceof IllegalStateException);
    }

    @Test
    public void sequenceKeepsGrowingAcrossCaptureRestarts() throws Exception {
        FrameSequencer sequencer = new FrameSequencer();
        sequencer.setActive(true);
        publish(sequencer);
        publish(sequencer);
        sequencer.setActive(false);
        long generation = sequencer.setActive(true);
        assertEquals(3, publish(sequencer));
        assertEquals(3, await(sequencer, generation, 3, 0));
    }

    @Test
    public void oldBufferPublishedAfterInputDoesNotSatisfyTimestampBoundary() throws Exception {
        FrameSequencer sequencer = new FrameSequencer();
        long generation = sequencer.setActive(true);
        long inputNs = 10_000_000L;
        long minSeq = sequencer.publish(8_000_000L, 8_100_000L, 8).seq + 1;

        sequencer.publish(9_000_000L, 11_000_000L, 11); // 先生产，输入完成后才到达
        assertEquals(minSeq, await(sequencer, generation, minSeq, 0));
        assertThrows(TimeoutException.class, () -> sequencer.await(generation, minSeq, inputNs, 0));
        sequencer.publish(inputNs, 11_100_000L, 11); // 严格晚于，时间相等也不满足
        assertThrows(TimeoutException.class, () -> sequencer.await(generation, minSeq, inputNs, 0));

        FrameSequencer.Frame newFrame = sequencer.publish(11_000_000L, 12_000_000L, 12);
        assertEquals(newFrame, sequencer.await(generation, minSeq, inputNs, 0));
    }

    @Test
    public void incomparableTimestampCanOnlySatisfyASequenceRequest() throws Exception {
        FrameSequencer sequencer = new FrameSequencer();
        long generation = sequencer.setActive(true);
        long acquiredNs = 3_000_000_000L;
        for (long invalid : new long[] {0, acquiredNs + 1, acquiredNs - 1_000_000_001L}) {
            FrameSequencer.Frame frame = sequencer.publish(invalid, acquiredNs, 3000);
            assertFalse(frame.timestampComparable);
            assertThrows(TimeoutException.class, () -> sequencer.await(generation, 0, 0L, 0));
            assertEquals(frame, sequencer.await(generation, 0, null, 0));
        }
    }

    @Test
    public void newScreenWaitsForItsOwnFirstFrameEvenWithMinSeqZero() throws Exception {
        FrameSequencer sequencer = new FrameSequencer();
        long old = sequencer.setActive(true);
        publish(sequencer);
        publish(sequencer);
        sequencer.setActive(false);
        long current = sequencer.setActive(true);
        assertThrows(TimeoutException.class, () -> await(sequencer, current, 0, 0));
        assertEquals(2, sequencer.latest());
        publish(sequencer);
        assertEquals(3, await(sequencer, current, 0, 0));
        assertThrows(IllegalStateException.class, () -> await(sequencer, old, 0, 0));
    }
}
