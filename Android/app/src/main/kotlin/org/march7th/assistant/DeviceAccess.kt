package org.march7th.assistant

import android.content.ComponentName
import android.content.Context
import android.content.ServiceConnection
import android.content.pm.PackageManager
import android.os.Binder
import android.os.IBinder
import android.os.Process
import android.util.Base64
import org.march7th.deviceservice.AppServer
import rikka.shizuku.Shizuku
import java.io.Closeable
import java.io.IOException
import java.security.SecureRandom
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

enum class Privilege { SHIZUKU, ROOT }
enum class PermissionState { NOT_INSTALLED, NOT_RUNNING, NOT_AUTHORIZED, READY }

internal class DeviceFailure(val code: String) : IOException(code)

internal fun newToken(): String = Base64.encodeToString(
    ByteArray(32).also(SecureRandom()::nextBytes),
    Base64.NO_WRAP or Base64.NO_PADDING or Base64.URL_SAFE
)

internal fun Context.hasPackage(packageName: String): Boolean = try {
    packageManager.getPackageInfo(packageName, 0)
    true
} catch (_: PackageManager.NameNotFoundException) {
    false
}

internal interface DeviceLease : Closeable {
    val port: Int
}

internal class DeviceAccess(private val context: Context) {
    @Volatile
    private var rootPermission = PermissionState.NOT_AUTHORIZED

    private val userService = Shizuku.UserServiceArgs(ComponentName(context, GameUserService::class.java))
        .daemon(false)
        .tag("m7a-device")
        .processNameSuffix("device")
        .version(BuildConfig.VERSION_CODE)

    fun state(privilege: Privilege): PermissionState {
        if (privilege == Privilege.ROOT) return rootPermission
        if (!context.hasPackage(SHIZUKU_PACKAGE)) return PermissionState.NOT_INSTALLED
        if (!Shizuku.pingBinder()) return PermissionState.NOT_RUNNING
        return runCatching {
            if (Shizuku.getVersion() >= 13 && Shizuku.checkSelfPermission() == PackageManager.PERMISSION_GRANTED) {
                PermissionState.READY
            } else {
                PermissionState.NOT_AUTHORIZED
            }
        }.getOrDefault(PermissionState.NOT_RUNNING)
    }

    fun requestShizukuPermission() {
        if (state(Privilege.SHIZUKU) == PermissionState.NOT_AUTHORIZED && Shizuku.getVersion() >= 13) {
            Shizuku.requestPermission(PERMISSION_REQUEST)
        }
    }

    fun probeRoot() {
        val process = try {
            ProcessBuilder("su", "-c", "id -u").redirectErrorStream(true).start()
        } catch (_: IOException) {
            rootPermission = PermissionState.NOT_INSTALLED
            return
        }
        try {
            val granted = process.waitFor(15, TimeUnit.SECONDS) && process.exitValue() == 0 &&
                process.inputStream.bufferedReader().readText().trim() == "0"
            rootPermission = if (granted) PermissionState.READY else PermissionState.NOT_AUTHORIZED
        } finally {
            process.destroy()
        }
    }

    fun open(privilege: Privilege, token: String): DeviceLease = when (privilege) {
        Privilege.SHIZUKU -> openUserService(token)
        Privilege.ROOT -> openRoot(token)
    }

    /** 只尝试回收本应用同一 tag 的残留 UserService。 */
    fun recoverShizuku() {
        if (state(Privilege.SHIZUKU) != PermissionState.READY) return
        val binding = UserBinding()
        if (Shizuku.peekUserService(userService, binding) >= 0) {
            try {
                if (!binding.connected.await(3, TimeUnit.SECONDS)) throw DeviceFailure("cleanup_pending")
            } finally {
                binding.close()
            }
        }
    }

