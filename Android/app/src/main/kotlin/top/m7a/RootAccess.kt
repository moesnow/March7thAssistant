package top.m7a

import android.os.Process.SHELL_UID
import android.util.Log
import org.march7th.deviceservice.AppServer
import java.io.IOException
import java.util.concurrent.CompletableFuture
import java.util.concurrent.TimeUnit
import java.util.concurrent.TimeoutException
import kotlin.concurrent.thread

internal class RootAccess(
    private val startProcess: (List<String>) -> java.lang.Process = {
        ProcessBuilder(it).redirectErrorStream(true).start()
    },
    private val warn: (String) -> Unit = { Log.w("M7ARoot", it) },
) {
    @Volatile
    var permission = PermissionState.NOT_CHECKED
        private set

    fun probe() {
        permission = PermissionState.NOT_AUTHORIZED
        val shell = try {
            startShell()
        } catch (error: DeviceFailure) {
            warn(error.message.orEmpty())
            return
        }
        var uid: Int? = null
        val reader = shell.readOutput { line ->
            line.toIntOrNull()?.let { uid = it }
            false
        }
        try {
            shell.writeLine("exec /system/bin/id -u")
            shell.process.outputStream.close()
            if (shell.process.waitFor(START_SECONDS, TimeUnit.SECONDS)) {
                reader.join(OUTPUT_DRAIN_MS)
                if (!reader.isAlive && shell.process.exitValue() == 0 && uid == SHELL_UID) {
                    permission = PermissionState.READY
                    return
                }
            }
            warn(shell.diagnostic("Root 自检未取得 UID $SHELL_UID"))
        } catch (error: IOException) {
            warn(shell.diagnostic("Root 自检：${error.message}"))
        } finally {
            shell.process.destroy()
        }
    }

    fun open(apkPath: String, token: String): DeviceLease {
        val shell = startShell(token)
        val tokenRequested = CompletableFuture<Boolean>()
        val portAnnounced = CompletableFuture<Int>()
        val reader = shell.readOutput(onClosed = {
            tokenRequested.complete(false)
            portAnnounced.complete(0)
        }) { line ->
            when {
                line == AppServer.ROOT_STDIN_READY -> {
                    tokenRequested.complete(true)
                    true
                }
                !tokenRequested.getNow(false) -> false
                line == "M7A_APP_BUSY" -> {
                    portAnnounced.complete(BUSY_PORT)
                    true
                }
                line.startsWith("M7A_APP_PORT ") -> {
                    val port = line.substringAfter(' ').toIntOrNull()
                    portAnnounced.complete(port?.takeIf { it in 1..65535 } ?: 0)
                    true
                }
                else -> false
            }
        }
        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(START_SECONDS)
        try {
            shell.writeLine(appServerCommand(apkPath))
            if (!tokenRequested.get(deadline - System.nanoTime(), TimeUnit.NANOSECONDS)) {
                permission = PermissionState.NOT_AUTHORIZED
                throw DeviceFailure("root_unavailable", "设备端未请求令牌")
            }
            // 等 AppServer 通过 UID 检查并接管 stdin，避免 shell 预读令牌。
            shell.writeLine(token)
            val port = portAnnounced.get(deadline - System.nanoTime(), TimeUnit.NANOSECONDS)
            if (port == BUSY_PORT) throw DeviceFailure(AppServer.BUSY)
            if (port == 0) throw DeviceFailure("service_start", "设备端未返回有效监听端口")
            return object : DeviceLease {
                override val port = port
                override fun close() = shell.close()
            }
        } catch (error: Exception) {
            val cleanup = runCatching { shell.close() }.exceptionOrNull()
            reader.join(OUTPUT_DRAIN_MS)
            val code = (error as? DeviceFailure)?.code ?: "service_start"
            val reason = if (error is TimeoutException) {
                if (tokenRequested.getNow(false)) "等待监听端口超时" else "等待设备端请求令牌超时"
            } else {
                error.message ?: error.javaClass.simpleName
            }
            val failure = DeviceFailure(code, shell.diagnostic(reason))
            if (cleanup != null) failure.addSuppressed(cleanup)
            throw failure
        }
    }

    fun recoverAudio(apkPath: String) {
        val shell = startShell()
        val reader = shell.readOutput { false }
        try {
            shell.writeLine(appServerCommand(apkPath) + " --recover-audio")
            shell.close()
            reader.join(OUTPUT_DRAIN_MS)
            if (shell.process.exitValue() != 0) {
                throw DeviceFailure("cleanup_pending", shell.diagnostic("游戏音频恢复失败"))
            }
        } finally {
            shell.process.destroy()
        }
    }

    private fun appServerCommand(apkPath: String): String {
        val path = "'" + apkPath.replace("'", "'\\''") + "'"
        return "CLASSPATH=$path exec /system/bin/app_process /system/bin " +
            "--nice-name=m7a-apk-root org.march7th.deviceservice.AppServer $path"
    }

    private fun startShell(token: String? = null): RootShell = try {
        // 只传 UID。Magisk 新旧版与 KernelSU、SukiSU 对 -c 和其后参数的解析不同。
        RootShell(startProcess(listOf("su", SHELL_UID.toString())), token)
    } catch (error: IOException) {
        permission = PermissionState.NOT_INSTALLED
        throw DeviceFailure("root_unavailable", "无法启动 su：${error.message}")
    }

    private companion object {
        const val START_SECONDS = 15L
        const val OUTPUT_DRAIN_MS = 250L
        const val BUSY_PORT = -1
    }
}

private class RootShell(val process: java.lang.Process, private val token: String?) {
    private val output = ArrayDeque<String>()

    fun writeLine(line: String) {
        process.outputStream.write((line + "\n").toByteArray(Charsets.UTF_8))
        process.outputStream.flush()
    }

    fun readOutput(onClosed: () -> Unit = {}, onLine: (String) -> Boolean) =
        thread(name = "m7a-root-output", isDaemon = true) {
            try {
                process.inputStream.bufferedReader().useLines { lines ->
                    for (line in lines) {
                        if (!onLine(line) && line.isNotBlank()) {
                            synchronized(output) {
                                if (output.size == 4) output.removeFirst()
                                output.addLast(redact(line).take(240))
                            }
                        }
                    }
                }
            } catch (_: IOException) {
                // 关闭进程时也会关闭输出管道。
            } finally {
                onClosed()
            }
        }

    fun diagnostic(reason: String): String {
        val exit = if (process.isAlive) "未退出" else process.exitValue().toString()
        val recent = synchronized(output) { output.joinToString(" | ") }
        return redact("$reason，exit=$exit" + if (recent.isEmpty()) "" else "，输出：$recent")
    }

    private fun redact(text: String): String = if (token.isNullOrEmpty()) text else text.replace(token, "[已脱敏]")

    fun close() {
        runCatching { process.outputStream.close() }
        if (!process.waitFor(9, TimeUnit.SECONDS)) {
            process.destroy()
            throw DeviceFailure("cleanup_pending", "等待 Root 设备端服务退出超时")
        }
    }
}
