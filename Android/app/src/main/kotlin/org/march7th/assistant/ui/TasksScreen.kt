package org.march7th.assistant.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import org.march7th.assistant.Catalog
import org.march7th.assistant.CatalogItem
import org.march7th.assistant.InstanceType
import org.march7th.assistant.R
import org.march7th.assistant.StepResult
import org.march7th.assistant.StepStatus
import org.march7th.assistant.Support
import org.march7th.assistant.TaskConfig
import org.march7th.assistant.TaskId
import org.march7th.assistant.TaskState
import org.march7th.assistant.idle
import org.march7th.assistant.plannedSteps
import java.time.LocalDate
import kotlin.math.roundToInt

@Composable
internal fun TasksScreen(state: TaskState, catalog: () -> Catalog, actions: AppActions, navigator: Navigator) {
    val enabled = !state.busy
    val config = state.config
    val today = LocalDate.now().dayOfWeek.value
    // 折叠状态随页面保存，从子页面返回时保持原样。
    var powerOpen by rememberSaveable { mutableStateOf(false) }
    var rewardsOpen by rememberSaveable { mutableStateOf(false) }
    var dailyOpen by rememberSaveable { mutableStateOf(false) }
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        ScreenTitle(tr(R.string.tasks_title), subtitle = tr(R.string.tasks_subtitle))
        if (!enabled) {
            Notice(tr(R.string.tasks_locked), tone = Tone.WARNING)
        }
        SectionLabel(tr(R.string.tasks_pick))
        Column(Modifier.selectableGroup(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            for (task in TaskId.entries) {
                TaskCard(task, task == state.task, enabled, taskBrief(task, config, catalog, today)) { actions.selectTask(task) }
            }
        }
        if (plannedSteps(state.task, config, today).idle) {
            Notice(tr(R.string.tasks_idle_warning), tone = Tone.WARNING, icon = M7Icons.Warning)
        }
        Column {
            SectionLabel(tr(R.string.tasks_settings))
            Text(
                tr(R.string.tasks_settings_shared), Modifier.padding(start = 4.dp, top = 2.dp),
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        ExpandableGroup(
            tr(R.string.power), powerSummary(config, catalog()), M7Icons.Bolt, powerOpen, { powerOpen = !powerOpen },
        ) {
            PowerOptions(state, catalog(), enabled, actions, navigator)
        }
        ExpandableGroup(
            tr(R.string.rewards), rewardsSummary(config), M7Icons.Gift, rewardsOpen, { rewardsOpen = !rewardsOpen },
        ) {
            RewardOptions(config, enabled, actions)
        }
        ExpandableGroup(
            tr(R.string.daily), dailySummary(config), M7Icons.Daily, dailyOpen, { dailyOpen = !dailyOpen },
        ) {
            DailyOptions(state, enabled, actions)
        }
        Notice(tr(R.string.tasks_order_note))
        Notice(tr(R.string.tasks_scope_note))
    }
}

/** 卡片上的一行说明，以及给读屏用的同一句话。 */
private class Brief(val text: AnnotatedString, val spoken: String) {
    constructor(text: String) : this(AnnotatedString(text), text)
}

/** 整张卡片可点，语义是单选。 */
@Composable
private fun TaskCard(task: TaskId, selected: Boolean, enabled: Boolean, brief: Brief, onSelect: () -> Unit) {
    val scheme = MaterialTheme.colorScheme
    val shape = MaterialTheme.shapes.large
    Surface(
        Modifier
            .fillMaxWidth()
            .clip(shape)
            .selectable(selected = selected, enabled = enabled, role = Role.RadioButton, onClick = onSelect),
        shape = shape,
        color = LocalBrand.current.card,
        border = if (selected) BorderStroke(2.dp, scheme.primary) else BorderStroke(1.dp, scheme.outlineVariant),
    ) {
        Row(
            Modifier.heightIn(min = 76.dp).padding(start = 4.dp, end = 16.dp, top = 12.dp, bottom = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            RadioButton(selected, onClick = null, Modifier.padding(horizontal = 10.dp), enabled = enabled)
            IconBadge(task.icon, if (selected) Tone.ACTIVE else Tone.NEUTRAL)
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(tr(task.title), style = MaterialTheme.typography.titleMedium)
                    if (task == TaskId.ROUTINE) {
                        Spacer(Modifier.width(8.dp))
                        Text(
                            tr(R.string.task_recommended),
                            Modifier.clip(CircleShape).background(scheme.primaryContainer).padding(horizontal = 8.dp, vertical = 2.dp),
                            style = MaterialTheme.typography.labelSmall, color = scheme.onPrimaryContainer,
                        )
                    }
                }
                Text(
                    brief.text, Modifier.semantics { contentDescription = brief.spoken },
                    style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant,
                )
            }
        }
    }
}

/** 收起设置也能看出这一轮会做什么。 */
@Composable
private fun taskBrief(task: TaskId, config: TaskConfig, catalog: () -> Catalog, today: Int): Brief = when (task) {
    TaskId.ROUTINE -> routineBrief(plannedSteps(TaskId.ROUTINE, config, today))
    TaskId.DAILY -> Brief(
        tr(
            when {
                config.dailyEnable && config.rewardEnable && config.quest -> R.string.task_daily_both
                config.dailyEnable -> R.string.task_daily_complete_only
                config.rewardEnable && config.quest -> R.string.task_daily_collect_only
                else -> R.string.task_daily_nothing
            }
        )
    )
    TaskId.POWER -> Brief(powerBrief(config, catalog()))
}

/** 步骤链，这一轮不做的步骤置灰并划掉，读屏时读出原因。 */
@Composable
private fun routineBrief(steps: List<StepResult>): Brief {
    val muted = MaterialTheme.colorScheme.outline
    val arrow = tr(R.string.step_separator)
    val marker = "\u0000"
    val parts = tr(R.string.task_routine_brief, marker).split(marker)
    val names = steps.map { stepName(it) }
    val spoken = steps.mapIndexed { index, step ->
        when {
            step.status != StepStatus.DISABLED -> names[index]
            step.startDay != null -> tr(R.string.task_step_later, names[index], tr(R.string.step_starts_on, weekday(step.startDay)))
            else -> tr(R.string.task_step_disabled, names[index])
        }
    }
    val text = buildAnnotatedString {
        append(parts.first())
        steps.forEachIndexed { index, step ->
            if (index > 0) append(arrow)
            if (step.status == StepStatus.DISABLED) {
                withStyle(SpanStyle(color = muted, textDecoration = TextDecoration.LineThrough)) { append(names[index]) }
            } else {
                append(names[index])
            }
        }
        append(parts.getOrElse(1) { "" })
    }
    return Brief(text, tr(R.string.task_routine_brief, spoken.joinToString(tr(R.string.list_separator))))
}

@Composable
private fun powerBrief(config: TaskConfig, catalog: Catalog): String {
    val type = config.instanceType
    val name = instanceLabel(type, config.instanceName(type, catalog), catalog)
    val plan = config.powerPlan
    val main = when {
        plan.isEmpty() -> tr(R.string.task_power_default, name)
        config.planContinue -> tr(R.string.task_power_plan_then_default, planSize(plan), name)
        else -> tr(R.string.task_power_plan_only, planSize(plan))
    }
    val uses = when {
        config.reserve && config.fuel -> R.string.task_power_uses_both
        config.reserve -> R.string.task_power_uses_reserve
        config.fuel -> R.string.task_power_uses_fuel
        else -> return main
    }
    return tr(R.string.sentence_join, main, tr(uses))
}

@Composable
private fun powerSummary(config: TaskConfig, catalog: Catalog): String {
    val type = config.instanceType
    return tr(R.string.option_instance_summary, tr(type.title), instanceLabel(type, config.instanceName(type, catalog), catalog))
}

@Composable
private fun rewardsSummary(config: TaskConfig): String {
    if (!config.rewardEnable) return tr(R.string.rewards_off)
    return listOfNotNull(
        tr(R.string.option_dispatch).takeIf { config.dispatch },
        tr(R.string.option_mail).takeIf { config.mail },
        tr(R.string.option_assist).takeIf { config.assist },
        tr(R.string.option_quest).takeIf { config.quest },
        tr(R.string.option_srpass).takeIf { config.srpass },
        tr(R.string.option_message).takeIf { config.message },
    ).ifEmpty { listOf(tr(R.string.rewards_none)) }.joinToString(tr(R.string.list_separator))
}

@Composable
private fun dailySummary(config: TaskConfig): String = tr(
    when {
        config.dailyEnable && config.synthesis -> R.string.daily_group_synthesis
        config.dailyEnable -> R.string.daily_group_complete
        else -> R.string.daily_group_off
    }
)

/** 属于上一个开关的子项，缩进一格。 */
@Composable
private fun Nested(content: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.padding(start = 16.dp), content = content)
}

