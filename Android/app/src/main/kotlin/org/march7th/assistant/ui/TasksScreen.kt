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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import org.march7th.assistant.Catalog
import org.march7th.assistant.CatalogItem
import org.march7th.assistant.InstanceType
import org.march7th.assistant.R
import org.march7th.assistant.TaskConfig
import org.march7th.assistant.TaskController
import org.march7th.assistant.TaskId
import org.march7th.assistant.TaskState
import kotlin.math.roundToInt

@Composable
internal fun TasksScreen(state: TaskState, catalog: () -> Catalog, actions: AppActions) {
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
            TaskCard(task, state.task == task, enabled, state.config, catalog, actions)
        }
        Notice(tr(R.string.tasks_scope_note))
    }
}

@Composable
private fun TaskCard(
    task: TaskId, selected: Boolean, enabled: Boolean, config: TaskConfig, catalog: () -> Catalog, actions: AppActions,
) {
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
                        TaskId.ROUTINE -> {
                            GroupLabel(R.string.tasks_group_power)
                            PowerOptions(config, enabled, catalog(), actions)
                            HorizontalDivider(color = scheme.outlineVariant)
                            GroupLabel(R.string.tasks_group_rewards)
                            RewardSwitches(config, enabled, actions)
                            HorizontalDivider(color = scheme.outlineVariant)
                            GroupLabel(R.string.tasks_group_daily)
                            DailySwitches(config, enabled, actions)
                        }
                        TaskId.DAILY -> DailySwitches(config, enabled, actions)
                        TaskId.REWARDS -> {
                            RewardSwitches(config, enabled, actions)
                            DailySwitches(config, enabled, actions)
                        }
                        TaskId.POWER -> PowerOptions(config, enabled, catalog(), actions)
                    }
                }
            }
        }
    }
}

@Composable
private fun GroupLabel(title: Int) {
    Text(
        tr(title), Modifier.padding(start = 16.dp, end = 16.dp, top = 14.dp),
        style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary,
    )
}

@Composable
private fun DailySwitches(config: TaskConfig, enabled: Boolean, actions: AppActions) {
    SwitchRow(
        tr(R.string.option_synthesis), config.synthesis,
        { actions.updateConfig(config.copy(synthesis = it)) },
        summary = tr(R.string.option_synthesis_summary), enabled = enabled,
    )
    SwitchRow(
        tr(R.string.option_quest), config.collectRewards,
        { actions.updateConfig(config.copy(collectRewards = it)) },
        summary = tr(R.string.option_quest_summary), enabled = enabled,
    )
}

@Composable
private fun RewardSwitches(config: TaskConfig, enabled: Boolean, actions: AppActions) {
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
    SwitchRow(
        tr(R.string.option_message), config.message,
        { actions.updateConfig(config.copy(message = it)) },
        summary = tr(R.string.option_message_summary), enabled = enabled,
    )
}

private enum class Picker { TYPE, INSTANCE, SUPPORTS }

@Composable
private fun PowerOptions(config: TaskConfig, enabled: Boolean, catalog: Catalog, actions: AppActions) {
    val scheme = MaterialTheme.colorScheme
    var picker by rememberSaveable { mutableStateOf<Picker?>(null) }
    val instances = catalog.instances[config.instanceType].orEmpty()
    val instance = instances.firstOrNull { it.id == config.instanceName }
    Column {
        SettingRow(
            tr(R.string.option_instance_type),
            summary = tr(config.instanceType.title), enabled = enabled, onClick = { picker = Picker.TYPE },
        )
        SettingRow(
            tr(R.string.option_instance),
            summary = instance?.detail?.let { tr(R.string.option_instance_summary, instance.title, it) } ?: config.instanceName,
            enabled = enabled, onClick = { picker = Picker.INSTANCE },
        )
        // 拖动时只改本地值，松手后再写入配置。
        var dragging by remember(config.waves) { mutableFloatStateOf(config.waves.toFloat()) }
        val waves = dragging.roundToInt()
        Row(
            Modifier.padding(start = 16.dp, end = 16.dp, top = 8.dp).alpha(if (enabled) 1f else 0.6f),
            verticalAlignment = Alignment.Bottom,
        ) {
            Text(
                tr(R.string.option_waves), Modifier.weight(1f),
                style = MaterialTheme.typography.labelLarge, color = scheme.onSurfaceVariant,
            )
            Text(
                tr(R.string.option_waves_value, waves, waves * config.instanceType.cost),
                style = MaterialTheme.typography.titleMedium,
            )
        }
        Slider(
            value = dragging,
            onValueChange = { dragging = it },
            modifier = Modifier.padding(horizontal = 16.dp),
            enabled = enabled,
            valueRange = 1f..TaskController.MAX_WAVES.toFloat(),
            steps = TaskController.MAX_WAVES - 2,
            onValueChangeFinished = { actions.updateConfig(config.copy(waves = waves)) },
        )
        Text(
            tr(R.string.option_power_note),
            Modifier.padding(start = 16.dp, end = 16.dp, bottom = 8.dp).alpha(if (enabled) 1f else 0.6f),
            style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant,
        )
        SwitchRow(
            tr(R.string.option_reserve), config.reserve,
            { actions.updateConfig(config.copy(reserve = it)) },
            summary = tr(R.string.option_reserve_summary), enabled = enabled,
        )
        SwitchRow(
            tr(R.string.option_fuel), config.fuel,
            { actions.updateConfig(config.copy(fuel = it)) },
            summary = tr(R.string.option_fuel_summary), enabled = enabled,
        )
        val names = catalog.characters.associate { it.id to it.title }
        SettingRow(
            tr(R.string.option_supports),
            summary = if (config.supports.isEmpty()) {
                tr(R.string.option_supports_none)
            } else {
                config.supports.joinToString(tr(R.string.option_supports_separator)) { names[it] ?: it }
            },
            enabled = enabled, onClick = { picker = Picker.SUPPORTS },
        )
        if (config.supports.isNotEmpty()) {
            SwitchRow(
                tr(R.string.option_borrow_always), config.borrowAlways,
                { actions.updateConfig(config.copy(borrowAlways = it)) },
                summary = tr(R.string.option_borrow_always_summary), enabled = enabled,
            )
        }
    }

    when (picker.takeIf { enabled }) {
        Picker.TYPE -> ChoiceDialog(
            tr(R.string.option_instance_type),
            InstanceType.entries.map { CatalogItem(it.name, tr(it.title), tr(R.string.instance_cost, it.cost)) },
            config.instanceType.name,
            onSelect = { name ->
                val type = InstanceType.valueOf(name)
                if (type != config.instanceType) {
                    // 副本名称按类型区分，换类型时落到该类型的第一个副本。
                    val first = catalog.instances[type].orEmpty().firstOrNull()?.id ?: config.instanceName
                    actions.updateConfig(config.copy(instanceType = type, instanceName = first))
                }
                picker = null
            },
            onDismiss = { picker = null },
        )
        Picker.INSTANCE -> ChoiceDialog(
            tr(config.instanceType.title),
            instances,
            config.instanceName,
            onSelect = {
                actions.updateConfig(config.copy(instanceName = it))
                picker = null
            },
            onDismiss = { picker = null },
        )
        Picker.SUPPORTS -> MultiChoiceDialog(
            tr(R.string.option_supports_dialog),
            catalog.characters,
            config.supports,
            TaskController.MAX_SUPPORTS,
            onConfirm = {
                actions.updateConfig(config.copy(supports = it))
                picker = null
            },
            onDismiss = { picker = null },
        )
        null -> {}
    }
}
