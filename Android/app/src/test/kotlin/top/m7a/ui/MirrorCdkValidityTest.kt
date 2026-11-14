package top.m7a.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.time.Instant

class MirrorCdkValidityTest {
    @Test
    fun distinguishesWholeDaysLessThanOneDayAndExpired() {
        val now = Instant.parse("2026-11-15T00:00:00Z")
        assertEquals(2L, remainingCdkDays(now.plusSeconds(172_801), now))
        assertEquals(0L, remainingCdkDays(now.plusSeconds(86_399), now))
        assertNull(remainingCdkDays(now, now))
        assertNull(remainingCdkDays(now.minusSeconds(1), now))
    }
}
