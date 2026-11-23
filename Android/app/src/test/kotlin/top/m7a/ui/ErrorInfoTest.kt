package top.m7a.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import top.m7a.R

class ErrorInfoTest {
    @Test
    fun displayFailuresExplainWhichStageFailedAndOpenTheLog() {
        for ((code, title, advice) in listOf(
            Triple("display_failed", R.string.error_display_failed_title, R.string.error_display_failed_advice),
            Triple("frame_timeout", R.string.error_frame_timeout_title, R.string.error_frame_timeout_advice),
            Triple("virtual_display_black", R.string.error_virtual_display_black_title, R.string.error_virtual_display_black_advice),
        )) {
            val info = checkNotNull(errorInfo(code, "HONOR", "HUAWEI"))
            assertEquals(title, info.title)
            assertEquals(advice, info.advice)
            assertEquals(ErrorFix.LOGS, info.fix)
            assertNull(info.additionalAdvice)
        }
    }

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
