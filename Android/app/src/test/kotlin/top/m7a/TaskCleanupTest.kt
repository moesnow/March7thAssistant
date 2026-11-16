package top.m7a

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TaskCleanupTest {
    private val errors = mutableListOf<Throwable>()
    private val cleanup = TaskCleanup { errors.add(it) }

    @Test
    fun confirmedCleanupKeepsTheTaskResult() {
        assertEquals("success", cleanup.finish("success") {})
        assertTrue(cleanup.confirmed)
        assertTrue(errors.isEmpty())
    }

    @Test
    fun successfulOrStoppedTaskReportsCleanupPendingIfCloseFails() {
        for (result in listOf("success", "stopped")) {
            val failure = SecurityException("permission denied while closing service")
            val reported = mutableListOf<Throwable>()
            val runCleanup = TaskCleanup { reported.add(it) }
            assertEquals("cleanup_pending", runCleanup.finish(result) { throw failure })
            assertFalse(runCleanup.confirmed)
            assertEquals(listOf(failure), reported)
        }
    }

    @Test
    fun bootstrapCleanupFailureRemainsUnconfirmedEvenWithoutALeaseToClose() {
        val failure = DeviceFailure("cleanup_pending", "waiting for service")
        cleanup.unconfirmed(failure)
        assertEquals("service_start", cleanup.finish("service_start") {})
        assertFalse(cleanup.confirmed)
        assertEquals(listOf(failure), errors)
    }
}
