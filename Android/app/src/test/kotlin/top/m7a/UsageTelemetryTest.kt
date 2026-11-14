package top.m7a

import org.junit.Assert.assertEquals
import org.junit.Test

class UsageTelemetryTest {
    @Test
    fun signatureMatchesServerCompactUtf8Payload() {
        val event = linkedMapOf(
            "event" to "task_complete",
            "uuid" to "a".repeat(32),
            "event_id" to "b".repeat(32),
            "timestamp" to "2026-11-15T00:00:00Z",
            "version" to "v2026.11.15-beta",
            "properties" to linkedMapOf(
                "client_platform" to "android", "device_model" to "机型/A",
                "task_id" to "daily", "outcome" to "success", "success" to true, "duration_seconds" to 4.2,
            ),
        )
        val body = signedUsageBatch(listOf(event), "c".repeat(32), "d".repeat(64)).decodeToString()
        val decoded = Json.decode(body) as Map<*, *>
        assertEquals(listOf(event), decoded["events"])
        assertEquals("c".repeat(32), decoded["batch_id"])
        assertEquals("3ce00112cc9200286838be9c0b328c2c85a253e7f31487aaed4c9e345e2d2c56", decoded["signature"])
    }
}
