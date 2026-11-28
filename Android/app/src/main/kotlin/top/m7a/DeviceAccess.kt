package top.m7a

import android.content.Context
import android.content.pm.PackageManager
import android.util.Base64
import rikka.shizuku.Shizuku
import rikka.sui.Sui
import java.io.Closeable
import java.io.File
import java.io.IOException
import java.security.SecureRandom

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

internal fun shizukuPermissionState(
    hasProvider: () -> Boolean,
    pingBinder: () -> Boolean = Shizuku::pingBinder,
    isAuthorized: () -> Boolean = {
        Shizuku.getVersion() >= 13 && Shizuku.checkSelfPermission() == PackageManager.PERMISSION_GRANTED
    },
): PermissionState = runCatching {
    // Sui 没有管理 APK，其他兼容实现也不需要安装原版 Shizuku。
    if (pingBinder()) {
        if (isAuthorized()) PermissionState.READY else PermissionState.NOT_AUTHORIZED
    } else {
        if (hasProvider()) PermissionState.NOT_RUNNING else PermissionState.NOT_INSTALLED
    }
}.getOrDefault(PermissionState.NOT_RUNNING)

internal fun Context.shizukuPermission(): PermissionState = shizukuPermissionState(
    hasProvider = { Sui.isSui() || DeviceAccess.SHIZUKU_MANAGER_PACKAGES.any(::hasPackage) },
)

internal interface DeviceLease : Closeable {
    val port: Int
}

internal val Context.deviceServiceLauncher: File
    get() = File(applicationInfo.nativeLibraryDir, "libm7a_launcher.so")

internal class DeviceAccess(private val context: Context, trace: (String) -> Unit) {
    private val root = RootAccess(context.deviceServiceLauncher)
    private val shizuku = ShizukuAccess({ audio -> startShizukuProcess(context, audio, trace) }, trace)

    fun state(privilege: Privilege): PermissionState {
        if (privilege == Privilege.ROOT) return root.permission
        return context.shizukuPermission()
    }

    fun requestShizukuPermission() {
        if (state(Privilege.SHIZUKU) == PermissionState.NOT_AUTHORIZED && Shizuku.getVersion() >= 13) {
            Shizuku.requestPermission(PERMISSION_REQUEST)
        }
    }

    fun probeRoot() = root.probe()

    fun open(privilege: Privilege, token: String, cancelled: () -> Boolean): DeviceLease = when (privilege) {
        Privilege.SHIZUKU -> shizuku.open(token, cancelled)
        Privilege.ROOT -> root.open(context.applicationInfo.sourceDir, token, cancelled)
    }

    fun recoverAudio(privilege: Privilege) = when (privilege) {
        Privilege.SHIZUKU -> shizuku.recoverAudio()
        Privilege.ROOT -> root.recoverAudio(context.applicationInfo.sourceDir)
    }

    companion object {
        val SHIZUKU_MANAGER_PACKAGES = listOf("moe.shizuku.privileged.api", "roro.stellar.manager")
        const val GAME_PACKAGE = "com.miHoYo.hkrpg"
        const val PERMISSION_REQUEST = 1802
    }
}
