package top.m7a

import java.io.File
import java.io.OutputStream
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

enum class LogLevel { DEBUG, INFO, WARNING, ERROR }
enum class LogCategory { TASK, DEVICE, APP }

data class LogEntry(
    val time: String?,
    val level: LogLevel,
    val category: LogCategory,
    val message: String,
    val heading: Boolean = false,
)

private val clockFormat = DateTimeFormatter.ofPattern("HH:mm:ss", Locale.ROOT)
private const val tracebackHeader = "Traceback (most recent call last):"
private val readableErrors = setOf("AdbError", "GameRecoveryError", "PowerError", "TouchProfileInputError")

internal fun LogEntry.forDisplay(fallback: String): LogEntry {
    if (level != LogLevel.ERROR || message.substringBefore('\n') != tracebackHeader) return this
    val lastHeader = message.lastIndexOf("\n$tracebackHeader\n")
    val exception = message.substring(lastHeader + 1).lineSequence().drop(1)
        .firstOrNull { it.isNotBlank() && !it.first().isWhitespace() }
    val name = exception?.substringBefore(':')?.substringAfterLast('.')
    val reason = exception?.substringAfter(':', "")?.trim()?.takeIf { it.isNotEmpty() }
    return copy(message = if (name != null && name in readableErrors && reason != null) reason.take(240) else fallback)
}

internal fun logEntry(
    timeMs: Long, level: LogLevel, category: LogCategory, message: String, heading: Boolean = false,
) = LogEntry(
    Instant.ofEpochMilli(timeMs).atZone(ZoneId.systemDefault()).format(clockFormat),
    level, category, message.replace("\r\n", "\n").replace('\r', '\n'), heading,
)

// 首行记录字段，后续行缩进一个制表符。导出的就是这份可直接阅读的日志。
internal fun LogEntry.toLogText(): String {
    val kind = if (heading) "H" else "-"
    return "[$time ${level.name} ${category.name} $kind] " + message.replace("\n", "\n\t") + "\n"
}

private fun readHeader(line: String): LogEntry? {
    if (!line.startsWith("[")) return null
    val end = line.indexOf("] ")
    if (end < 0) return null
    val fields = line.substring(1, end).split(' ')
    if (fields.size != 4 || fields[0].length != 8 || fields[3] !in setOf("H", "-")) return null
    val level = LogLevel.entries.firstOrNull { it.name == fields[1] } ?: return null
    val category = LogCategory.entries.firstOrNull { it.name == fields[2] } ?: return null
    return LogEntry(fields[0], level, category, line.substring(end + 2), heading = fields[3] == "H")
}

internal fun File.readRunLog(limit: Int): List<LogEntry> = useLines { lines ->
    val tail = ArrayDeque<LogEntry>()
    var entry: LogEntry? = null
    val message = StringBuilder()
    fun add(item: LogEntry) {
        if (tail.size == limit) tail.removeFirst()
        tail.addLast(item)
    }
    fun flush() {
        entry?.let { add(it.copy(message = message.toString())) }
        entry = null
        message.clear()
    }
    for (line in lines) {
        if (entry != null && line.startsWith('\t')) {
            message.append('\n').append(line, 1, line.length)
        } else {
            flush()
            val header = readHeader(line)
            if (header == null) {
                // U2 的日志缺少类别和分节字段，保留原文供查看和导出。
                add(LogEntry(null, LogLevel.INFO, LogCategory.APP, line))
            } else {
                entry = header
                message.append(header.message)
            }
        }
    }
    flush()
    tail.toList()
}

/** 保留近期调试记录，和本轮原始运行日志一起导出。调用方与运行日志共用一把锁。 */
internal class RunDiagnostics(directory: File, private val chunkBytes: Long = 512L * 1024) {
    private val current = File(directory, "last-run-diagnostics.log")
    private val previous = File(directory, "last-run-diagnostics.previous.log")

    fun clear() {
        Files.deleteIfExists(previous.toPath())
        Files.deleteIfExists(current.toPath())
    }

    fun append(entry: LogEntry) {
        val bytes = entry.toLogText().toByteArray(Charsets.UTF_8)
        if (current.length() > 0 && current.length() + bytes.size > chunkBytes) {
            Files.move(current.toPath(), previous.toPath(), StandardCopyOption.REPLACE_EXISTING)
        }
        current.appendBytes(bytes)
    }

    fun exportTo(output: OutputStream) {
        val files = listOf(previous, current).filter { it.length() > 0 }
        if (files.isEmpty()) return
        output.write("\n近期诊断（模板匹配、OCR 等）\n".toByteArray(Charsets.UTF_8))
        for (file in files) {
            file.inputStream().use { it.copyTo(output) }
        }
    }
}
