package top.m7a

import android.content.Context
import android.content.pm.PackageManager
import android.util.Base64
import rikka.shizuku.Shizuku
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

    fun open(privilege: Privilege, token: String, cancelled: () -> Boolean): DeviceLease = when (privilege) {
        Privilege.SHIZUKU -> shizuku.open(token, cancelled)
        Privilege.ROOT -> root.open(context.applicationInfo.sourceDir, token, cancelled)
    }

    fun recoverAudio(privilege: Privilege) = when (privilege) {
        Privilege.SHIZUKU -> shizuku.recoverAudio()
        Privilege.ROOT -> root.recoverAudio(context.applicationInfo.sourceDir)
    }

    companion object {
        const val SHIZUKU_PACKAGE = "moe.shizuku.privileged.api"
        const val GAME_PACKAGE = "com.miHoYo.hkrpg"
        const val PERMISSION_REQUEST = 1802
    }
}