@Composable
private fun NoteText(text: String) {
    Text(
        text, Modifier.padding(start = 16.dp, end = 16.dp, bottom = 12.dp),
        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

private enum class Picker { TYPE, INSTANCE, SUPPORTS, ECHO_INSTANCE, ECHO_DAY, COUNTS }

private enum class Confirm { FUEL, RELIC }

@Composable
private fun PowerOptions(state: TaskState, catalog: Catalog, enabled: Boolean, actions: AppActions, navigator: Navigator) {
    val config = state.config
    val update = actions.updateConfig
    var picker by rememberSaveable { mutableStateOf<Picker?>(null) }
    var confirm by rememberSaveable { mutableStateOf<Confirm?>(null) }
    var ownerOf by rememberSaveable { mutableStateOf<String?>(null) }
    var more by rememberSaveable { mutableStateOf(false) }
    val type = config.instanceType
    val instance = catalog.instances[type].orEmpty().firstOrNull { it.id == config.instanceName(type, catalog) }
    val characters = catalog.characters.associate { it.id to it.title }

    SwitchRow(
        tr(R.string.option_power_enable), config.powerEnable, { update(config.copy(powerEnable = it)) },
        summary = tr(R.string.option_power_enable_summary), enabled = enabled,
    )
    RowDivider()
    SettingRow(
        tr(R.string.option_plan),
        value = if (config.powerPlan.isEmpty()) tr(R.string.plan_none) else planSize(config.powerPlan),
        summary = tr(R.string.option_plan_summary),
        onClick = { navigator.open(SubPage.POWER_PLAN) },
    )
    RowDivider()
    SettingRow(
        tr(R.string.option_instance_type), value = tr(type.title), summary = tr(R.string.instance_cost, type.cost),
        enabled = enabled, onClick = { picker = Picker.TYPE },
    )
    SettingRow(
        tr(R.string.option_instance), value = instance?.title ?: config.instanceName(type, catalog), summary = instance?.detail,
        enabled = enabled, onClick = { picker = Picker.INSTANCE },
    )
    NoteText(tr(R.string.option_instance_note))
    RowDivider()
    SwitchRow(
        tr(R.string.option_reserve), config.reserve, { update(config.copy(reserve = it)) },
        summary = tr(R.string.option_reserve_summary), enabled = enabled,
    )
    RowDivider()
    SwitchRow(
        tr(R.string.option_team), config.teamEnable, { update(config.copy(teamEnable = it)) },
        summary = tr(R.string.option_team_summary), enabled = enabled,
    )
    if (config.teamEnable) {
        Nested {
            StepperRow(
                tr(R.string.option_team_default), config.teamNumber, 1..TaskConfig.MAX_TEAM,
                { update(config.copy(teamNumber = it)) },
                summary = tr(R.string.option_team_default_summary), enabled = enabled,
            )
            SettingRow(
                tr(R.string.option_team_rules),
                value = if (config.teamRules.isEmpty()) tr(R.string.team_rules_none) else tr(R.string.team_rules_count, config.teamRules.size),
                onClick = { navigator.open(SubPage.TEAM_RULES) },
            )
        }
    }
    RowDivider()
    SwitchRow(
        tr(R.string.option_borrow), config.borrowEnable, { update(config.copy(borrowEnable = it)) },
        summary = tr(R.string.option_borrow_summary), enabled = enabled,
    )
    if (config.borrowEnable) {
        Nested {
            SettingRow(
                tr(R.string.option_supports),
                value = config.supports.takeIf { it.isNotEmpty() }
                    ?.joinToString(tr(R.string.list_separator)) { characters[it.key] ?: it.key },
                summary = tr(R.string.option_supports_summary, TaskConfig.MAX_SUPPORTS),
                enabled = enabled, onClick = { picker = Picker.SUPPORTS },
            )
            if (config.supports.isEmpty()) {
                Notice(
                    tr(R.string.option_supports_empty), Modifier.padding(start = 16.dp, end = 16.dp, bottom = 12.dp),
                    tone = Tone.WARNING, icon = M7Icons.Warning,
                )
            }
            for (support in config.supports) {
                SettingRow(
                    characters[support.key] ?: support.key,
                    value = if (support.owner.isEmpty()) tr(R.string.support_any_owner) else tr(R.string.support_owner, support.owner),
                    enabled = enabled, onClick = { ownerOf = support.key },
                )
            }
            SwitchRow(
                tr(R.string.option_borrow_always), config.borrowAlways, { update(config.copy(borrowAlways = it)) },
                summary = tr(R.string.option_borrow_always_summary), enabled = enabled,
            )
        }
    }
    RowDivider()
    SwitchRow(
        tr(R.string.option_echo), config.echoEnable, { update(config.copy(echoEnable = it)) },
        summary = tr(R.string.option_echo_summary), enabled = enabled,
    )
    if (config.echoEnable) {
        val echo = catalog.instances[InstanceType.ECHO].orEmpty()
            .firstOrNull { it.id == config.instanceName(InstanceType.ECHO, catalog) }
        Nested {
            SettingRow(
                tr(R.string.option_echo_instance), value = echo?.title ?: config.instanceName(InstanceType.ECHO, catalog),
                summary = echo?.detail, enabled = enabled, onClick = { picker = Picker.ECHO_INSTANCE },
            )
            SettingRow(
                tr(R.string.option_echo_day), value = weekday(config.echoStartDay), summary = tr(R.string.option_echo_day_summary),
                enabled = enabled, onClick = { picker = Picker.ECHO_DAY },
            )
            SettingRow(tr(R.string.option_echo_done), value = recordTime(state.lastEchoDone))
        }
    }
    RowDivider()
    MoreToggle(more) { more = !more }
    AnimatedVisibility(more) {
        Column {
            SwitchRow(
                tr(R.string.option_fuel), config.fuel,
                { if (it) confirm = Confirm.FUEL else update(config.copy(fuel = false)) },
                summary = tr(R.string.option_fuel_summary), enabled = enabled,
            )
            SwitchRow(
                tr(R.string.option_teleport), config.teleportFirst, { update(config.copy(teleportFirst = it)) },
                summary = tr(R.string.option_teleport_summary), enabled = enabled,
            )
            SwitchRow(
                tr(R.string.option_relic_cleanup), config.relicCleanup,
                { if (it) confirm = Confirm.RELIC else update(config.copy(relicCleanup = false)) },
                summary = tr(R.string.option_relic_cleanup_summary), enabled = enabled,
            )
            SettingRow(
                tr(R.string.option_challenge_counts), summary = tr(R.string.option_challenge_counts_summary),
                enabled = enabled, onClick = { picker = Picker.COUNTS },
            )
            if (config.borrowEnable) {
                StepperRow(
                    tr(R.string.option_scroll), config.borrowScrollTimes, 1..TaskConfig.MAX_SCROLL_TIMES,
                    { update(config.copy(borrowScrollTimes = it)) },
                    summary = tr(R.string.option_scroll_summary), enabled = enabled,
                )
            }
            SwitchRow(
                tr(R.string.option_auto_battle), config.autoBattle, { update(config.copy(autoBattle = it)) },
                summary = tr(R.string.option_auto_battle_summary), enabled = enabled,
            )
        }
    }

    fun close() {
        picker = null
    }
    when (picker.takeIf { enabled }) {
        Picker.TYPE -> ChoiceDialog(
            tr(R.string.option_instance_type),
            InstanceType.defaults.map { CatalogItem(it.name, tr(it.title), tr(R.string.instance_cost, it.cost)) },
            type.name,
            onSelect = {
                // 每种类型各记一个副本，换回来时还是上次的选择。
                update(config.copy(instanceType = InstanceType.valueOf(it)))
                close()
            },
            onDismiss = ::close,
        )
        Picker.INSTANCE -> InstancePicker(type, config, catalog, update, ::close)
        Picker.ECHO_INSTANCE -> InstancePicker(InstanceType.ECHO, config, catalog, update, ::close)
        Picker.SUPPORTS -> MultiChoiceDialog(
            tr(R.string.option_supports_dialog),
            catalog.characters,
            config.supports.map { it.key },
            TaskConfig.MAX_SUPPORTS,
            onConfirm = { keys ->
                // 保留已经填好的好友名称。
                update(config.copy(supports = keys.map { key -> config.supports.firstOrNull { it.key == key } ?: Support(key) }))
                close()
            },
            onDismiss = ::close,
        )
        Picker.ECHO_DAY -> ChoiceDialog(
            tr(R.string.option_echo_day),
            (1..7).map { CatalogItem(it.toString(), weekday(it)) },
            config.echoStartDay.toString(),
            onSelect = {
                update(config.copy(echoStartDay = it.toInt()))
                close()
            },
            onDismiss = ::close,
        )
        Picker.COUNTS -> ChallengeCountsDialog(config, update, ::close)
        null -> {}
    }
    ownerOf?.takeIf { enabled }?.let { key ->
        val support = config.supports.firstOrNull { it.key == key }
        if (support != null) {
            TextDialog(
                tr(R.string.support_owner_title, characters[key] ?: key),
                support.owner,
                tr(R.string.support_owner_label),
                tr(R.string.support_owner_hint),
                onConfirm = { owner ->
                    update(config.copy(supports = config.supports.map { if (it.key == key) it.copy(owner = owner) else it }))
                    ownerOf = null
                },
                onDismiss = { ownerOf = null },
            )
        }
    }
    when (confirm.takeIf { enabled }) {
        Confirm.FUEL -> ConfirmDialog(
            tr(R.string.fuel_confirm_title), tr(R.string.fuel_confirm_body),
            onConfirm = {
                update(config.copy(fuel = true))
                confirm = null
            },
            onDismiss = { confirm = null },
        )
        Confirm.RELIC -> ConfirmDialog(
            tr(R.string.relic_confirm_title), tr(R.string.relic_confirm_body),
            onConfirm = {
                update(config.copy(relicCleanup = true))
                confirm = null
            },
            onDismiss = { confirm = null },
        )
        null -> {}
    }
}

/** 选某个类型的副本，选中的名称记在该类型下。 */
@Composable
internal fun InstancePicker(
    type: InstanceType,
    config: TaskConfig,
    catalog: Catalog,
    update: (TaskConfig) -> Unit,
    onDismiss: () -> Unit,
) {
    ChoiceDialog(
        tr(type.title),
        catalog.instances[type].orEmpty(),
        config.instanceName(type, catalog),
        onSelect = {
            update(config.copy(instanceNames = config.instanceNames + (type to it)))
            onDismiss()
        },
        onDismiss = onDismiss,
    )
}

@Composable
private fun MoreToggle(expanded: Boolean, onToggle: () -> Unit) {
    val scheme = MaterialTheme.colorScheme
    val action = tr(if (expanded) R.string.task_collapse else R.string.task_expand)
    val status = tr(if (expanded) R.string.state_expanded else R.string.state_collapsed)
    Row(
        Modifier
            .fillMaxWidth()
            .clickable(onClickLabel = action, role = Role.Button, onClick = onToggle)
            .semantics { stateDescription = status }
            .heightIn(min = 56.dp)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(tr(R.string.option_more), Modifier.weight(1f), style = MaterialTheme.typography.titleMedium, color = scheme.primary)
        Icon(M7Icons.ExpandMore, null, Modifier.rotate(if (expanded) 180f else 0f), tint = scheme.primary)
    }
}

/** 每种副本一个滑块，松手即保存。 */
@Composable
private fun ChallengeCountsDialog(config: TaskConfig, update: (TaskConfig) -> Unit, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        confirmButton = { TextButton(onClick = onDismiss) { Text(tr(R.string.done)) } },
        title = { Text(tr(R.string.option_challenge_counts)) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                Text(
                    tr(R.string.option_challenge_counts_summary),
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                for (type in InstanceType.entries) {
                    val count = config.challengeCount(type)
                    var dragging by remember(count) { mutableFloatStateOf(count.toFloat()) }
                    val shown = dragging.roundToInt()
                    Row(Modifier.padding(top = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text(tr(type.title), Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
                        Text(tr(R.string.challenge_count_value, shown), style = MaterialTheme.typography.titleSmall)
                    }
                    Slider(
                        value = dragging,
                        onValueChange = { dragging = it },
                        valueRange = 1f..type.maxBatch.toFloat(),
                        steps = (type.maxBatch - 2).coerceAtLeast(0),
                        onValueChangeFinished = {
                            update(config.copy(challengeCounts = config.challengeCounts + (type to shown)))
                        },
                    )
                }
            }
        },
    )
}

@Composable
private fun RewardOptions(config: TaskConfig, enabled: Boolean, actions: AppActions) {
    val update = actions.updateConfig
    SwitchRow(
        tr(R.string.option_reward_enable), config.rewardEnable, { update(config.copy(rewardEnable = it)) },
        summary = tr(R.string.option_reward_enable_summary), enabled = enabled,
    )
    RowDivider()
    // 总开关关闭时子项置灰，保留各自的选择。
    val items = enabled && config.rewardEnable
    SwitchRow(
        tr(R.string.option_dispatch), config.dispatch, { update(config.copy(dispatch = it)) },
        summary = tr(R.string.option_dispatch_summary), enabled = items,
    )
    SwitchRow(
        tr(R.string.option_mail), config.mail, { update(config.copy(mail = it)) },
        summary = tr(R.string.option_mail_summary), enabled = items,
    )
    SwitchRow(
        tr(R.string.option_assist), config.assist, { update(config.copy(assist = it)) },
        summary = tr(R.string.option_assist_summary), enabled = items,
    )
    SwitchRow(
        tr(R.string.option_quest), config.quest, { update(config.copy(quest = it)) },
        summary = tr(R.string.option_quest_summary), enabled = items,
    )
    SwitchRow(
        tr(R.string.option_srpass), config.srpass, { update(config.copy(srpass = it)) },
        summary = tr(R.string.option_srpass_summary), enabled = items,
    )
    SwitchRow(
        tr(R.string.option_message), config.message, { update(config.copy(message = it)) },
        summary = tr(R.string.option_message_summary), enabled = items,
    )
}

@Composable
private fun DailyOptions(state: TaskState, enabled: Boolean, actions: AppActions) {
    val config = state.config
    val update = actions.updateConfig
    SwitchRow(
        tr(R.string.option_daily_enable), config.dailyEnable, { update(config.copy(dailyEnable = it)) },
        summary = tr(R.string.option_daily_enable_summary), enabled = enabled,
    )
    RowDivider()
    SwitchRow(
        tr(R.string.option_synthesis), config.synthesis, { update(config.copy(synthesis = it)) },
        summary = tr(R.string.option_synthesis_summary), enabled = enabled && config.dailyEnable,
    )
    RowDivider()
    SettingRow(tr(R.string.option_daily_done), value = recordTime(state.lastDailyDone))
}
