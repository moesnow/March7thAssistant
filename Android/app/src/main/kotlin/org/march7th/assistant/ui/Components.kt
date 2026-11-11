package org.march7th.assistant.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import org.march7th.assistant.R
import org.march7th.assistant.StepResult
import org.march7th.assistant.StepStatus

internal enum class Tone { NEUTRAL, ACTIVE, SUCCESS, WARNING, ERROR }

internal class ToneColors(val container: Color, val content: Color, val accent: Color)

@Composable
@ReadOnlyComposable
internal fun Tone.colors(): ToneColors {
    val scheme = MaterialTheme.colorScheme
    val brand = LocalBrand.current
    return when (this) {
        Tone.NEUTRAL -> ToneColors(scheme.surfaceContainerHigh, scheme.onSurfaceVariant, scheme.outline)
        Tone.ACTIVE -> ToneColors(scheme.primaryContainer, scheme.onPrimaryContainer, scheme.primary)
        Tone.SUCCESS -> ToneColors(brand.successContainer, brand.onSuccessContainer, brand.success)
        Tone.WARNING -> ToneColors(brand.warningContainer, brand.onWarningContainer, brand.warning)
        Tone.ERROR -> ToneColors(scheme.errorContainer, scheme.onErrorContainer, scheme.error)
    }
}

/** 页面里的卡片：白底细边，深色下用略亮的面。 */
@Composable
internal fun PanelCard(
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    padding: PaddingValues = PaddingValues(16.dp),
    content: @Composable ColumnScope.() -> Unit,
) {
    val shape = MaterialTheme.shapes.large
    val color = LocalBrand.current.card
    val border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)
    if (onClick == null) {
        Surface(modifier.fillMaxWidth(), shape, color, border = border) { Column(Modifier.padding(padding), content = content) }
    } else {
        Surface(onClick, modifier.fillMaxWidth(), shape = shape, color = color, border = border) {
            Column(Modifier.padding(padding), content = content)
        }
    }
}

@Composable
internal fun StatusPill(text: String, tone: Tone, modifier: Modifier = Modifier, container: Color? = null) {
    val colors = tone.colors()
    Row(
        modifier.clip(CircleShape).background(container ?: colors.container).padding(horizontal = 10.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(8.dp).clip(CircleShape).background(colors.accent))
        Spacer(Modifier.width(6.dp))
        Text(text, style = MaterialTheme.typography.labelMedium, color = if (container == null) colors.content else MaterialTheme.colorScheme.onSurface)
    }
}

@Composable
internal fun SectionLabel(text: String, modifier: Modifier = Modifier) {
    Text(
        text,
        modifier.padding(start = 4.dp, top = 8.dp),
        style = MaterialTheme.typography.titleSmall,
        color = MaterialTheme.colorScheme.primary,
    )
}

@Composable
internal fun IconBadge(icon: ImageVector, tone: Tone = Tone.ACTIVE, modifier: Modifier = Modifier) {
    val colors = tone.colors()
    Box(modifier.size(40.dp).clip(CircleShape).background(colors.container), contentAlignment = Alignment.Center) {
        Icon(icon, null, Modifier.size(22.dp), tint = if (tone == Tone.NEUTRAL) colors.content else colors.accent)
    }
}

