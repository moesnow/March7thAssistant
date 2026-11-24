package top.m7a

import android.util.Log
import java.io.File
import java.io.IOException
import java.util.concurrent.TimeUnit

internal class RootAccess(
    private val launcher: File,
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
                if (!reader.isAlive && shell.process.exitValue() == 0 && uid == 0) {
                    permission = PermissionState.READY
                    return
                }
            }
            warn(shell.diagnostic("Root 自检未取得 UID 0"))
        } catch (error: IOException) {
            warn(shell.diagnostic("Root 自检：${error.message}"))
        } finally {
            shell.process.destroy()
        }
    }

    fun open(apkPath: String, token: String, cancelled: () -> Boolean = { false }): DeviceLease {
        val shell = startShell(token)
        return shell.open(token, startDeadline(), cancelled, start = { shell.writeLine(appServerCommand(apkPath)) }) {
            permission = PermissionState.NOT_AUTHORIZED
            DeviceFailure("root_unavailable", "设备端未请求令牌")
        }
    }

    fun recoverAudio(apkPath: String) {
        val shell = startShell()
        shell.recoverAudio { shell.writeLine(appServerCommand(apkPath) + " --recover-audio") }
    }

    private fun appServerCommand(apkPath: String): String {
        fun quote(path: String) = "'" + path.replace("'", "'\\''") + "'"
        return "exec ${quote(launcher.absolutePath)} --root ${quote(apkPath)}"
    }

    private fun startShell(token: String? = null): DeviceProcess = try {
        // 只传 UID。Magisk 新旧版与 KernelSU、SukiSU 对 -c 和其后参数的解析不同。
        DeviceProcess(startProcess(listOf("su", "0")), "Root", token)
    } catch (error: IOException) {
        permission = PermissionState.NOT_INSTALLED
        throw DeviceFailure("root_unavailable", "无法启动 su：${error.message}")
    }

    private companion object {
        const val START_SECONDS = 15L
        const val OUTPUT_DRAIN_MS = 250L
    }
}
