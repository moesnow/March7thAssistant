package top.m7a

import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.DeadObjectException
import android.os.ParcelFileDescriptor
import android.os.Process.SHELL_UID
import android.os.RemoteException
import moe.shizuku.server.IRemoteProcess
import moe.shizuku.server.IShizukuService
import rikka.shizuku.Shizuku
import java.io.Closeable
import java.io.File
import java.io.InputStream
import java.io.OutputStream
import java.util.concurrent.CompletableFuture
import java.util.concurrent.TimeUnit
import kotlin.concurrent.thread

/** 每次创建只认领自己的进程和管道。超时返回后仍持有旧请求，直到它失败或进程退出。 */
internal class ShizukuAccess(
    private val spawn: (recoverAudio: Boolean) -> Process,
    private val trace: (String) -> Unit,
    private val startTimeoutMs: Long = 15_000,
) {
    private var pending: CompletableFuture<DeviceProcess>? = null
    private var unconfirmed: Process? = null

    @Synchronized
    private fun reserve(token: String?): CompletableFuture<DeviceProcess> {
        if (pending != null) throw DeviceFailure("cleanup_pending", "上次 Shizuku 进程尚未退出")
        val previous = unconfirmed
        val ticket = CompletableFuture<DeviceProcess>()
        pending = ticket
        thread(name = "m7a-shizuku-create", isDaemon = true) {
            try {
                if (previous?.isAlive == true) throw DeviceFailure("cleanup_pending", "上次 Shizuku 进程尚未退出")
                val child = spawn(token == null)
                ticket.complete(DeviceProcess(child, "Shizuku", token, separateStderr = true) { exited ->
                    finish(ticket, child.takeUnless { exited })
                })
            } catch (error: Exception) {
                finish(ticket, previous)
                ticket.completeExceptionally(error)
            }
        }
        return ticket
    }

    @Synchronized
    private fun finish(ticket: CompletableFuture<DeviceProcess>, remaining: Process?) {
        if (pending !== ticket) return
        unconfirmed = remaining
        pending = null
    }

    private fun create(token: String?, deadline: Long, cancelled: () -> Boolean): DeviceProcess {
        if (cancelled()) throw DeviceFailure("stopped")
        val created = reserve(token)
        try {
            return created.awaitStage(deadline, "创建 Shizuku 进程", cancelled)
        } catch (error: Exception) {
            // Binder 调用可能迟到。旧进程不会收到令牌，也不会被交给下次调用。
            created.thenAcceptAsync { late ->
                runCatching { late.close() }
                    .onSuccess { trace("已回收迟到的 Shizuku 进程") }
                    .onFailure { trace("迟到的 Shizuku 进程清理待确认：${it.message}") }
            }
            if (error is DeviceFailure) throw error
            throw DeviceFailure("service_start", "创建 Shizuku 进程失败：${error.message}")
        }
    }

    fun open(token: String, cancelled: () -> Boolean = { false }): DeviceLease {
        val deadline = startDeadline(startTimeoutMs)
        val process = create(token, deadline, cancelled)
        return process.open(token, deadline, cancelled, trace = trace)
    }

    fun recoverAudio() = create(null, startDeadline(startTimeoutMs)) { false }.recoverAudio()
}

