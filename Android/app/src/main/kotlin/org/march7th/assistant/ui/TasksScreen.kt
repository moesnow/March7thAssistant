package org.march7th.assistant.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import org.march7th.assistant.Calyx
import org.march7th.assistant.R
import org.march7th.assistant.TaskConfig
import org.march7th.assistant.TaskId
import org.march7th.assistant.TaskState
import kotlin.math.roundToInt

/** 拟造花萼（金）每次挑战消耗的开拓力。 */
private const val POWER_PER_WAVE = 10

@Composable
internal fun TasksScreen(state: TaskState, actions: AppActions) {
    val enabled = !state.busy
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        ScreenTitle(tr(R.string.tasks_title), subtitle = tr(R.string.tasks_subtitle))
        if (!enabled) {
            Notice(tr(R.string.tasks_locked), tone = Tone.WARNING)
        }
        for (task in TaskId.entries) {
            TaskCard(task, state.task == task, enabled, state.config, actions)
        }
        Notice(tr(R.string.tasks_scope_note))
    }
}

@Composable
private fun TaskCard(task: TaskId, selected: Boolean, enabled: Boolean, config: TaskConfig, actions: AppActions) {
    val scheme = MaterialTheme.colorScheme
    Surface(
        Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.large,
        color = LocalBrand.current.card,
        border = if (selected) BorderStroke(2.dp, scheme.primary) else BorderStroke(1.dp, scheme.outlineVariant),
    ) {
        Column {
            Row(
                Modifier
                    .fillMaxWidth()
                    .selectable(selected = selected, enabled = enabled, role = Role.RadioButton) { actions.selectTask(task) }
                    .heightIn(min = 76.dp)
                    .padding(start = 16.dp, end = 8.dp, top = 12.dp, bottom = 12.dp)
                    .alpha(if (enabled) 1f else 0.6f),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconBadge(task.icon, if (selected) Tone.ACTIVE else Tone.NEUTRAL)
                Spacer(Modifier.width(14.dp))
                Column(Modifier.weight(1f)) {
                    Text(tr(task.title), style = MaterialTheme.typography.titleMedium)
                    Text(tr(task.summary), style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant)
                }
                RadioButton(selected, null, Modifier.padding(12.dp), enabled = enabled)
            }
            AnimatedVisibility(selected) {
                Column {
                    HorizontalDivider(color = scheme.outlineVariant)
                    when (task) {
                        TaskId.DAILY -> QuestRewardSwitch(config, enabled, actions)
                        TaskId.REWARDS -> {
                            SwitchRow(
                                tr(R.string.option_dispatch), config.dispatch,
                                { actions.updateConfig(config.copy(dispatch = it)) },
                                summary = tr(R.string.option_dispatch_summary), enabled = enabled,
                            )
                            SwitchRow(
                                tr(R.string.option_mail), config.mail,
                                { actions.updateConfig(config.copy(mail = it)) },
                                summary = tr(R.string.option_mail_summary), enabled = enabled,
                            )
                            SwitchRow(
                                tr(R.string.option_assist), config.assist,
                                { actions.updateConfig(config.copy(assist = it)) },
                                summary = tr(R.string.option_assist_summary), enabled = enabled,
                            )
                            QuestRewardSwitch(config, enabled, actions)
                        }
                        TaskId.POWER -> PowerOptions(config, enabled, actions)
                    }
                }
            }
        }
    }
}

@Composable
private fun QuestRewardSwitch(config: TaskConfig, enabled: Boolean, actions: AppActions) {
    SwitchRow(
        tr(R.string.option_quest), config.collectRewards,
        { actions.updateConfig(config.copy(collectRewards = it)) },
        summary = tr(R.string.option_quest_summary), enabled = enabled,
    )
}

@Composable
private fun PowerOptions(config: TaskConfig, enabled: Boolean, actions: AppActions) {
    val scheme = MaterialTheme.colorScheme
    Column(Modifier.padding(top = 12.dp, bottom = 16.dp).alpha(if (enabled) 1f else 0.6f)) {
        Text(
            tr(R.string.option_calyx), Modifier.padding(horizontal = 16.dp),
            style = MaterialTheme.typography.labelLarge, color = scheme.onSurfaceVariant,
        )
        for (calyx in Calyx.entries) {
            Row(
                Modifier
                    .fillMaxWidth()
                    .selectable(selected = config.calyx == calyx, enabled = enabled, role = Role.RadioButton) {
                        actions.updateConfig(config.copy(calyx = calyx))
                    }
                    .heightIn(min = 56.dp)
                    .padding(start = 4.dp, end = 16.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                RadioButton(config.calyx == calyx, null, Modifier.padding(12.dp), enabled = enabled)
                Column {
                    Text(tr(calyx.title), style = MaterialTheme.typography.bodyLarge)
                    Text(tr(calyx.reward), style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant)
                }
            }
        }
        Spacer(Modifier.heightIn(min = 8.dp))
        // 拖动时只改本地值，松手后再写入配置。
        var dragging by remember(config.waves) { mutableFloatStateOf(config.waves.toFloat()) }
        val waves = dragging.roundToInt()
        Row(Modifier.padding(horizontal = 16.dp), verticalAlignment = Alignment.Bottom) {
            Text(
                tr(R.string.option_waves), Modifier.weight(1f),
                style = MaterialTheme.typography.labelLarge, color = scheme.onSurfaceVariant,
            )
            Text(tr(R.string.option_waves_value, waves, waves * POWER_PER_WAVE), style = MaterialTheme.typography.titleMedium)
        }
        Slider(
            value = dragging,
            onValueChange = { dragging = it },
            modifier = Modifier.padding(horizontal = 16.dp),
            enabled = enabled,
            valueRange = 1f..24f,
            steps = 22,
            onValueChangeFinished = { actions.updateConfig(config.copy(waves = waves)) },
        )
        Text(
            tr(R.string.option_power_note), Modifier.padding(horizontal = 16.dp),
            style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant,
        )
    }
}
