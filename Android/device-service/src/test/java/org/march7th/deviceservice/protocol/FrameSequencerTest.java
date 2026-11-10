package org.march7th.deviceservice.protocol;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import org.junit.Test;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;

public class FrameSequencerTest {
    @Test
    public void sequenceStartsAtOneAndIncreasesByOne() {
        FrameSequencer sequencer = new FrameSequencer();
        assertEquals(0, sequencer.latest());
        assertEquals(1, sequencer.publish());
        assertEquals(2, sequencer.publish());
        assertEquals(2, sequencer.latest());
    }

    @Test
    public void awaitReturnsImmediatelyWhenTheFrameExists() throws Exception {
        FrameSequencer sequencer = new FrameSequencer();
        sequencer.setActive(true);
        sequencer.publish();
        sequencer.publish();
        assertEquals(2, sequencer.await(0, 0));
        assertEquals(2, sequencer.await(1, 0));
        assertEquals(2, sequencer.await(2, 0));
    }

    @Test
    public void minSeqZeroStillNeedsAFirstFrame() throws Exception {
        FrameSequencer sequencer = new FrameSequencer();
        sequencer.setActive(true);
        try {
            sequencer.await(0, 20);
            fail();
        } catch (TimeoutException expected) {
            // 还没有任何帧
        }
    }

    @Test
    public void awaitTimesOutWhenNoNewerFrameArrives() throws Exception {
        FrameSequencer sequencer = new FrameSequencer();
        sequencer.setActive(true);
        long inputSeq = sequencer.publish();
        long begin = System.nanoTime();
        try {
            sequencer.await(inputSeq + 1, 50);
            fail("an old frame satisfied a request for a newer one");
        } catch (TimeoutException expected) {
            assertTrue(System.nanoTime() - begin >= 45_000_000L);
        }
    }

    @Test
    public void awaitWakesUpOnTheFrameAfterTheInput() throws Exception {
        FrameSequencer sequencer = new FrameSequencer();
        sequencer.setActive(true);
        sequencer.publish();
        long inputSeq = sequencer.latest();

        AtomicLong result = new AtomicLong(-1);
        CountDownLatch waiting = new CountDownLatch(1);
        Thread waiter = new Thread(() -> {
            try {
                waiting.countDown();
                result.set(sequencer.await(inputSeq + 1, 5000));
            } catch (Exception e) {
                result.set(-2);
            }
        });
        waiter.start();
        assertTrue(waiting.await(1, TimeUnit.SECONDS));
        Thread.sleep(30);
        assertEquals(-1, result.get());
        sequencer.publish();
        waiter.join(2000);
        assertEquals(inputSeq + 1, result.get());
    }

    @Test
    public void awaitReturnsTheLatestWhenSeveralFramesArrived() throws Exception {
        FrameSequencer sequencer = new FrameSequencer();
        sequencer.setActive(true);
        for (int i = 0; i < 5; i++) {
            sequencer.publish();
        }
        assertEquals(5, sequencer.await(3, 0));
    }

    @Test
    public void awaitFailsWhenCaptureIsNotActive() throws Exception {
        FrameSequencer sequencer = new FrameSequencer();
        try {
            sequencer.await(0, 1000);
            fail();
        } catch (IllegalStateException expected) {
            assertFalse(sequencer.isActive());
        }
    }

    @Test
    public void stoppingCaptureReleasesWaiters() throws Exception {
        FrameSequencer sequencer = new FrameSequencer();
        sequencer.setActive(true);
        AtomicReference<Throwable> thrown = new AtomicReference<>();
        Thread waiter = new Thread(() -> {
            try {
                sequencer.await(1, 5000);
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
        sequencer.publish();
        sequencer.publish();
        sequencer.setActive(false);
        sequencer.setActive(true);
        assertEquals(3, sequencer.publish());
        assertEquals(3, sequencer.await(3, 0));
    }
}
