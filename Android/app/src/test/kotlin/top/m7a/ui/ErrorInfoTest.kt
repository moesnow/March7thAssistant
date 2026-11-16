package top.m7a.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import top.m7a.R

class ErrorInfoTest {
    @Test
    fun honorStartupTimeoutAddsSmartResolutionAdviceAndKeepsExistingAdvice() {
        val cases = listOf(" Honor " to "HUAWEI", "unknown" to "HONOR")
        for ((brand, manufacturer) in cases) {
            val info = checkNotNull(errorInfo("game_start_timeout", brand, manufacturer))
            assertEquals(R.string.error_game_start_timeout_title, info.title)
            assertEquals(R.string.error_game_start_timeout_advice, info.advice)
            assertEquals(ErrorFix.LOGS, info.fix)
            assertEquals(R.string.error_honor_smart_resolution_advice, info.additionalAdvice)
        }
    }

    @Test
    fun nonHonorAndUnknownDevicesKeepTheRegularStartupAdvice() {
        val cases = listOf("Redmi" to "Xiaomi", "HUAWEI" to "HUAWEI", null to null)
        for ((brand, manufacturer) in cases) {
            val info = checkNotNull(errorInfo("game_start_timeout", brand, manufacturer))
            assertEquals(R.string.error_game_start_timeout_advice, info.advice)
            assertNull(info.additionalAdvice)
        }
    }

    @Test
    fun knownDifferentErrorsDoNotShowSmartResolutionAdviceOnHonor() {
        val codes = listOf(
            "manual_action_required", "game_exited", "disconnected", "timeout",
            "template_missing", "frame_clock_unavailable", "cleanup_pending", "task_failed",
        )
        for (code in codes) {
            val info = checkNotNull(errorInfo(code, "HONOR", "HONOR"))
            assertNull(code, info.additionalAdvice)
        }
    }
}