    private fun openUserService(token: String): DeviceLease {
        val binding = UserBinding()
        try {
            Shizuku.bindUserService(userService, binding)
            if (!binding.connected.await(12, TimeUnit.SECONDS)) throw DeviceFailure("service_start")
            val remote = binding.remote ?: throw DeviceFailure("service_start")
            binding.port = IDeviceBootstrap.Stub.asInterface(remote).start(token, binding.owner)
            if (binding.port == GameUserService.BUSY) throw DeviceFailure(AppServer.BUSY)
            if (binding.port !in 1..65535) throw DeviceFailure("service_start")
            return binding
        } catch (error: Exception) {
            binding.close()
            throw if (error is DeviceFailure) error else DeviceFailure("service_start")
        }
    }

    private inner class UserBinding : ServiceConnection, DeviceLease {
        val connected = CountDownLatch(1)
        val owner = Binder()
        @Volatile var remote: IBinder? = null
        override var port = 0

        override fun onServiceConnected(name: ComponentName, service: IBinder) {
            remote = service
            connected.countDown()
        }

        override fun onServiceDisconnected(name: ComponentName) {
            remote = null
            connected.countDown()
        }

        override fun close() {
            val binder = remote
            try {
                if (binder != null && binder.isBinderAlive) {
                    val stopped = CountDownLatch(1)
                    val death = IBinder.DeathRecipient { stopped.countDown() }
                    try {
                        binder.linkToDeath(death, 0)
                        IDeviceBootstrap.Stub.asInterface(binder).destroy()
                        if (!stopped.await(9, TimeUnit.SECONDS)) throw DeviceFailure("cleanup_pending")
                    } catch (_: android.os.DeadObjectException) {
                        // 服务已经自行完成关闭。
                    } finally {
                        binder.unlinkToDeath(death, 0)
                    }
                }
            } finally {
                runCatching { Shizuku.unbindUserService(userService, this, true) }
            }
        }
    }

    private fun openRoot(token: String): DeviceLease {
        val path = "'" + context.applicationInfo.sourceDir.replace("'", "'\\''") + "'"
        val command = "CLASSPATH=$path exec /system/bin/app_process /system/bin " +
            "--nice-name=m7a-apk-root org.march7th.deviceservice.AppServer $path"
        val process = try {
            ProcessBuilder("su", "-c", command, Process.SHELL_UID.toString()).redirectErrorStream(true).start()
        } catch (_: IOException) {
            rootPermission = PermissionState.NOT_INSTALLED
            throw DeviceFailure("root_unavailable")
        }
        val ready = CountDownLatch(1)
        var port = 0
        var busy = false
        Thread({
            try {
                process.inputStream.bufferedReader().useLines { lines ->
                    for (line in lines) {
                        if (line.startsWith("M7A_APP_PORT ")) {
                            port = line.substringAfter(' ').toIntOrNull() ?: 0
                            ready.countDown()
                        } else if (line == "M7A_APP_BUSY") {
                            busy = true
                            ready.countDown()
                        }
                    }
                }
            } catch (_: IOException) {
                // 进程已关闭管道。
            } finally {
                ready.countDown()
            }
        }, "m7a-root-output").apply { isDaemon = true }.start()
        try {
            process.outputStream.write((token + "\n").toByteArray(Charsets.US_ASCII))
            process.outputStream.flush()
            if (!ready.await(15, TimeUnit.SECONDS)) throw DeviceFailure("service_start")
            if (busy) throw DeviceFailure(AppServer.BUSY)
            if (port !in 1..65535) {
                rootPermission = PermissionState.NOT_AUTHORIZED
                throw DeviceFailure("root_unavailable")
            }
            return object : DeviceLease {
                override val port = port
                override fun close() = closeRoot(process)
            }
        } catch (error: Exception) {
            closeRoot(process)
            throw error
        }
    }

    private fun closeRoot(process: java.lang.Process) {
        runCatching { process.outputStream.close() }
        if (!process.waitFor(9, TimeUnit.SECONDS)) {
            process.destroy()
            throw DeviceFailure("cleanup_pending")
        }
    }

    companion object {
        const val SHIZUKU_PACKAGE = "moe.shizuku.privileged.api"
        const val GAME_PACKAGE = "com.miHoYo.hkrpg"
        const val PERMISSION_REQUEST = 1802
    }
}
