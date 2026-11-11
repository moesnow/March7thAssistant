package org.march7th.assistant.ui

import androidx.annotation.StringRes
import androidx.compose.runtime.Composable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringArrayResource
import androidx.compose.ui.res.stringResource
import org.march7th.assistant.Catalog
import org.march7th.assistant.GameState
import org.march7th.assistant.InstanceType
import org.march7th.assistant.PermissionState
import org.march7th.assistant.PlanItem
import org.march7th.assistant.Privilege
import org.march7th.assistant.R
import org.march7th.assistant.ServiceState
import org.march7th.assistant.StepId
import org.march7th.assistant.StepResult
import org.march7th.assistant.StepStatus
import org.march7th.assistant.TaskId
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** 界面文案统一从资源读取，和 Context.tr 同名。 */
@Composable
@ReadOnlyComposable
internal fun tr(@StringRes id: Int, vararg args: Any): String = stringResource(id, *args)

internal val TaskId.title: Int
    get() = when (this) {
        TaskId.ROUTINE -> R.string.routine
        TaskId.DAILY -> R.string.daily
        TaskId.POWER -> R.string.power
    }

internal val TaskId.icon: ImageVector
    get() = when (this) {
        TaskId.ROUTINE -> M7Icons.Routine
        TaskId.DAILY -> M7Icons.Daily
        TaskId.POWER -> M7Icons.Bolt
    }

internal val StepId.title: Int
    get() = when (this) {
        StepId.ECHO -> R.string.instance_echo
        StepId.POWER -> R.string.power
        StepId.REWARDS -> R.string.rewards
        StepId.DAILY -> R.string.daily
    }

/** 表里的步骤用界面上的名字，其余步骤用 Python 报来的原名。 */
@Composable
@ReadOnlyComposable
internal fun stepName(step: StepResult): String = step.step?.let { tr(it.title) } ?: step.name

/** 周一为 1。 */
@Composable
@ReadOnlyComposable
internal fun weekday(day: Int): String = stringArrayResource(R.array.weekdays)[day - 1]

/** 结果卡和步骤清单里每一行的说明。running 为真时还没轮到的步骤显示「等待执行」，结束后才是「没有执行」。 */
@Composable
@ReadOnlyComposable
internal fun stepDetail(step: StepResult, running: Boolean = false): String = when (step.status) {
    StepStatus.DONE -> step.detail ?: tr(R.string.step_done)
    StepStatus.FAILED -> step.detail ?: tr(R.string.step_failed_detail)
    StepStatus.STOPPED -> tr(R.string.step_stopped)
    StepStatus.PENDING -> tr(if (running) R.string.step_waiting else R.string.step_pending)
    StepStatus.RUNNING -> tr(R.string.step_running)
    StepStatus.DISABLED -> step.startDay?.let { tr(R.string.step_starts_on, weekday(it)) } ?: tr(R.string.step_disabled)
}

/** 赤萼在数据里用地区作名称，显示时带上花萼名。 */
@Composable
@ReadOnlyComposable
internal fun instanceLabel(type: InstanceType, name: String, catalog: Catalog): String {
    if (type != InstanceType.CRIMSON_CALYX) return name
    val bud = catalog.instances[type].orEmpty().firstOrNull { it.id == name }?.detail ?: return name
    return tr(R.string.option_instance_summary, name, bud)
}

/** 「N 项，共 M 次」。 */
@Composable
@ReadOnlyComposable
internal fun planSize(plan: List<PlanItem>): String = tr(R.string.plan_size, plan.size, plan.sumOf { it.count })

private val clock = DateTimeFormatter.ofPattern("HH:mm", Locale.ROOT)

/** 「今天 21:47」「昨天 21:47」「11月9日 21:47」，不是今年的再带上年份。 */
@Composable
@ReadOnlyComposable
internal fun recordTime(millis: Long?): String {
    if (millis == null) return tr(R.string.time_none)
    val zone = ZoneId.systemDefault()
    val time = Instant.ofEpochMilli(millis).atZone(zone)
    val today = LocalDate.now(zone)
    val text = time.format(clock)
    return when (val date = time.toLocalDate()) {
        today -> tr(R.string.time_today, text)
        today.minusDays(1) -> tr(R.string.time_yesterday, text)
        else -> if (date.year == today.year) {
            tr(R.string.time_date, date.monthValue, date.dayOfMonth, text)
        } else {
            tr(R.string.time_full_date, date.year, date.monthValue, date.dayOfMonth, text)
        }
    }
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

internal val InstanceType.title: Int
    get() = when (this) {
        InstanceType.GOLDEN_CALYX -> R.string.instance_golden_calyx
        InstanceType.CRIMSON_CALYX -> R.string.instance_crimson_calyx
        InstanceType.STAGNANT_SHADOW -> R.string.instance_stagnant_shadow
        InstanceType.CAVERN -> R.string.instance_cavern
        InstanceType.ECHO -> R.string.instance_echo
        InstanceType.ORNAMENT -> R.string.instance_ornament
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
