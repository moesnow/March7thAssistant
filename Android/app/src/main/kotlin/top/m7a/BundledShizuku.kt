package top.m7a

import android.content.Context
import android.util.AtomicFile
import java.io.File
import java.io.IOException

internal const val BUNDLED_SHIZUKU_APK = "shizuku/Shizuku.apk"
private val shizukuApkLock = Any()

/** 在 I/O 线程准备安装器可读的副本。权限引导和应用更新各自使用独立缓存。 */
internal fun prepareBundledShizuku(context: Context): File = synchronized(shizukuApkLock) {
    val directory = File(context.cacheDir, "shizuku-install")
    if (!directory.isDirectory && !directory.mkdirs()) throw IOException("Cannot create Shizuku install cache")
    val apk = File(directory, "Shizuku.apk")
    val atomic = AtomicFile(apk)
    val output = atomic.startWrite()
    try {
        context.assets.open(BUNDLED_SHIZUKU_APK).use { it.copyTo(output) }
        atomic.finishWrite(output)
    } catch (error: Exception) {
        atomic.failWrite(output)
        throw error
    }
    apk
}
