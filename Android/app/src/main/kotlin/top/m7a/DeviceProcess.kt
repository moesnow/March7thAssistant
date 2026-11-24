package top.m7a

import org.march7th.deviceservice.AppServer
import java.io.Closeable
import java.io.IOException
import java.io.InputStream
import java.util.concurrent.CompletableFuture
import java.util.concurrent.ExecutionException
import java.util.concurrent.TimeUnit
import java.util.concurrent.TimeoutException
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.concurrent.thread

internal fun startDeadline(timeoutMs: Long = 15_000) = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(timeoutMs)

internal fun <T> CompletableFuture<T>.awaitStage(deadline: Long, stage: String, cancelled: () -> Boolean): T {
    while (true) {
        if (cancelled()) throw DeviceFailure("stopped", stage)
        val remaining = deadline - System.nanoTime()
        if (remaining <= 0) throw DeviceFailure("service_start", "${stage}超时")
        try {
            return get(minOf(remaining, TimeUnit.MILLISECONDS.toNanos(100)), TimeUnit.NANOSECONDS)
        } catch (_: TimeoutException) {
            // 共用本轮截止时间，在等待期间也响应停止。
        } catch (error: ExecutionException) {
            throw error.cause ?: error
        }
    }
}

/** AppServer 的一次启动独占这组管道。只有 stdout 可以宣告端口。 */
internal class DeviceProcess(
    val process: Process,
    private val method: String,
    private val token: String? = null,
    private val separateStderr: Boolean = false,
    private val onClosed: (exited: Boolean) -> Unit = {},
) : Closeable {
    private val output = ArrayDeque<String>()
    private var stdoutReader: Thread? = null
    private var stderrReader: Thread? = null

    fun writeLine(line: String) {
        process.outputStream.write((line + "\n").toByteArray(Charsets.UTF_8))
        process.outputStream.flush()
    }

    private fun remember(line: String) {
        if (line.isBlank()) return
        synchronized(output) {
            if (output.size == 4) output.removeFirst()
            output.addLast(redact(line).take(240))
        }
    }

    private fun drain(stream: InputStream, onClosed: () -> Unit = {}, onLine: (String) -> Unit) =
        thread(name = "m7a-$method-output", isDaemon = true) {
            try {
                stream.bufferedReader().use { reader ->
                    val line = StringBuilder()
                    while (true) {
                        val ch = reader.read()
                        if (ch == -1 || ch == '\n'.code) {
                            // 超长行整行丢弃，避免缓存无换行的输出或截出半个令牌。
                            if (line.length <= 512) onLine(line.toString().trimEnd('\r'))
                            if (ch == -1) break
                            line.setLength(0)
                        } else if (line.length <= 512) line.append(ch.toChar())
                    }
                }
            } catch (_: IOException) {
                // 进程退出或 Binder 断开也会关闭输出。
            } finally {
                onClosed()
            }
        }

    fun readOutput(onClosed: () -> Unit = {}, onLine: (String) -> Boolean): Thread {
        if (separateStderr) stderrReader = drain(process.errorStream, onLine = ::remember)
        return drain(process.inputStream, onClosed) { if (!onLine(it)) remember(it) }.also { stdoutReader = it }
    }

    fun open(
        token: String,
        deadline: Long,
        cancelled: () -> Boolean,
        start: () -> Unit = {},
        trace: (String) -> Unit = {},
        missingReady: () -> DeviceFailure = { DeviceFailure("service_start", "设备端未请求令牌") },
    ): DeviceLease {
        val ready = CompletableFuture<Boolean>()
        val port = CompletableFuture<Int>()
        val sending = AtomicBoolean()
        try {
            readOutput(onClosed = {
                ready.complete(false)
                port.complete(0)
            }) { line ->
                when {
                    line == AppServer.ROOT_STDIN_READY -> ready.complete(true)
                    line == "M7A_APP_FILES_FAILED" -> ready.completeExceptionally(
                        DeviceFailure("service_start", "设备服务文件权限处理失败")
                    )
                    !sending.get() -> false
                    line == "M7A_APP_BUSY" -> port.complete(-1)
                    line.startsWith("M7A_APP_PORT ") -> port.complete(line.substringAfter(' ').toIntOrNull()?.takeIf { it in 1..65535 } ?: 0)
                    else -> false
                }
            }
            start()
            if (!ready.awaitStage(deadline, "等待设备端请求令牌", cancelled)) throw missingReady()
            if (cancelled()) throw DeviceFailure("stopped")
            if (System.nanoTime() >= deadline) throw DeviceFailure("service_start", "发送令牌前已超时")
            sending.set(true)
            writeLine(token)
            trace("$method 设备端已接管 stdin，令牌已发送")
            val announced = port.awaitStage(deadline, "等待设备端监听端口", cancelled)
            if (announced == -1) throw DeviceFailure(AppServer.BUSY)
            if (announced !in 1..65535) throw DeviceFailure("service_start", "设备端未返回有效监听端口")
            trace("$method 设备端已返回监听端口")
            return object : DeviceLease {
                override val port = announced
                override fun close() = this@DeviceProcess.close()
            }
        } catch (error: Exception) {
            val cleanup = runCatching { close() }.exceptionOrNull()
            val failure = DeviceFailure((error as? DeviceFailure)?.code ?: "service_start", diagnostic(error.message.orEmpty()))
            if (cleanup != null) failure.addSuppressed(cleanup)
            throw failure
        }
    }

    fun recoverAudio(start: () -> Unit = {}) {
        try {
            readOutput { false }
            start()
        } catch (error: Exception) {
            runCatching { close() }.onFailure(error::addSuppressed)
            throw error
        }
        close()
        if (process.exitValue() != 0) throw DeviceFailure("cleanup_pending", diagnostic("游戏音频恢复失败"))
    }

    fun diagnostic(reason: String): String {
        val exit = runCatching { if (process.isAlive) "未退出" else process.exitValue().toString() }.getOrDefault("未知")
        val recent = synchronized(output) { output.joinToString(" | ") }
        return redact("$method $reason，exit=$exit" + if (recent.isEmpty()) "" else "，输出：$recent")
    }

    private fun redact(text: String) = if (token.isNullOrEmpty()) text else text.replace(token, "[已脱敏]")

    override fun close() {
        runCatching { process.outputStream.close() }
        var exited = false
        try {
            exited = process.waitFor(9, TimeUnit.SECONDS)
            if (!exited) {
                val failure = DeviceFailure("cleanup_pending", "等待 $method 设备端服务退出超时")
                runCatching { process.destroy() }.onFailure(failure::addSuppressed)
                throw failure
            }
            stdoutReader?.join(250)
            stderrReader?.join(250)
        } finally {
            // 读线程在 EOF 时各自关闭 PFD。跨线程关闭正在阻塞读取的流可能拖住超时清理。
            // 迟到的进程未启动读线程，需要在这里归还 PFD。
            if (separateStderr) {
                if (stdoutReader == null) runCatching { process.inputStream.close() }
                if (stderrReader == null) runCatching { process.errorStream.close() }
            }
            onClosed(exited)
        }
    }
}
