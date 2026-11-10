package org.march7th.assistant.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
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
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import org.march7th.assistant.GameState
import org.march7th.assistant.PermissionState
import org.march7th.assistant.R
import org.march7th.assistant.ServiceState
import org.march7th.assistant.TaskPhase
import org.march7th.assistant.TaskState

private class Headline(val pill: Int, val tone: Tone, val title: String, val detail: String, val art: Int)

@Composable
private fun headline(state: TaskState): Headline {
    val task = tr(state.task.title)
    val error = errorInfo(state.errorCode)
    return when {
        state.service == ServiceState.RECOVERING -> Headline(
            R.string.pill_working, Tone.ACTIVE, tr(R.string.home_recovering), tr(R.string.home_recovering_detail), R.drawable.chibi_typing
        )
        state.phase == TaskPhase.PREPARING -> Headline(
            R.string.pill_running, Tone.ACTIVE, tr(R.string.phase_preparing), tr(R.string.home_preparing_detail), R.drawable.chibi_typing
        )
        state.phase == TaskPhase.WAITING_FOR_GAME -> Headline(
            R.string.pill_running, Tone.ACTIVE, tr(R.string.home_launching),
            tr(
                when (state.game) {
                    GameState.FLASHING -> R.string.game_flashing_detail
                    GameState.RETURNING -> R.string.home_returning_detail
                    GameState.MANUAL_LOGIN -> R.string.home_manual_login_detail
                    else -> R.string.home_launching_detail
                }
            ),
            R.drawable.chibi_typing,
        )
        state.phase == TaskPhase.RUNNING -> Headline(
            R.string.pill_running, Tone.ACTIVE, tr(R.string.home_running, task),
            tr(if (state.game == GameState.FLASHING) R.string.game_flashing_detail else R.string.home_running_detail),
            R.drawable.chibi_typing,
        )
        state.phase == TaskPhase.STOPPING -> Headline(
            R.string.pill_working, Tone.WARNING, tr(R.string.phase_stopping), tr(R.string.home_stopping_detail), R.drawable.chibi_typing
        )
        state.phase == TaskPhase.CLEANING -> Headline(
            R.string.pill_working, Tone.ACTIVE, tr(R.string.phase_cleaning), tr(R.string.home_cleaning_detail), R.drawable.chibi_typing
        )
        error != null -> Headline(
            R.string.pill_failed, Tone.ERROR, tr(R.string.home_failed), tr(R.string.home_failed_detail), R.drawable.chibi_lost
        )
        state.permission != PermissionState.READY -> Headline(
            R.string.pill_setup, Tone.WARNING, tr(R.string.home_setup),
            tr(rootPermissionHint(state.privilege, state.permission) ?: R.string.home_setup_detail), R.drawable.chibi_full,
        )
        state.phase == TaskPhase.SUCCEEDED -> Headline(
            R.string.pill_done, Tone.SUCCESS, tr(R.string.home_done, task),
            state.summary ?: tr(R.string.home_done_detail), R.drawable.chibi_wave,
        )
        state.phase == TaskPhase.STOPPED -> Headline(
            R.string.pill_stopped, Tone.NEUTRAL, tr(R.string.phase_stopped), tr(R.string.home_stopped_detail), R.drawable.chibi_full
        )
        else -> Headline(
            R.string.pill_ready, Tone.SUCCESS, tr(R.string.home_ready), tr(R.string.home_ready_detail), R.drawable.chibi_full
        )
    }
}

