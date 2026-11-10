package org.march7th.assistant

import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class RunLogTest {
    @get:Rule
    val folder = TemporaryFolder()

    @Test
    fun restoresAllFieldsAndKeepsTheWholeMultilineRecordInTheTail() {
        val file = folder.newFile()
        val heading = logEntry(0, LogLevel.INFO, LogCategory.TASK, "开始触屏每日实训", heading = true)
        val device = logEntry(0, LogLevel.WARNING, LogCategory.DEVICE, "move_back_frame_timeout")
        val error = logEntry(0, LogLevel.ERROR, LogCategory.APP, "失败\r\n\n\t栈帧\n[12:00:00 INFO TASK -] 续行\n")
        val entries = listOf(heading, device, error)
        file.writeText(entries.joinToString("") { it.toLogText() })

        assertEquals(entries, file.readRunLog(200))
        assertEquals(listOf(error), file.readRunLog(1))
    }

    @Test
    fun readsLegacyTextAlongsideNewRecoveryRecords() {
        val file = folder.newFile()
        val legacy = "01:00:00 | WARNING | U2 日志"
        val recovered = logEntry(0, LogLevel.INFO, LogCategory.APP, "已检查上次异常结束的设备端租约")
        file.writeText("$legacy\n" + recovered.toLogText())

        assertEquals(listOf(LogEntry(null, LogLevel.INFO, LogCategory.APP, legacy), recovered), file.readRunLog(200))
    }
}
