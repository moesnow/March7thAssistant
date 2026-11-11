package org.march7th.assistant.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import org.march7th.assistant.GameState
import org.march7th.assistant.PermissionState
import org.march7th.assistant.R
import org.march7th.assistant.ServiceState
import org.march7th.assistant.StepStatus
import org.march7th.assistant.TaskPhase
import org.march7th.assistant.TaskState
import org.march7th.assistant.label

@Composable
internal fun StatusScreen(state: TaskState, lastLog: String?, navigator: Navigator) {
    Column(Modifier.fillMaxSize()) {
        SubPageBar(tr(R.string.status_title), navigator.back)
        Column(
            Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(start = 16.dp, end = 16.dp, bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            PanelCard {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconBadge(state.task.icon)
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(
                            tr(R.string.status_current_task),
                            style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Text(tr(state.task.title), style = MaterialTheme.typography.titleMedium)
                    }
                    // 有步骤失败但其余完成时，和首页一样标成部分完成。
                    val partial = state.phase == TaskPhase.FAILED && state.errorCode == "task_failed" &&
                        state.steps.any { it.status == StepStatus.DONE }
                    if (partial) {
                        StatusPill(tr(R.string.pill_partial), Tone.WARNING)
                    } else {
                        StatusPill(tr(state.phase.label), state.phase.tone)
                    }
                }
                Spacer(Modifier.height(18.dp))
                Timeline(state)
            }

            SectionLabel(tr(R.string.status_where))
            PanelCard {
                ScreensDiagram(state)
                Spacer(Modifier.height(14.dp))
                BodyText(tr(whereCaption(state)))
            }

            SectionLabel(tr(R.string.status_details))
            PanelCard(padding = PaddingValues(0.dp)) {
                val serviceUp = state.service == ServiceState.CONNECTED
                SettingRow(
                    tr(R.string.status_service),
                    icon = M7Icons.Service,
                    iconTone = if (serviceUp) Tone.ACTIVE else Tone.NEUTRAL,
                    summary = tr(state.service.detail),
                    trailing = { StatusPill(tr(state.service.label), if (serviceUp) Tone.SUCCESS else state.service.tone) },
                )
                RowDivider()
                val display = state.displayId
                SettingRow(
                    tr(R.string.status_display),
                    icon = M7Icons.Display,
                    iconTone = if (display != null) Tone.ACTIVE else Tone.NEUTRAL,
                    summary = if (display != null) tr(R.string.status_display_detail, display) else tr(R.string.status_display_none),
                    trailing = {
                        StatusPill(
                            tr(if (display != null) R.string.status_display_on else R.string.status_display_off),
                            if (display != null) Tone.SUCCESS else Tone.NEUTRAL,
                        )
                    },
                )
                RowDivider()
                SettingRow(
                    tr(R.string.status_game),
                    icon = M7Icons.Game,
                    iconTone = if (state.game == GameState.OFF) Tone.NEUTRAL else Tone.ACTIVE,
                    summary = gameLocation(state),
                    trailing = { StatusPill(tr(state.game.label), state.game.tone) },
                )
                RowDivider()
                SettingRow(
                    tr(R.string.status_panel),
                    icon = if (state.panelOff) M7Icons.ScreenOff else M7Icons.Phone,
                    iconTone = if (state.panelOff) Tone.ACTIVE else Tone.NEUTRAL,
                    summary = tr(if (state.panelOff) R.string.status_panel_off_detail else R.string.status_panel_on_detail),
                    trailing = {
                        StatusPill(
                            tr(if (state.panelOff) R.string.status_panel_off else R.string.status_panel_on),
                            if (state.panelOff) Tone.ACTIVE else Tone.NEUTRAL,
                        )
                    },
                )
                RowDivider()
                val ready = state.permission == PermissionState.READY
                SettingRow(
                    tr(R.string.home_permission),
                    icon = M7Icons.Shield,
                    iconTone = if (ready) Tone.SUCCESS else Tone.WARNING,
                    summary = tr(rootPermissionHint(state.privilege, state.permission) ?: state.privilege.title),
                    onClick = { navigator.open(SubPage.GUIDE) },
                    trailing = {
                        StatusPill(tr(permissionLabel(state.privilege, state.permission)), if (ready) Tone.SUCCESS else Tone.WARNING)
                    },
                )
            }

            if (lastLog != null) {
                PanelCard(padding = PaddingValues(0.dp)) {
                    SettingRow(
                        tr(R.string.home_latest_log),
                        icon = M7Icons.Logs,
                        iconTone = Tone.NEUTRAL,
                        summary = lastLog,
                        summaryMaxLines = 3,
                        onClick = { navigator.openTab(Tab.LOGS) },
                    )
                }
            }
        }
    }
}