@Composable
internal fun HomeScreen(state: TaskState, lastLog: String?, actions: AppActions, navigator: Navigator) {
    val error = errorInfo(state.errorCode).takeUnless { state.busy }
    Column(Modifier.fillMaxSize()) {
        Column(
            Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(Modifier.padding(horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                Image(
                    painterResource(R.drawable.brand_logo), null,
                    Modifier.size(36.dp).clip(RoundedCornerShape(10.dp)),
                )
                Spacer(Modifier.width(10.dp))
                Text(tr(R.string.app_name), style = MaterialTheme.typography.titleLarge)
            }
            Hero(state)
            if (state.busy && state.game == GameState.MANUAL_LOGIN) {
                Notice(tr(R.string.home_manual_login_notice), tone = Tone.WARNING, icon = M7Icons.Warning)
            }
            if (error != null) {
                ErrorCard(error, state.errorCode.orEmpty(), actions, navigator)
            }
            Row(Modifier.height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                val ready = state.permission == PermissionState.READY
                Tile(
                    Modifier.weight(1f).fillMaxHeight(),
                    icon = M7Icons.Shield,
                    tone = if (ready) Tone.SUCCESS else Tone.WARNING,
                    label = tr(R.string.home_permission),
                    value = tr(state.privilege.title),
                    status = tr(permissionLabel(state.privilege, state.permission)),
                    onClick = { navigator.open(SubPage.GUIDE) },
                )
                Tile(
                    Modifier.weight(1f).fillMaxHeight(),
                    icon = state.task.icon,
                    tone = Tone.ACTIVE,
                    label = tr(R.string.home_task),
                    value = tr(state.task.title),
                    status = tr(if (state.busy) R.string.home_task_locked else R.string.home_task_change),
                    onClick = { navigator.openTab(Tab.TASKS) },
                )
            }
            PanelCard(padding = PaddingValues(0.dp)) {
                SettingRow(
                    tr(R.string.status_title),
                    icon = M7Icons.Display,
                    iconTone = if (state.displayId != null) Tone.ACTIVE else Tone.NEUTRAL,
                    summary = runSummary(state),
                    onClick = { navigator.open(SubPage.STATUS) },
                )
                if (state.busy && lastLog != null) {
                    RowDivider()
                    SettingRow(
                        tr(R.string.home_latest_log),
                        icon = M7Icons.Logs,
                        iconTone = Tone.NEUTRAL,
                        summary = lastLog,
                        summaryMaxLines = 2,
                        onClick = { navigator.openTab(Tab.LOGS) },
                    )
                }
            }
            if (!state.busy) {
                Notice(tr(R.string.home_tip_cold_start))
            }
        }
        Box(Modifier.padding(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 12.dp)) {
            val winding = state.service == ServiceState.RECOVERING ||
                state.phase == TaskPhase.STOPPING || state.phase == TaskPhase.CLEANING
            when {
                state.busy -> BigActionButton(
                    tr(
                        when {
                            state.service == ServiceState.RECOVERING -> R.string.service_recovering
                            winding -> state.phase.stopLabel
                            else -> R.string.stop
                        }
                    ),
                    actions.stop, icon = M7Icons.Stop, style = ActionStyle.STOP, enabled = !winding, loading = winding,
                )
                state.permission != PermissionState.READY -> BigActionButton(
                    tr(R.string.go_authorize), { navigator.open(SubPage.GUIDE) }, icon = M7Icons.Shield, style = ActionStyle.PLAIN,
                )
                else -> BigActionButton(tr(R.string.start_task, tr(state.task.title)), actions.start, icon = M7Icons.Play)
            }
        }
    }
}

private val TaskPhase.stopLabel: Int
    get() = if (this == TaskPhase.CLEANING) R.string.phase_cleaning else R.string.phase_stopping

@Composable
internal fun runSummary(state: TaskState): String {
    val display = state.displayId ?: return tr(
        if (state.busy) R.string.status_summary_starting else R.string.status_summary_idle
    )
    return tr(R.string.status_summary_running, display, tr(state.game.label))
}

@Composable
private fun Hero(state: TaskState) {
    val brand = LocalBrand.current
    val head = headline(state)
    Column(
        Modifier
            .fillMaxWidth()
            .clip(MaterialTheme.shapes.extraLarge)
            .background(Brush.linearGradient(listOf(brand.heroStart, brand.heroEnd))),
    ) {
        Row(Modifier.height(IntrinsicSize.Min)) {
            Column(Modifier.weight(1f).padding(start = 20.dp, top = 20.dp, bottom = 20.dp)) {
                StatusPill(tr(head.pill), head.tone, container = brand.card.copy(alpha = 0.72f))
                Spacer(Modifier.height(12.dp))
                Text(head.title, style = MaterialTheme.typography.headlineSmall)
                Spacer(Modifier.height(6.dp))
                Text(head.detail, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Image(
                painterResource(head.art), null,
                Modifier.padding(start = 4.dp, end = 12.dp, top = 16.dp).width(104.dp).fillMaxHeight(),
                alignment = Alignment.BottomCenter,
                contentScale = ContentScale.Fit,
            )
        }
        if (state.busy && state.service != ServiceState.RECOVERING) {
            PhaseBar(state.phase, Modifier.padding(start = 20.dp, end = 20.dp, bottom = 18.dp))
        }
    }
}

/** 一轮任务的四个阶段。停止请求可能发生在任何阶段，统一算作收尾。 */
@Composable
internal fun PhaseBar(phase: TaskPhase, modifier: Modifier = Modifier) {
    val current = when (phase) {
        TaskPhase.PREPARING -> 0
        TaskPhase.WAITING_FOR_GAME -> 1
        TaskPhase.RUNNING -> 2
        TaskPhase.STOPPING, TaskPhase.CLEANING -> 3
        else -> -1
    }
    val steps = listOf(R.string.step_prepare, R.string.step_game, R.string.step_task, R.string.step_cleanup)
    val scheme = MaterialTheme.colorScheme
    Row(modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        steps.forEachIndexed { index, label ->
            Column(Modifier.weight(1f)) {
                val bar = Modifier.fillMaxWidth().height(6.dp).clip(CircleShape)
                when {
                    index < current -> Box(bar.background(scheme.primary))
                    index == current -> LinearProgressIndicator(
                        bar, color = scheme.primary, trackColor = scheme.primary.copy(alpha = 0.25f)
                    )
                    else -> Box(bar.background(scheme.onSurface.copy(alpha = 0.12f)))
                }
                Spacer(Modifier.height(6.dp))
                Text(
                    tr(label),
                    style = MaterialTheme.typography.labelMedium,
                    color = if (index <= current) scheme.onSurface else scheme.onSurfaceVariant,
                    maxLines = 1,
                )
            }
        }
    }
}

@Composable
private fun Tile(
    modifier: Modifier,
    icon: ImageVector,
    tone: Tone,
    label: String,
    value: String,
    status: String,
    onClick: () -> Unit,
) {
    PanelCard(modifier, onClick, PaddingValues(14.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconBadge(icon, tone)
            Spacer(Modifier.weight(1f))
            Icon(M7Icons.ChevronRight, null, tint = MaterialTheme.colorScheme.outline)
        }
        Spacer(Modifier.height(10.dp))
        Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
        Text(
            status,
            style = MaterialTheme.typography.bodySmall,
            color = if (tone == Tone.ACTIVE) MaterialTheme.colorScheme.onSurfaceVariant else tone.colors().accent,
        )
    }
}

@Composable
private fun ErrorCard(error: ErrorInfo, code: String, actions: AppActions, navigator: Navigator) {
    val scheme = MaterialTheme.colorScheme
    PanelCard(padding = PaddingValues(start = 16.dp, end = 16.dp, top = 16.dp, bottom = 6.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(M7Icons.Error, null, Modifier.size(22.dp), tint = scheme.error)
            Spacer(Modifier.width(8.dp))
            Text(tr(error.title), Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
        }
        Spacer(Modifier.height(8.dp))
        Text(tr(error.advice), style = MaterialTheme.typography.bodyMedium)
        Spacer(Modifier.height(6.dp))
        Text(tr(R.string.error_code, code), style = MaterialTheme.typography.labelSmall, color = scheme.onSurfaceVariant)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
            when (error.fix) {
                ErrorFix.GUIDE -> TextButton({ navigator.open(SubPage.GUIDE) }) { Text(tr(R.string.open_guide)) }
                ErrorFix.APP_SETTINGS -> TextButton(actions.openAppSettings) { Text(tr(R.string.open_app_settings)) }
                else -> Unit
            }
            TextButton({ navigator.openTab(Tab.LOGS) }) { Text(tr(R.string.view_logs)) }
        }
    }
}
