package org.march7th.assistant.ui

import androidx.annotation.StringRes
import androidx.compose.runtime.Composable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import org.march7th.assistant.Calyx
import org.march7th.assistant.GameState
import org.march7th.assistant.PermissionState
import org.march7th.assistant.Privilege
import org.march7th.assistant.R
import org.march7th.assistant.ServiceState
import org.march7th.assistant.TaskId

/** 界面文案统一从资源读取，和 Context.tr 同名。 */
@Composable
@ReadOnlyComposable
internal fun tr(@StringRes id: Int, vararg args: Any): String = stringResource(id, *args)

internal val TaskId.title: Int
    get() = when (this) {
        TaskId.DAILY -> R.string.daily
        TaskId.REWARDS -> R.string.rewards
        TaskId.POWER -> R.string.power
    }

internal val TaskId.summary: Int
    get() = when (this) {
        TaskId.DAILY -> R.string.task_daily_summary
        TaskId.REWARDS -> R.string.task_rewards_summary
        TaskId.POWER -> R.string.task_power_summary
    }

internal val TaskId.icon: ImageVector
    get() = when (this) {
        TaskId.DAILY -> M7Icons.Daily
        TaskId.REWARDS -> M7Icons.Gift
        TaskId.POWER -> M7Icons.Bolt
    }

internal val Privilege.title: Int
    get() = when (this) {
        Privilege.SHIZUKU -> R.string.method_shizuku
        Privilege.ROOT -> R.string.method_root
    }

internal fun permissionLabel(privilege: Privilege, permission: PermissionState): Int = when (permission) {
    PermissionState.NOT_CHECKED -> R.string.permission_unchecked
    PermissionState.NOT_INSTALLED ->
        if (privilege == Privilege.ROOT) R.string.permission_no_root else R.string.permission_missing
    PermissionState.NOT_RUNNING -> R.string.permission_inactive
    PermissionState.NOT_AUTHORIZED -> R.string.permission_denied
    PermissionState.READY -> R.string.permission_ready
}

internal fun rootPermissionHint(privilege: Privilege, permission: PermissionState): Int? {
    if (privilege != Privilege.ROOT) return null
    return when (permission) {
        PermissionState.NOT_CHECKED -> R.string.guide_root_unchecked
        PermissionState.NOT_AUTHORIZED -> R.string.guide_root_denied
        else -> null
    }
}

internal val ServiceState.label: Int
    get() = when (this) {
        ServiceState.IDLE -> R.string.service_idle
        ServiceState.RECOVERING -> R.string.service_recovering
        ServiceState.STARTING -> R.string.service_starting
        ServiceState.CONNECTED -> R.string.service_connected
        ServiceState.CLEANING -> R.string.service_cleaning
    }

internal val GameState.label: Int
    get() = when (this) {
        GameState.OFF -> R.string.game_off
        GameState.STARTING -> R.string.game_starting
        GameState.FLASHING -> R.string.game_flashing
        GameState.RETURNING -> R.string.game_returning
        GameState.READY -> R.string.game_ready
        GameState.MANUAL_LOGIN -> R.string.game_manual_login
    }

internal val Calyx.title: Int
    get() = when (this) {
        Calyx.CREDITS -> R.string.calyx_credits
        Calyx.EXP -> R.string.calyx_exp
        Calyx.MATERIALS -> R.string.calyx_materials
    }

internal val Calyx.reward: Int
    get() = when (this) {
        Calyx.CREDITS -> R.string.calyx_credits_reward
        Calyx.EXP -> R.string.calyx_exp_reward
        Calyx.MATERIALS -> R.string.calyx_materials_reward
    }

/** 出错后界面能直接带用户去的地方。 */
internal enum class ErrorFix { NONE, GUIDE, LOGS, APP_SETTINGS }

internal class ErrorInfo(@StringRes val title: Int, @StringRes val advice: Int, val fix: ErrorFix)

/** 契约里列出的错误码各有标题和处理步骤，其余错误码走通用说明并引导看日志。 */
internal fun errorInfo(code: String?): ErrorInfo? = when (code) {
    null -> null
    "service_busy", "cleanup_pending" -> ErrorInfo(R.string.error_busy_title, R.string.error_busy_advice, ErrorFix.NONE)
    "service_start" -> ErrorInfo(R.string.error_service_title, R.string.error_service_advice, ErrorFix.GUIDE)
    "root_unavailable" -> ErrorInfo(R.string.error_root_title, R.string.error_root_advice, ErrorFix.GUIDE)
    "game_not_installed" -> ErrorInfo(R.string.error_game_title, R.string.error_game_advice, ErrorFix.NONE)
    "manual_action_required" -> ErrorInfo(R.string.error_login_title, R.string.error_login_advice, ErrorFix.NONE)
    "keyguard_locked" -> ErrorInfo(R.string.error_locked_title, R.string.error_locked_advice, ErrorFix.NONE)
    "device_asleep" -> ErrorInfo(R.string.error_asleep_title, R.string.error_asleep_advice, ErrorFix.NONE)
    "inject_denied" -> ErrorInfo(R.string.error_inject_title, R.string.error_inject_advice, ErrorFix.GUIDE)
    "interrupted" -> ErrorInfo(R.string.error_interrupted_title, R.string.error_interrupted_advice, ErrorFix.APP_SETTINGS)
    "foreground_start" -> ErrorInfo(R.string.error_foreground_title, R.string.error_foreground_advice, ErrorFix.APP_SETTINGS)
    "task_failed" -> ErrorInfo(R.string.error_task_title, R.string.error_task_advice, ErrorFix.LOGS)
    "runtime_error" -> ErrorInfo(R.string.error_runtime_title, R.string.error_runtime_advice, ErrorFix.LOGS)
    else -> ErrorInfo(R.string.error_unknown_title, R.string.error_unknown_advice, ErrorFix.LOGS)
}

/** 「常见问题」里按这个顺序列出。 */
internal val commonErrors = listOf(
    "service_start", "inject_denied", "keyguard_locked", "device_asleep", "manual_action_required",
    "service_busy", "interrupted", "game_not_installed", "root_unavailable", "task_failed", "runtime_error",
)