/** 唯一依赖 Shizuku API 13 旧进程接口的位置。命令只包含安装目录中的 launcher 和 APK。 */
internal fun startShizukuProcess(context: Context, recoverAudio: Boolean, trace: (String) -> Unit): Process {
    val manager = runCatching {
        context.packageManager.getPackageInfo(DeviceAccess.SHIZUKU_PACKAGE, 0).let { "${it.versionName} (${it.longVersionCode})" }
    }.getOrDefault("未知")
    val soc = if (Build.VERSION.SDK_INT >= 31) Build.SOC_MODEL else Build.HARDWARE
    trace("${Build.MANUFACTURER} ${Build.MODEL} (${Build.DEVICE}, $soc), Android ${Build.VERSION.RELEASE}/API ${Build.VERSION.SDK_INT}, " +
        "ROM=${Build.DISPLAY}, fingerprint=${Build.FINGERPRINT}")
    trace("App=${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE}, ${BuildConfig.BUILD_TYPE}), " +
        "Shizuku manager=$manager, SDK=${BuildConfig.SHIZUKU_SDK_VERSION}")
    try {
        val binder = Shizuku.getBinder()?.takeIf { it.pingBinder() }
            ?: throw DeviceFailure("permission_unavailable", "Shizuku Binder 未连接")
        if (Shizuku.checkSelfPermission() != PackageManager.PERMISSION_GRANTED) {
            throw DeviceFailure("permission_unavailable", "Shizuku 未授权")
        }
        val api = Shizuku.getVersion()
        val uid = Shizuku.getUid()
        trace("Shizuku API=$api, UID=$uid, " + if (recoverAudio) "恢复音频" else "启动设备服务")
        val info = context.applicationInfo
        val argv = shizukuLaunchArgs(api, uid, context.deviceServiceLauncher, info.sourceDir, recoverAudio)
        val remote = IShizukuService.Stub.asInterface(binder).newProcess(argv, null, null)
            ?: throw DeviceFailure("shizuku_unsupported", "Shizuku 未提供进程接口")
        return RemoteLauncher.connect(remote)
    } catch (error: SecurityException) {
        throw DeviceFailure("permission_unavailable", "Shizuku 拒绝创建进程：${error.message}")
    } catch (_: DeadObjectException) {
        throw DeviceFailure("permission_unavailable", "Shizuku Binder 已断开")
    } catch (error: RemoteException) {
        val code = if (error.message.orEmpty().contains("unimplemented", ignoreCase = true)) "shizuku_unsupported" else "service_start"
        throw DeviceFailure(code, "Shizuku 进程接口调用失败：${error.message}")
    }
}

internal fun shizukuLaunchArgs(api: Int, uid: Int, launcher: File, apk: String, recoverAudio: Boolean): Array<String> {
    if (api != 13) throw DeviceFailure("shizuku_unsupported", "进程接口需要 API 13，当前为 $api")
    if (uid != SHELL_UID && uid != 0) throw DeviceFailure("shizuku_unsupported", "不支持的 Shizuku UID $uid")
    if (!launcher.canExecute()) throw DeviceFailure("service_start", "Shizuku launcher 缺失或不可执行")
    return if (recoverAudio) arrayOf(launcher.absolutePath, apk, "--recover-audio") else arrayOf(launcher.absolutePath, apk)
}

private class RemoteLauncher(
    private val remote: IRemoteProcess,
    private val stdin: OutputStream,
    private val stdout: InputStream,
    private val stderr: InputStream,
) : Process() {
    override fun getOutputStream() = stdin
    override fun getInputStream() = stdout
    override fun getErrorStream() = stderr
    override fun waitFor() = remote.waitFor()
    override fun waitFor(timeout: Long, unit: TimeUnit) = remote.waitForTimeout(timeout, unit.name)
    override fun exitValue() = remote.exitValue()
    override fun destroy() = remote.destroy()
    override fun isAlive() = try {
        remote.asBinder().isBinderAlive && remote.alive()
    } catch (_: DeadObjectException) {
        false
    }

    companion object {
        fun connect(remote: IRemoteProcess): RemoteLauncher {
            val opened = mutableListOf<Closeable>()
            try {
                val stdin = ParcelFileDescriptor.AutoCloseOutputStream(remote.outputStream).also(opened::add)
                val stdout = ParcelFileDescriptor.AutoCloseInputStream(remote.inputStream).also(opened::add)
                val stderr = ParcelFileDescriptor.AutoCloseInputStream(remote.errorStream).also(opened::add)
                return RemoteLauncher(remote, stdin, stdout, stderr)
            } catch (error: Exception) {
                opened.forEach { runCatching { it.close() } }
                val failure = DeviceFailure("service_start", "连接 Shizuku 进程管道失败：${error.message}")
                runCatching { remote.destroy() }.onFailure(failure::addSuppressed)
                throw failure
            }
        }
    }
}
