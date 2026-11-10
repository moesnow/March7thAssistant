package org.march7th.assistant

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.IBinder
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

internal fun Context.tr(id: Int, vararg args: Any): String = getString(id, *args)

internal val TaskPhase.label: Int
    get() = when (this) {
        TaskPhase.IDLE -> R.string.phase_idle
        TaskPhase.PREPARING -> R.string.phase_preparing
        TaskPhase.WAITING_FOR_GAME -> R.string.phase_waiting
        TaskPhase.RUNNING -> R.string.phase_running
        TaskPhase.STOPPING -> R.string.phase_stopping
        TaskPhase.CLEANING -> R.string.phase_cleaning
        TaskPhase.SUCCEEDED -> R.string.phase_succeeded
        TaskPhase.STOPPED -> R.string.phase_stopped
        TaskPhase.FAILED -> R.string.phase_failed
    }

class TaskRunnerService : Service() {
    private val scope = CoroutineScope(Dispatchers.Main.immediate + SupervisorJob())
    private val controller by lazy { TaskController.get(this) }
    private val notifications by lazy { getSystemService(NotificationManager::class.java) }
    private var foreground = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            controller.stop()
            if (!foreground) stopSelf()
            return START_NOT_STICKY
        }
        if (foreground) return START_NOT_STICKY

        notifications.createNotificationChannel(
            NotificationChannel(CHANNEL, tr(R.string.notification_channel), NotificationManager.IMPORTANCE_LOW)
        )
        startForeground(NOTIFICATION_ID, notification(controller.state.value))
        foreground = true
        if (!controller.begin(::finish)) {
            finish()
            return START_NOT_STICKY
        }
        scope.launch {
            controller.state.collect {
                if (foreground && it.busy) notifications.notify(NOTIFICATION_ID, notification(it))
            }
        }
        return START_NOT_STICKY
    }

    private fun finish() {
        foreground = false
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        if (foreground) controller.stop()
        scope.cancel()
        super.onDestroy()
    }

    private fun notification(state: TaskState): Notification {
        val flags = PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        val view = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), flags)
        val stop = PendingIntent.getService(
            this, 0, Intent(this, TaskRunnerService::class.java).setAction(ACTION_STOP), flags
        )
        val step = when (state.phase) {
            TaskPhase.WAITING_FOR_GAME -> 1
            TaskPhase.RUNNING -> 2
            TaskPhase.CLEANING -> 3
            else -> 0
        }
        return Notification.Builder(this, CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_task)
            .setContentTitle(tr(when (state.task) {
                TaskId.DAILY -> R.string.daily
                TaskId.REWARDS -> R.string.rewards
                TaskId.POWER -> R.string.power
            }))
            .setContentText(tr(state.phase.label))
            .setContentIntent(view)
            .setOnlyAlertOnce(true)
            .setOngoing(true)
            .setProgress(3, step, state.phase == TaskPhase.STOPPING)
            .addAction(Notification.Action.Builder(null, tr(R.string.stop), stop).build())
            .build()
    }

    companion object {
        private const val CHANNEL = "daily_task"
        private const val NOTIFICATION_ID = 2
        private const val ACTION_STOP = "org.march7th.assistant.STOP_TASK"
    }
}