/** 设置项和状态行：左侧图标，标题、当前取值加说明，右侧可放开关、状态或箭头。 */
@Composable
internal fun SettingRow(
    title: String,
    modifier: Modifier = Modifier,
    icon: ImageVector? = null,
    iconTone: Tone = Tone.ACTIVE,
    value: String? = null,
    summary: String? = null,
    summaryMaxLines: Int = Int.MAX_VALUE,
    enabled: Boolean = true,
    onClick: (() -> Unit)? = null,
    trailing: @Composable (() -> Unit)? = null,
) {
    Row(
        modifier
            .fillMaxWidth()
            .then(if (onClick != null) Modifier.clickable(enabled, role = Role.Button, onClick = onClick) else Modifier)
            .heightIn(min = 64.dp)
            .padding(horizontal = 16.dp, vertical = 12.dp)
            .alpha(if (enabled) 1f else 0.5f),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (icon != null) {
            IconBadge(icon, iconTone)
            Spacer(Modifier.width(14.dp))
        }
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            if (value != null) {
                Text(
                    value,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.primary,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            if (summary != null) {
                Text(
                    summary,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = summaryMaxLines,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
        if (trailing != null) {
            Spacer(Modifier.width(12.dp))
            trailing()
        } else if (onClick != null) {
            Icon(M7Icons.ChevronRight, null, tint = MaterialTheme.colorScheme.outline)
        }
    }
}

/** 数字步进器：两侧加减，中间可以直接输入。输入只收数字，超出范围的值收进范围。 */
@Composable
internal fun Stepper(
    value: Int,
    range: IntRange,
    onChange: (Int) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    val scheme = MaterialTheme.colorScheme
    val focus = LocalFocusManager.current
    val digits = range.last.toString().length
    var text by remember(value) { mutableStateOf(value.toString()) }
    Row(modifier, verticalAlignment = Alignment.CenterVertically) {
        IconButton({ onChange(value - 1) }, enabled = enabled && value > range.first) {
            Icon(M7Icons.Remove, "${tr(R.string.stepper_minus)} $label")
        }
        BasicTextField(
            value = text,
            onValueChange = { input ->
                text = input.filter(Char::isDigit).take(digits)
                text.toIntOrNull()?.let { onChange(it.coerceIn(range)) }
            },
            modifier = Modifier
                .width((digits * 12 + 28).dp)
                .clip(MaterialTheme.shapes.small)
                .border(1.dp, if (enabled) scheme.outline else scheme.outlineVariant, MaterialTheme.shapes.small)
                .onFocusChanged { if (!it.isFocused) text = value.toString() }
                .semantics { contentDescription = label }
                .padding(vertical = 10.dp),
            enabled = enabled,
            singleLine = true,
            textStyle = MaterialTheme.typography.titleMedium.copy(
                color = if (enabled) scheme.onSurface else scheme.onSurfaceVariant, textAlign = TextAlign.Center,
            ),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number, imeAction = ImeAction.Done),
            keyboardActions = KeyboardActions(onDone = { focus.clearFocus() }),
            cursorBrush = SolidColor(scheme.primary),
        )
        IconButton({ onChange(value + 1) }, enabled = enabled && value < range.last) {
            Icon(M7Icons.Add, "${tr(R.string.stepper_plus)} $label")
        }
    }
}

/** 标题、说明和可选范围在左，步进器在右。 */
@Composable
internal fun StepperRow(
    title: String,
    value: Int,
    range: IntRange,
    onChange: (Int) -> Unit,
    modifier: Modifier = Modifier,
    summary: String? = null,
    enabled: Boolean = true,
) {
    Row(
        modifier.fillMaxWidth().heightIn(min = 64.dp).padding(start = 16.dp, end = 8.dp, top = 12.dp, bottom = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f).alpha(if (enabled) 1f else 0.5f)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            val hint = tr(R.string.stepper_range, range.first, range.last)
            Text(
                if (summary == null) hint else "$summary\n$hint",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Spacer(Modifier.width(8.dp))
        Stepper(value, range, onChange, title, enabled = enabled)
    }
}

/** 可折叠的设置组：标题行显示图标、名称、一行摘要和展开箭头。 */
@Composable
internal fun ExpandableGroup(
    title: String,
    summary: String,
    icon: ImageVector,
    expanded: Boolean,
    onToggle: () -> Unit,
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    PanelCard(modifier, padding = PaddingValues(0.dp)) {
        val action = tr(if (expanded) R.string.task_collapse else R.string.task_expand)
        val status = tr(if (expanded) R.string.state_expanded else R.string.state_collapsed)
        Row(
            Modifier
                .fillMaxWidth()
                .clickable(onClickLabel = action, role = Role.Button, onClick = onToggle)
                .semantics { stateDescription = status }
                .heightIn(min = 72.dp)
                .padding(horizontal = 16.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconBadge(icon)
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text(title, style = MaterialTheme.typography.titleMedium)
                Text(
                    summary, style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant,
                    maxLines = 2, overflow = TextOverflow.Ellipsis,
                )
            }
            Spacer(Modifier.width(8.dp))
            Icon(M7Icons.ExpandMore, null, Modifier.rotate(if (expanded) 180f else 0f), tint = scheme.onSurfaceVariant)
        }
        AnimatedVisibility(expanded) {
            Column {
                HorizontalDivider(color = scheme.outlineVariant)
                content()
            }
        }
    }
}

/** 一个步骤的结果：状态图标、步骤名和说明。running 表示这一轮还在进行。 */
@Composable
internal fun StepResultRow(step: StepResult, modifier: Modifier = Modifier, running: Boolean = false) {
    val scheme = MaterialTheme.colorScheme
    val brand = LocalBrand.current
    val (icon, tint) = when (step.status) {
        StepStatus.DONE -> M7Icons.Check to brand.success
        StepStatus.FAILED -> M7Icons.Close to scheme.error
        StepStatus.STOPPED -> M7Icons.Stop to brand.warning
        StepStatus.RUNNING -> M7Icons.Play to scheme.primary
        StepStatus.PENDING, StepStatus.DISABLED -> M7Icons.Remove to scheme.outline
    }
    val muted = step.status == StepStatus.PENDING || step.status == StepStatus.DISABLED
    val status = if (running && step.status == StepStatus.PENDING) R.string.step_waiting else step.status.label
    Row(modifier.fillMaxWidth().semantics(mergeDescendants = true) {}.padding(vertical = 6.dp)) {
        Icon(icon, tr(status), Modifier.padding(top = 1.dp).size(20.dp), tint = tint)
        Spacer(Modifier.width(10.dp))
        Text(
            stepName(step), Modifier.widthIn(min = 72.dp),
            style = MaterialTheme.typography.titleSmall,
            color = if (muted) scheme.onSurfaceVariant else scheme.onSurface,
        )
        Spacer(Modifier.width(10.dp))
        Text(
            stepDetail(step, running), Modifier.weight(1f),
            style = MaterialTheme.typography.bodyMedium,
            color = if (step.status == StepStatus.FAILED) scheme.error else scheme.onSurfaceVariant,
        )
    }
}

internal val StepStatus.label: Int
    get() = when (this) {
        StepStatus.PENDING -> R.string.step_pending
        StepStatus.RUNNING -> R.string.step_running
        StepStatus.DONE -> R.string.step_done
        StepStatus.FAILED -> R.string.step_failed
        StepStatus.STOPPED -> R.string.step_stopped
        StepStatus.DISABLED -> R.string.step_disabled
    }

@Composable
internal fun SwitchRow(
    title: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    modifier: Modifier = Modifier,
    icon: ImageVector? = null,
    summary: String? = null,
    enabled: Boolean = true,
) {
    Row(
        modifier
            .fillMaxWidth()
            .toggleable(value = checked, enabled = enabled, role = Role.Switch, onValueChange = onCheckedChange)
            .heightIn(min = 64.dp)
            .padding(horizontal = 16.dp, vertical = 12.dp)
            .alpha(if (enabled) 1f else 0.5f),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (icon != null) {
            IconBadge(icon)
            Spacer(Modifier.width(14.dp))
        }
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            if (summary != null) {
                Text(summary, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        Spacer(Modifier.width(12.dp))
        Switch(checked, null, enabled = enabled)
    }
}

@Composable
internal fun RowDivider() {
    HorizontalDivider(Modifier.padding(horizontal = 16.dp), color = MaterialTheme.colorScheme.outlineVariant)
}

@Composable
internal fun Notice(text: String, modifier: Modifier = Modifier, tone: Tone = Tone.NEUTRAL, icon: ImageVector = M7Icons.Info) {
    val colors = tone.colors()
    Row(
        modifier.fillMaxWidth().clip(MaterialTheme.shapes.medium).background(colors.container).padding(12.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Icon(icon, null, Modifier.padding(top = 1.dp).size(18.dp), tint = colors.accent)
        Text(text, style = MaterialTheme.typography.bodySmall, color = colors.content)
    }
}

/** 等宽分段选择，单手点按时每段都足够大。 */
@Composable
internal fun <T> Segmented(
    options: List<Pair<T, String>>,
    selected: T,
    onSelect: (T) -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    val scheme = MaterialTheme.colorScheme
    Row(
        modifier.fillMaxWidth().clip(CircleShape).background(scheme.surfaceContainerHigh).padding(4.dp)
            .alpha(if (enabled) 1f else 0.5f),
    ) {
        for ((value, label) in options) {
            val active = value == selected
            Box(
                Modifier
                    .weight(1f)
                    .clip(CircleShape)
                    .background(if (active) scheme.primary else Color.Transparent)
                    .selectable(selected = active, enabled = enabled, role = Role.RadioButton) { onSelect(value) }
                    .heightIn(min = 40.dp)
                    .padding(horizontal = 8.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    label,
                    style = MaterialTheme.typography.labelLarge,
                    color = if (active) scheme.onPrimary else scheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                    maxLines = 1,
                )
            }
        }
    }
}

internal enum class ActionStyle { START, STOP, PLAIN }

/** 首页底部的主按钮，拇指够得到的位置，够高够宽。 */
@Composable
internal fun BigActionButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    icon: ImageVector? = null,
    style: ActionStyle = ActionStyle.START,
    enabled: Boolean = true,
    loading: Boolean = false,
) {
    val scheme = MaterialTheme.colorScheme
    val brand = LocalBrand.current
    val (brush, content) = when (style) {
        ActionStyle.START -> Brush.horizontalGradient(listOf(brand.actionStart, brand.actionEnd)) to brand.onAction
        ActionStyle.STOP -> Brush.horizontalGradient(listOf(scheme.inverseSurface, scheme.inverseSurface)) to scheme.inverseOnSurface
        ActionStyle.PLAIN -> Brush.horizontalGradient(listOf(scheme.secondaryContainer, scheme.secondaryContainer)) to scheme.onSecondaryContainer
    }
    Row(
        modifier
            .fillMaxWidth()
            .height(60.dp)
            .alpha(if (enabled) 1f else 0.55f)
            .clip(CircleShape)
            .background(brush)
            .clickable(enabled, role = Role.Button, onClick = onClick)
            .padding(horizontal = 24.dp),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (loading) {
            CircularProgressIndicator(Modifier.size(20.dp), color = content, strokeWidth = 2.5.dp)
            Spacer(Modifier.width(12.dp))
        } else if (icon != null) {
            Icon(icon, null, Modifier.size(26.dp), tint = content)
            Spacer(Modifier.width(8.dp))
        }
        Text(text, style = MaterialTheme.typography.titleLarge, color = content, maxLines = 1)
    }
}

/** 二级页顶部：返回和标题。 */
@Composable
internal fun SubPageBar(title: String, onBack: () -> Unit, modifier: Modifier = Modifier) {
    Row(modifier.fillMaxWidth().height(56.dp).padding(horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(
            Modifier.size(48.dp).clip(CircleShape).clickable(role = Role.Button, onClickLabel = tr(R.string.back), onClick = onBack),
            contentAlignment = Alignment.Center,
        ) {
            Icon(M7Icons.ArrowBack, tr(R.string.back))
        }
        Text(title, Modifier.padding(start = 4.dp), style = MaterialTheme.typography.titleLarge)
    }
}

/** 一级页的大标题。 */
@Composable
internal fun ScreenTitle(title: String, modifier: Modifier = Modifier, subtitle: String? = null) {
    Column(modifier.padding(horizontal = 4.dp, vertical = 4.dp)) {
        Text(title, style = MaterialTheme.typography.headlineSmall)
        if (subtitle != null) {
            Text(subtitle, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

internal enum class StepState { DONE, CURRENT, PENDING, FAILED }

/** 竖排步骤：左侧序号和连接线，右侧标题与内容。 */
@Composable
internal fun StepItem(
    number: Int,
    title: String,
    state: StepState,
    modifier: Modifier = Modifier,
    last: Boolean = false,
    content: @Composable ColumnScope.() -> Unit = {},
) {
    val scheme = MaterialTheme.colorScheme
    val brand = LocalBrand.current
    val (fill, onFill) = when (state) {
        StepState.DONE -> brand.success to scheme.surface
        StepState.CURRENT -> scheme.primary to scheme.onPrimary
        StepState.PENDING -> scheme.surfaceContainerHighest to scheme.onSurfaceVariant
        StepState.FAILED -> scheme.error to scheme.onError
    }
    Row(modifier.fillMaxWidth().height(IntrinsicSize.Min)) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Box(Modifier.size(28.dp).clip(CircleShape).background(fill), contentAlignment = Alignment.Center) {
                when (state) {
                    StepState.DONE -> Icon(M7Icons.Check, null, Modifier.size(18.dp), tint = onFill)
                    StepState.FAILED -> Icon(M7Icons.Warning, null, Modifier.size(16.dp), tint = onFill)
                    else -> Text(number.toString(), style = MaterialTheme.typography.labelLarge, color = onFill)
                }
            }
            if (!last) {
                Box(
                    Modifier.padding(vertical = 4.dp).width(2.dp).weight(1f)
                        .background(if (state == StepState.DONE) brand.success.copy(alpha = 0.5f) else scheme.outlineVariant)
                )
            }
        }
        Spacer(Modifier.width(14.dp))
        Column(Modifier.weight(1f).padding(top = 2.dp, bottom = if (last) 0.dp else 18.dp)) {
            Text(
                title,
                style = MaterialTheme.typography.titleMedium,
                color = if (state == StepState.PENDING) scheme.onSurfaceVariant else scheme.onSurface,
            )
            content()
        }
    }
}

@Composable
internal fun BodyText(text: String, modifier: Modifier = Modifier) {
    Text(text, modifier, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
}

/** 图标加一段说明，用在提示清单里。 */
@Composable
internal fun TipRow(icon: ImageVector, text: String, modifier: Modifier = Modifier, tone: Tone = Tone.NEUTRAL) {
    Row(modifier.fillMaxWidth().padding(vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Icon(icon, null, Modifier.padding(top = 2.dp).size(20.dp), tint = if (tone == Tone.NEUTRAL) MaterialTheme.colorScheme.primary else tone.colors().accent)
        Text(text, style = MaterialTheme.typography.bodyMedium)
    }
}
