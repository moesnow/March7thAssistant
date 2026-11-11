package org.march7th.assistant

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Test

class WakeLockRenewalTest {
    @Test
    fun keepsTheTimeoutAheadOfTheClockForHours() {
        val clock = Harness()
        clock.renewal.use {
            it.start()
            repeat(18) { clock.advanceToRenewal() }
            assertEquals(3 * 60 * 60 * 1000L, clock.now)
            assertEquals(19, clock.acquisitions)
        }
    }

    @Test
    fun closingCancelsTheTimerAndIgnoresAnAlreadyDequeuedCallback() {
        val clock = Harness()
        clock.renewal.start()
        val callback = checkNotNull(clock.pending).first
        clock.renewal.close()
        callback.run()
        clock.renewal.close()

        assertEquals(1, clock.releases)
        assertEquals(1, clock.acquisitions)
        assertNull(clock.pending)
    }

    @Test
    fun taskExceptionStillReleasesTheLock() {
        val clock = Harness()
        assertThrows(IllegalStateException::class.java) {
            clock.renewal.use {
                it.start()
                error("任务失败")
            }
        }

        assertEquals(1, clock.releases)
        assertNull(clock.pending)
    }

    @Test
    fun failedRenewalReleasesAndRetries() {
        val clock = Harness()
        clock.renewal.use {
            it.start()
            clock.failAcquire = true
            clock.advanceToRenewal()
            assertEquals(1, clock.errors)
            assertEquals(1, clock.releases)

            clock.failAcquire = false
            clock.advanceToRenewal()
            assertEquals(2, clock.acquisitions)
        }
    }

    private class Harness {
        var now = 0L
        var pending: Pair<Runnable, Long>? = null
        var acquisitions = 0
        var releases = 0
        var errors = 0
        var failAcquire = false
        private var expiresAt = 0L

        val renewal = WakeLockRenewal(
            acquire = { timeout ->
                check(!failAcquire)
                assertEquals(20 * 60 * 1000L, timeout)
                acquisitions++
                expiresAt = now + timeout
            },
            release = { releases++ },
            now = { now },
            postAtTime = { callback, time -> pending = callback to time },
            removeCallbacks = { pending = null },
            onRenewalError = { errors++ },
        )

        fun advanceToRenewal() {
            val (callback, time) = checkNotNull(pending)
            assertEquals(now + 10 * 60 * 1000L, time)
            check(time < expiresAt || errors > 0)
            pending = null
            now = time
            callback.run()
        }
    }
}
