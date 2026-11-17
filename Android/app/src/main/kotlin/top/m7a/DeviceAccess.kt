package top.m7a

import android.content.ComponentName
import android.content.Context
import android.content.ServiceConnection
import android.content.pm.PackageManager
import android.os.Binder
import android.os.DeadObjectException
import android.os.IBinder
import android.util.Base64
import android.util.Log
import org.march7th.deviceservice.AppServer
import rikka.shizuku.Shizuku
import java.io.Closeable
import java.io.IOException
import java.security.SecureRandom
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

enum class Privilege { SHIZUKU, ROOT }
enum class PermissionState { NOT_CHECKED, CHECKING, NOT_INSTALLED, NOT_RUNNING, NOT_AUTHORIZED, READY }

internal class DeviceFailure(val code: String, detail: String? = null) :
    IOException(if (detail == null) code else "$code ($detail)")

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

internal fun closeUserService(binder: IBinder, timeoutMs: Long = 9_000, destroy: () -> Unit) {
    if (!binder.isBinderAlive) return
    val stopped = CountDownLatch(1)
    val death = IBinder.DeathRecipient { stopped.countDown() }
    try {
        binder.linkToDeath(death, 0)
        Closeable {
            try {
                binder.unlinkToDeath(death, 0)
            } catch (_: NoSuchElementException) {
                // 死亡监听已移除，仍以关闭请求和等待结果为准。
            }
        }.use {
            destroy()
            if (!stopped.await(timeoutMs, TimeUnit.MILLISECONDS)) {
                throw DeviceFailure("cleanup_pending", "等待 Shizuku 设备端服务退出超时")
            }
        }
    } catch (_: DeadObjectException) {
        // 服务在注册监听或发送关闭请求时已经退出。
    }
}

internal class DeviceAccess(private val context: Context) {
    private val root = RootAccess()

    private val userService = Shizuku.UserServiceArgs(ComponentName(context, GameUserService::class.java))
        .daemon(false)
        .tag("m7a-device")
        .processNameSuffix("device")
        .version(BuildConfig.VERSION_CODE)

    fun state(privilege: Privilege): PermissionState {
        if (privilege == Privilege.ROOT) return root.permission
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

    fun probeRoot() = root.probe()

    fun open(privilege: Privilege, token: String): DeviceLease = when (privilege) {
        Privilege.SHIZUKU -> openUserService(token)
        Privilege.ROOT -> root.open(context.applicationInfo.sourceDir, token)
    }

    fun recoverAudio(privilege: Privilege) {
        if (privilege == Privilege.ROOT) {
            root.recoverAudio(context.applicationInfo.sourceDir)
            return
        }
        recoverShizuku()
        UserBinding().use { binding ->
            val remote = bindUserService(binding)
            if (IDeviceBootstrap.Stub.asInterface(remote).recoverAudio() != 0) {
                throw DeviceFailure("cleanup_pending")
            }
        }
    }

    /** 只尝试回收本应用同一 tag 的残留 UserService。 */
    fun recoverShizuku() {
        if (state(Privilege.SHIZUKU) != PermissionState.READY) return
        val binding = UserBinding()
        if (Shizuku.peekUserService(userService, binding) >= 0) {
            binding.use {
                if (!it.connected.await(3, TimeUnit.SECONDS)) {
                    throw DeviceFailure("cleanup_pending", "等待上次 Shizuku 设备端服务连接超时")
                }
            }
        }
    }

    private fun openUserService(token: String): DeviceLease {
        val binding = UserBinding()
        try {
            val remote = bindUserService(binding)
            binding.port = IDeviceBootstrap.Stub.asInterface(remote).start(token, binding.owner)
            if (binding.port == GameUserService.BUSY) throw DeviceFailure(AppServer.BUSY)
            if (binding.port !in 1..65535) throw DeviceFailure("service_start")
            return binding
        } catch (error: Exception) {
            val failure = if (error is DeviceFailure) error else DeviceFailure("service_start", error.toString())
            try {
                binding.close()
            } catch (cleanupError: Exception) {
                failure.addSuppressed(cleanupError)
            }
            throw failure
        }
    }

    private fun bindUserService(binding: UserBinding): IBinder {
        Shizuku.bindUserService(userService, binding)
        if (!binding.connected.await(12, TimeUnit.SECONDS)) throw DeviceFailure("service_start")
        return binding.remote ?: throw DeviceFailure("service_start")
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
            if (binder == null) {
                Shizuku.unbindUserService(userService, this, true)
                return
            }
            try {
                closeUserService(binder) {
                    IDeviceBootstrap.Stub.asInterface(binder).destroy()
                }
            } finally {
                // Binder 提供实际退出结果，此处顺带移除 Shizuku 的绑定。
                runCatching { Shizuku.unbindUserService(userService, this, true) }
                    .onFailure { Log.w("M7ADevice", "Cannot remove Shizuku binding", it) }
            }
        }
    }

    companion object {
        const val SHIZUKU_PACKAGE = "moe.shizuku.privileged.api"
        const val GAME_PACKAGE = "com.miHoYo.hkrpg"
        const val PERMISSION_REQUEST = 1802
    }
}
