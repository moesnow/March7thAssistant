package top.m7a

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.ByteArrayOutputStream

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

    @Test
    fun showsTheLastExpectedErrorInAnExistingStackWithoutChangingItsExport() {
        val file = folder.newFile()
        val reason = "委托失败后无法回到可操作界面：无法识别当前游戏界面"
        val trace = """
            Traceback (most recent call last):
              File "/data/tasks.py", line 1, in run
            RuntimeError: 无法识别当前游戏界面

            The above exception was the direct cause of the following exception:

            Traceback (most recent call last):
              File "/data/task_steps.py", line 49, in run_steps
            tasks.base.task_steps.GameRecoveryError: $reason
        """.trimIndent()
        val entry = logEntry(0, LogLevel.ERROR, LogCategory.TASK, trace)
        file.writeText(entry.toLogText())

        assertEquals(entry.copy(message = reason), file.readRunLog(200).single().forDisplay("可导出日志"))
        assertEquals(entry.toLogText(), file.readText())
    }

    @Test
    fun displaysStartupTimeoutReasonAndSummarizesUnexpectedStacks() {
        val entry = logEntry(0, LogLevel.ERROR, LogCategory.TASK, """
            Traceback (most recent call last):
              File "/data/adb_ready.py", line 61, in wait_for_game
            module.game.adb_transport.AdbError: 等待游戏就绪超时
        """.trimIndent())
        assertEquals("等待游戏就绪超时", entry.forDisplay("可导出日志").message)
        val unknown = entry.copy(message = entry.message.replace("AdbError:", "ValueError:"))
        assertEquals("可导出日志", unknown.forDisplay("可导出日志").message)
        val ordinary = entry.copy(message = "清体力未完成\n未确认补充数量弹窗")
        assertEquals(ordinary, ordinary.forDisplay("可导出日志"))
    }

    @Test
    fun exportsRecentDiagnosticsInOrderWithoutReplacingTheRunLog() {
        val log = folder.newFile()
        val error = logEntry(0, LogLevel.ERROR, LogCategory.TASK, "原始错误")
        log.writeText(error.toLogText())
        val diagnostics = RunDiagnostics(folder.root, chunkBytes = 40)
        for (text in listOf("old template", "template >= 0.9", "OCR result")) {
            diagnostics.append(logEntry(0, LogLevel.DEBUG, LogCategory.TASK, text))
        }
        val export = ByteArrayOutputStream()
        log.inputStream().use { it.copyTo(export) }
        diagnostics.exportTo(export)
        val full = export.toString(Charsets.UTF_8.name())
        assertTrue(full.startsWith(error.toLogText()))
        assertFalse(full.contains("old template"))
        assertTrue(full.indexOf("template >= 0.9") in 0 until full.indexOf("OCR result"))
        assertEquals(listOf(error), log.readRunLog(1))

        diagnostics.clear()
        val empty = ByteArrayOutputStream()
        diagnostics.exportTo(empty)
        assertEquals(0, empty.size())
    }
}
