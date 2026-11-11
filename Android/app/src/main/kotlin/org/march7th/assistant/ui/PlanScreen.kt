package org.march7th.assistant.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import org.march7th.assistant.Catalog
import org.march7th.assistant.CatalogItem
import org.march7th.assistant.InstanceType
import org.march7th.assistant.PlanItem
import org.march7th.assistant.R
import org.march7th.assistant.TaskConfig
import org.march7th.assistant.TaskState
import org.march7th.assistant.TeamRule

/** 新增计划项时 editing 取这个值，其余取要修改的下标。 */
private const val NEW_ITEM = -1

@Composable
internal fun PowerPlanScreen(state: TaskState, catalog: () -> Catalog, actions: AppActions, navigator: Navigator) {
    val config = state.config
    val enabled = !state.busy
    val plan = config.powerPlan
    var editing by rememberSaveable { mutableStateOf<Int?>(null) }
    fun save(items: List<PlanItem>) = actions.updateConfig(config.copy(powerPlan = items))

    Column(Modifier.fillMaxSize()) {
        SubPageBar(tr(R.string.option_plan), navigator.back)
        Column(
            Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(start = 16.dp, end = 16.dp, bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (!enabled) {
                Notice(tr(R.string.tasks_locked), tone = Tone.WARNING)
            }
            BodyText(tr(R.string.plan_intro))
            PanelCard(padding = PaddingValues(0.dp)) {
                if (plan.isEmpty()) {
                    BodyText(tr(R.string.plan_empty), Modifier.padding(16.dp))
                }
                plan.forEachIndexed { index, item ->
                    if (index > 0) RowDivider()
                    PlanRow(
                        index, item, catalog(), enabled,
                        onEdit = { editing = index },
                        onMoveUp = { save(plan.toMutableList().apply { add(index - 1, removeAt(index)) }) },
                        onDelete = { save(plan.filterIndexed { position, _ -> position != index }) },
                    )
                }
                RowDivider()
                val full = plan.size >= TaskConfig.MAX_PLAN_ITEMS
                Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                    TextButton({ editing = NEW_ITEM }, Modifier.heightIn(min = 48.dp), enabled = enabled && !full) {
                        Icon(M7Icons.Add, null, Modifier.size(18.dp))
                        Spacer(Modifier.width(6.dp))
                        Text(tr(R.string.plan_add))
                    }
                    Spacer(Modifier.weight(1f))
                    Text(
                        tr(R.string.plan_limit, TaskConfig.MAX_PLAN_ITEMS), Modifier.padding(end = 8.dp),
                        style = MaterialTheme.typography.bodySmall,
                        color = if (full) LocalBrand.current.warning else MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            val priced = plan.filter { it.type.fixedCost != null }
            if (priced.isNotEmpty()) {
                val total = priced.sumOf { it.type.fixedCost!! * it.count }
                Text(
                    tr(if (priced.size < plan.size) R.string.plan_total_partial else R.string.plan_total, total),
                    Modifier.padding(horizontal = 4.dp), style = MaterialTheme.typography.titleSmall,
                )
            }
            PanelCard(padding = PaddingValues(0.dp)) {
                SwitchRow(
                    tr(R.string.plan_keep), config.planKeep, { actions.updateConfig(config.copy(planKeep = it)) },
                    summary = tr(R.string.plan_keep_summary), enabled = enabled,
                )
                RowDivider()
                SwitchRow(
                    tr(R.string.plan_continue), config.planContinue, { actions.updateConfig(config.copy(planContinue = it)) },
                    summary = tr(R.string.plan_continue_summary), enabled = enabled,
                )
            }
        }
    }

    editing?.takeIf { enabled }?.let { index ->
        PlanItemDialog(
            plan.getOrNull(index), config, catalog(),
            onConfirm = { item ->
                save(if (index == NEW_ITEM) plan + item else plan.mapIndexed { position, old -> if (position == index) item else old })
                editing = null
            },
            onDismiss = { editing = null },
        )
    }
}

@Composable
private fun PlanRow(
    index: Int,
    item: PlanItem,
    catalog: Catalog,
    enabled: Boolean,
    onEdit: () -> Unit,
    onMoveUp: () -> Unit,
    onDelete: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    Row(
        Modifier
            .fillMaxWidth()
            .clickable(enabled, onClickLabel = tr(R.string.plan_edit), role = Role.Button, onClick = onEdit)
            .heightIn(min = 64.dp)
            .padding(start = 16.dp, end = 4.dp, top = 8.dp, bottom = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(28.dp).clip(CircleShape).background(scheme.primaryContainer), contentAlignment = Alignment.Center) {
            Text((index + 1).toString(), style = MaterialTheme.typography.labelLarge, color = scheme.onPrimaryContainer)
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(instanceLabel(item.type, item.name, catalog), style = MaterialTheme.typography.titleMedium)
            val parts = listOfNotNull(
                tr(item.type.title),
                tr(R.string.plan_count, item.count),
                item.type.fixedCost?.let { tr(R.string.plan_cost, it * item.count) },
            )
            Text(
                parts.joinToString(" · "),
                style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant,
            )
        }
        IconButton(onMoveUp, enabled = enabled && index > 0) {
            Icon(M7Icons.ArrowUp, tr(R.string.plan_move_up))
        }
        IconButton(onDelete, enabled = enabled) {
            Icon(M7Icons.Delete, tr(R.string.plan_delete))
        }
    }
}

private enum class PlanPicker { TYPE, NAME }

/** 副本类型（六种）→ 副本名称 → 次数，确定后写回计划。 */
@Composable
private fun PlanItemDialog(
    initial: PlanItem?,
    config: TaskConfig,
    catalog: Catalog,
    onConfirm: (PlanItem) -> Unit,
    onDismiss: () -> Unit,
) {
    var type by rememberSaveable { mutableStateOf(initial?.type ?: InstanceType.GOLDEN_CALYX) }
    var name by rememberSaveable { mutableStateOf(initial?.name ?: config.instanceName(type, catalog)) }
    var count by rememberSaveable { mutableIntStateOf(initial?.count ?: 1) }
    var picker by rememberSaveable { mutableStateOf<PlanPicker?>(null) }
    val item = catalog.instances[type].orEmpty().firstOrNull { it.id == name }

    AlertDialog(
        onDismissRequest = onDismiss,
        confirmButton = {
            TextButton({ onConfirm(PlanItem(type, name, count)) }, enabled = name.isNotBlank()) { Text(tr(R.string.confirm)) }
        },
        dismissButton = { TextButton(onDismiss) { Text(tr(R.string.cancel)) } },
        title = { Text(tr(if (initial == null) R.string.plan_add else R.string.plan_edit)) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                SettingRow(
                    tr(R.string.option_instance_type), value = tr(type.title),
                    summary = tr(R.string.instance_cost, type.cost), onClick = { picker = PlanPicker.TYPE },
                )
                SettingRow(
                    tr(R.string.option_instance), value = item?.title ?: name, summary = item?.detail,
                    onClick = { picker = PlanPicker.NAME },
                )
                StepperRow(tr(R.string.plan_times), count, 1..TaskConfig.MAX_PLAN_COUNT, { count = it })
                if (type == InstanceType.ECHO) {
                    Notice(tr(R.string.plan_echo_note), Modifier.padding(top = 4.dp), tone = Tone.WARNING, icon = M7Icons.Warning)
                }
            }
        },
    )

    when (picker) {
        PlanPicker.TYPE -> ChoiceDialog(
            tr(R.string.option_instance_type),
            InstanceType.entries.map { CatalogItem(it.name, tr(it.title), tr(R.string.instance_cost, it.cost)) },
            type.name,
            onSelect = {
                val chosen = InstanceType.valueOf(it)
                if (chosen != type) {
                    type = chosen
                    name = config.instanceName(chosen, catalog)
                }
                picker = null
            },
            onDismiss = { picker = null },
        )
        PlanPicker.NAME -> ChoiceDialog(
            tr(type.title), catalog.instances[type].orEmpty(), name,
            onSelect = {
                name = it
                picker = null
            },
            onDismiss = { picker = null },
        )
        null -> {}
    }
}

private enum class RuleStep { TYPE, NAME, TEAM }

@Composable
internal fun TeamRulesScreen(state: TaskState, catalog: () -> Catalog, actions: AppActions, navigator: Navigator) {
    val config = state.config
    val enabled = !state.busy
    val rules = config.teamRules
    var step by rememberSaveable { mutableStateOf<RuleStep?>(null) }
    var newType by rememberSaveable { mutableStateOf<InstanceType?>(null) }
    var newName by rememberSaveable { mutableStateOf<String?>(null) }
    fun save(items: List<TeamRule>) = actions.updateConfig(config.copy(teamRules = items))
    fun reset() {
        step = null
        newType = null
        newName = null
    }
    // Python 只按名称匹配，副本类型从清单里反查，只用于显示。
    fun typeOf(name: String) = catalog().instances.entries.firstOrNull { (_, items) -> items.any { it.id == name } }?.key

    Column(Modifier.fillMaxSize()) {
        SubPageBar(tr(R.string.option_team_rules), navigator.back)
        Column(
            Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(start = 16.dp, end = 16.dp, bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (!enabled) {
                Notice(tr(R.string.tasks_locked), tone = Tone.WARNING)
            }
            BodyText(tr(R.string.team_rules_intro))
            PanelCard(padding = PaddingValues(0.dp)) {
                if (rules.isEmpty()) {
                    BodyText(tr(R.string.team_rules_empty), Modifier.padding(16.dp))
                }
                rules.forEachIndexed { index, rule ->
                    if (index > 0) RowDivider()
                    val type = typeOf(rule.instance)
                    val label = type?.let { instanceLabel(it, rule.instance, catalog()) } ?: rule.instance
                    Row(
                        Modifier.fillMaxWidth().heightIn(min = 64.dp).padding(start = 16.dp, end = 4.dp, top = 8.dp, bottom = 8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(Modifier.weight(1f)) {
                            Text(label, style = MaterialTheme.typography.titleMedium)
                            if (type != null) {
                                Text(
                                    tr(type.title), style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                        Stepper(
                            rule.team, 1..TaskConfig.MAX_TEAM,
                            { team -> save(rules.map { if (it.instance == rule.instance) it.copy(team = team) else it }) },
                            label, enabled = enabled,
                        )
                        IconButton({ save(rules - rule) }, enabled = enabled) {
                            Icon(M7Icons.Delete, tr(R.string.plan_delete))
                        }
                    }
                }
                RowDivider()
                TextButton(
                    { step = RuleStep.TYPE },
                    Modifier.padding(horizontal = 8.dp, vertical = 4.dp).heightIn(min = 48.dp),
                    enabled = enabled,
                ) {
                    Icon(M7Icons.Add, null, Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text(tr(R.string.team_rules_add))
                }
            }
        }
    }

    // 先选副本，再选队伍。已经指定过的副本不再列出。
    when (step.takeIf { enabled }) {
        RuleStep.TYPE -> ChoiceDialog(
            tr(R.string.team_rules_pick_type),
            InstanceType.entries.map { CatalogItem(it.name, tr(it.title)) },
            null,
            onSelect = {
                newType = InstanceType.valueOf(it)
                step = RuleStep.NAME
            },
            onDismiss = ::reset,
        )
        RuleStep.NAME -> newType?.let { type ->
            ChoiceDialog(
                tr(type.title),
                catalog().instances[type].orEmpty().filter { item -> rules.none { it.instance == item.id } },
                null,
                onSelect = {
                    newName = it
                    step = RuleStep.TEAM
                },
                onDismiss = ::reset,
            )
        }
        RuleStep.TEAM -> newName?.let { name ->
            ChoiceDialog(
                tr(R.string.team_rules_pick_team),
                (1..TaskConfig.MAX_TEAM).map { CatalogItem(it.toString(), tr(R.string.team_number, it)) },
                config.teamNumber.toString(),
                onSelect = {
                    save(rules + TeamRule(name, it.toInt()))
                    reset()
                },
                onDismiss = ::reset,
                searchable = false,
            )
        }
        null -> {}
    }
}
