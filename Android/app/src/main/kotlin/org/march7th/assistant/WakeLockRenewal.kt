package org.march7th.assistant

/** 续期使用与系统唤醒锁相同的 uptime 时钟。关闭后，已出队的回调也不能再拿锁。 */
internal class WakeLockRenewal(
    private val acquire: (Long) -> Unit,
    private val release: () -> Unit,
    private val now: () -> Long,
    private val postAtTime: (Runnable, Long) -> Unit,
    private val removeCallbacks: (Runnable) -> Unit,
    private val onRenewalError: (Exception) -> Unit,
) : AutoCloseable {
    private var active = false
    private val renew = Runnable {
        synchronized(this) {
            if (!active) return@Runnable
            try {
                acquire(TIMEOUT_MS)
            } catch (error: Exception) {
                // 重拿锁可能已撤销旧的超时回调，失败时先尝试释放。
                runCatching(release).onFailure(error::addSuppressed)
                onRenewalError(error)
            }
            scheduleRenewal()
        }
    }

    @Synchronized
    fun start() {
        if (active) return
        active = true
        acquire(TIMEOUT_MS)
        scheduleRenewal()
    }

    @Synchronized
    override fun close() {
        if (!active) return
        active = false
        try {
            removeCallbacks(renew)
        } finally {
            release()
        }
    }

    private fun scheduleRenewal() {
        postAtTime(renew, now() + RENEW_INTERVAL_MS)
    }

    private companion object {
        const val TIMEOUT_MS = 20 * 60 * 1000L
        const val RENEW_INTERVAL_MS = 10 * 60 * 1000L
    }
}