private val TaskPhase.tone: Tone
    get() = when (this) {
        TaskPhase.IDLE, TaskPhase.STOPPED -> Tone.NEUTRAL
        TaskPhase.SUCCEEDED -> Tone.SUCCESS
        TaskPhase.FAILED -> Tone.ERROR
        TaskPhase.STOPPING -> Tone.WARNING
        else -> Tone.ACTIVE
    }

private val ServiceState.tone: Tone
    get() = if (this == ServiceState.IDLE) Tone.NEUTRAL else Tone.ACTIVE

private val ServiceState.detail: Int
    get() = when (this) {
        ServiceState.IDLE -> R.string.service_idle_detail
        ServiceState.RECOVERING -> R.string.service_recovering_detail
        ServiceState.STARTING -> R.string.service_starting_detail
        ServiceState.CONNECTED -> R.string.service_connected_detail
        ServiceState.CLEANING -> R.string.service_cleaning_detail
    }

private val GameState.tone: Tone
    get() = when (this) {
        GameState.OFF -> Tone.NEUTRAL
        GameState.READY -> Tone.SUCCESS
        GameState.FLASHING, GameState.MANUAL_LOGIN -> Tone.WARNING
        else -> Tone.ACTIVE
    }

private fun onVirtual(state: TaskState) = state.gameDisplayId != null && state.gameDisplayId == state.displayId
private fun onPhysical(state: TaskState) = state.gameDisplayId == 0

@Composable
private fun gameLocation(state: TaskState): String {
    val id = state.gameDisplayId
    return when {
        id == null -> tr(R.string.status_game_nowhere)
        onVirtual(state) -> tr(R.string.status_game_virtual, id)
        id == 0 -> tr(R.string.status_game_physical)
        else -> tr(R.string.status_game_other, id)
    }
}

private fun whereCaption(state: TaskState): Int = when {
    state.game == GameState.MANUAL_LOGIN -> R.string.status_where_login
    state.game == GameState.FLASHING -> R.string.game_flashing_detail
    state.game == GameState.RETURNING -> R.string.home_returning_detail
    onVirtual(state) && state.panelOff -> R.string.status_where_virtual_panel_off
    onVirtual(state) -> R.string.status_where_virtual
    state.displayId != null -> R.string.status_where_waiting
    else -> R.string.status_where_idle
}

/** 关掉面板的手机屏幕，深浅主题下都画成黑屏。 */
private val PanelOffColor = Color(0xFF0E0C10)

/** 手机屏幕和后台虚拟屏并排画出来，「游戏」标记落在它当前所在的那一块。 */
@Composable
private fun ScreensDiagram(state: TaskState) {
    val scheme = MaterialTheme.colorScheme
    val hasDisplay = state.displayId != null
    val physical = onPhysical(state)
    val virtual = onVirtual(state)
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.Center) {
        ScreenBox(
            width = 62.dp, height = 110.dp, corner = 12.dp,
            label = tr(R.string.status_screen_physical),
            caption = tr(if (state.panelOff) R.string.status_panel_off else R.string.status_panel_on),
            active = true, dimmed = state.panelOff, game = physical,
        )
        Column(Modifier.padding(horizontal = 10.dp).padding(bottom = 64.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(
                M7Icons.ArrowBack, null,
                Modifier.size(22.dp).rotate(180f).alpha(if (physical) 1f else 0.25f),
                tint = if (physical) scheme.primary else scheme.outline,
            )
        }
        ScreenBox(
            width = 150.dp, height = 84.dp, corner = 10.dp,
            label = tr(R.string.status_screen_virtual),
            caption = state.displayId?.let { tr(R.string.status_display_id, it) } ?: tr(R.string.status_display_off),
            active = hasDisplay, dimmed = false, game = virtual,
        )
    }
}

