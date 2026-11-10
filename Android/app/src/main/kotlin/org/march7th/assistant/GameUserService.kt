package org.march7th.assistant

import android.content.Context
import android.os.Binder
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.Process
import android.util.Log
import org.march7th.deviceservice.AppServer
import java.util.concurrent.FutureTask
import java.util.concurrent.TimeUnit

/** Shizuku 通过带 Context 的构造器加载此类。 */
class GameUserService(private val context: Context) : IDeviceBootstrap.Stub() {
    private val appUid = context.applicationInfo.uid
    private var server: AppServer? = null
    private var started = false

    @Synchronized
    override fun start(token: String, owner: IBinder): Int {
        if (Binder.getCallingUid() != appUid) {
            throw SecurityException()
        }
        check(!started)
        started = true
        owner.linkToDeath({ stopProcess() }, 0)
        val launch = FutureTask { AppServer.start(context.applicationInfo.sourceDir, token) }
        Handler(Looper.getMainLooper()).post(launch)
        try {
            val opened = launch.get(8, TimeUnit.SECONDS)
            server = opened
            return opened.port()
        } catch (error: Exception) {
            Log.e("M7ADevice", "UserService bootstrap failed", error)
            // 让调用方先收到失败结果，随后退出并释放实例锁。
            Handler(Looper.getMainLooper()).postDelayed({ stopProcess() }, 300)
            return if (error.cause?.message == AppServer.BUSY) BUSY else FAILED
        }
    }

    override fun destroy() {
        val caller = Binder.getCallingUid()
        if (caller != appUid && caller != Process.myUid() && caller != Process.SHELL_UID && caller != 0) {
            throw SecurityException()
        }
        stopProcess()
    }

    @Synchronized
    private fun stopProcess() {
        val running = server
        if (running == null) {
            Process.killProcess(Process.myPid())
        } else {
            running.stop()
        }
    }

    companion object {
        const val BUSY = -1
        const val FAILED = -2
    }
}