@Composable
private fun ScreenBox(width: Dp, height: Dp, corner: Dp, label: String, caption: String, active: Boolean, dimmed: Boolean, game: Boolean) {
    val scheme = MaterialTheme.colorScheme
    val shape = RoundedCornerShape(corner)
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Box(
            Modifier
                .size(width, height)
                .alpha(if (active) 1f else 0.45f)
                .clip(shape)
                .background(if (dimmed) PanelOffColor else if (game) scheme.primaryContainer else scheme.surfaceContainerHigh)
                .border(2.dp, if (game) scheme.primary else scheme.outline.copy(alpha = 0.6f), shape),
            contentAlignment = Alignment.Center,
        ) {
            if (game) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Box(Modifier.size(32.dp).clip(CircleShape).background(scheme.primary), contentAlignment = Alignment.Center) {
                        Icon(M7Icons.Game, null, Modifier.size(20.dp), tint = scheme.onPrimary)
                    }
                    Text(
                        tr(R.string.status_game), Modifier.padding(top = 2.dp),
                        style = MaterialTheme.typography.labelSmall,
                        color = if (dimmed) Color.White else scheme.onPrimaryContainer,
                    )
                }
            }
        }
        Spacer(Modifier.height(8.dp))
        Text(label, style = MaterialTheme.typography.labelLarge, textAlign = TextAlign.Center)
        Text(caption, style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant, textAlign = TextAlign.Center)
    }
}

@Composable
private fun Timeline(state: TaskState) {
    val current = when (state.phase) {
        TaskPhase.PREPARING -> 0
        TaskPhase.WAITING_FOR_GAME -> 1
        TaskPhase.RUNNING -> 2
        TaskPhase.STOPPING, TaskPhase.CLEANING -> 3
        TaskPhase.SUCCEEDED -> 4
        else -> -1
    }
    val steps = listOf(
        R.string.phase_preparing_short to R.string.timeline_prepare,
        R.string.step_game to R.string.timeline_game,
        R.string.step_task to R.string.timeline_task,
        R.string.phase_cleaning_short to R.string.timeline_cleanup,
    )
    steps.forEachIndexed { index, (title, detail) ->
        val step = when {
            current < 0 -> StepState.PENDING
            index < current -> StepState.DONE
            index == current -> StepState.CURRENT
            else -> StepState.PENDING
        }
        StepItem(index + 1, tr(title), step) {
            BodyText(
                when {
                    index == 3 && state.phase == TaskPhase.STOPPING -> tr(R.string.home_stopping_detail)
                    index == 2 -> tr(detail, tr(state.task.title))
                    else -> tr(detail)
                }
            )
            // 本轮各步骤及状态列在「执行任务」下面。
            if (index == 2 && state.steps.isNotEmpty()) {
                Column(Modifier.padding(top = 6.dp)) {
                    for (item in state.steps) StepResultRow(item, running = state.busy)
                }
            }
        }
    }
    val error = errorInfo(state.errorCode)
    val failedSteps = state.steps.count { it.status == StepStatus.FAILED }
    val stepFailure = state.errorCode == "task_failed" && failedSteps > 0
    val (result, text) = when (state.phase) {
        TaskPhase.SUCCEEDED -> StepState.DONE to tr(R.string.phase_succeeded)
        TaskPhase.STOPPED -> StepState.DONE to tr(R.string.phase_stopped)
        TaskPhase.FAILED -> StepState.FAILED to when {
            stepFailure && state.steps.any { it.status == StepStatus.DONE } -> tr(R.string.pill_partial)
            else -> error?.let { tr(it.title) } ?: tr(R.string.phase_failed)
        }
        else -> StepState.PENDING to tr(R.string.timeline_result)
    }
    StepItem(5, text, result, last = true) {
        when (state.phase) {
            TaskPhase.SUCCEEDED -> state.summary?.let { BodyText(it) }
            TaskPhase.FAILED -> BodyText(
                if (stepFailure) tr(R.string.home_partial, failedSteps) else tr(R.string.timeline_failed_detail)
            )
            TaskPhase.STOPPED -> BodyText(tr(R.string.home_stopped_detail))
            else -> Unit
        }
    }
}
