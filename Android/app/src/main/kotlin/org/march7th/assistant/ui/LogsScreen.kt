package org.march7th.assistant.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import org.march7th.assistant.R
import org.march7th.assistant.TaskState

internal enum class LogLevel { INFO, WARNING, ERROR }

internal class LogEntry(val time: String?, val level: LogLevel, val message: String, val heading: Boolean = false)

// Python 任务日志的格式是「时:分:秒 | 级别 | 内容」，应用自己写的行没有前缀。
private val LINE = Regex("""^(\d{2}:\d{2}:\d{2}) \| (\w+) \| (.*)$""", RegexOption.DOT_MATCHES_ALL)
private val HEADING = Regex("""^=+ (.+?) =+$""")
private val TRACEBACK = Regex("""^(\s|Traceback |[A-Za-z_][\w.]*(Error|Exception|Exit|Interrupt|Warning)\b).*""", RegexOption.DOT_MATCHES_ALL)

internal fun parseLog(line: String): LogEntry {
    val match = LINE.find(line) ?: return LogEntry(null, LogLevel.INFO, line)
    val (time, name, text) = match.destructured
    val level = when (name) {
        "WARNING" -> LogLevel.WARNING
        "ERROR", "CRITICAL" -> LogLevel.ERROR
        else -> LogLevel.INFO
    }
    val heading = HEADING.find(text)
    return if (heading != null) LogEntry(time, level, heading.groupValues[1], true) else LogEntry(time, level, text)
}

/** 应用重启后日志按行读回，报错堆栈会被拆开，这里把它们并回所属的那一条。 */
internal fun parseLogs(lines: List<String>): List<LogEntry> {
    val entries = ArrayList<LogEntry>(lines.size)
    for (line in lines) {
        val entry = parseLog(line)
        val previous = entries.lastOrNull()
        if (entry.time == null && previous != null && previous.time != null &&
            previous.level != LogLevel.INFO && TRACEBACK.matches(line)
        ) {
            entries[entries.lastIndex] = LogEntry(previous.time, previous.level, previous.message + "\n" + line)
        } else {
            entries += entry
        }
    }
    return entries
}

private enum class LogsSection { LOG, HELP }

@Composable
internal fun LogsScreen(state: TaskState, logs: List<String>, actions: AppActions) {
    var section by rememberSaveable { mutableStateOf(LogsSection.LOG) }
    Column(Modifier.fillMaxSize().padding(start = 16.dp, end = 16.dp, top = 12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            ScreenTitle(tr(R.string.logs_title), Modifier.weight(1f))
            OutlinedButton(actions.exportLog, Modifier.heightIn(min = 44.dp), enabled = logs.isNotEmpty()) {
                Icon(M7Icons.Download, null, Modifier.size(18.dp))
                Spacer(Modifier.width(6.dp))
                Text(tr(R.string.export_log))
            }
        }
        Spacer(Modifier.height(10.dp))
        Segmented(
            listOf(LogsSection.LOG to tr(R.string.logs_tab_log), LogsSection.HELP to tr(R.string.logs_tab_help)),
            section, { section = it },
        )
        Spacer(Modifier.height(12.dp))
        when (section) {
            LogsSection.LOG -> LogList(state, logs) { section = LogsSection.HELP }
            LogsSection.HELP -> HelpList(state.errorCode)
        }
    }
}

@Composable
private fun LogList(state: TaskState, logs: List<String>, onHelp: () -> Unit) {
    val scheme = MaterialTheme.colorScheme
    val entries = remember(logs) { parseLogs(logs) }
    var level by rememberSaveable { mutableStateOf<LogLevel?>(null) }
    var query by rememberSaveable { mutableStateOf("") }
    val shown = remember(entries, level, query) {
        entries.filter { (level == null || it.level == level) && (query.isBlank() || it.message.contains(query.trim(), ignoreCase = true)) }
    }
    val error = errorInfo(state.errorCode).takeUnless { state.busy }

    Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        if (error != null) {
            // 日志页把空间留给日志，处理步骤放在「常见问题」里。
            Row(
                Modifier.fillMaxWidth().clip(MaterialTheme.shapes.medium).background(scheme.errorContainer)
                    .clickable(role = Role.Button, onClick = onHelp).heightIn(min = 48.dp).padding(start = 14.dp, end = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(M7Icons.Error, null, Modifier.size(20.dp), tint = scheme.error)
                Spacer(Modifier.width(10.dp))
                Text(
                    tr(error.title), Modifier.weight(1f),
                    style = MaterialTheme.typography.titleSmall, color = scheme.onErrorContainer,
                )
                Text(tr(R.string.logs_see_fix), style = MaterialTheme.typography.labelLarge, color = scheme.error)
                Icon(M7Icons.ChevronRight, null, tint = scheme.error)
            }
        }
        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            LevelChip(tr(R.string.logs_filter_all), entries.size, level == null, Tone.ACTIVE) { level = null }
            LevelChip(tr(R.string.logs_filter_info), entries.count { it.level == LogLevel.INFO }, level == LogLevel.INFO, Tone.ACTIVE) {
                level = LogLevel.INFO
            }
            LevelChip(tr(R.string.logs_filter_warning), entries.count { it.level == LogLevel.WARNING }, level == LogLevel.WARNING, Tone.WARNING) {
                level = LogLevel.WARNING
            }
            LevelChip(tr(R.string.logs_filter_error), entries.count { it.level == LogLevel.ERROR }, level == LogLevel.ERROR, Tone.ERROR) {
                level = LogLevel.ERROR
            }
        }
        SearchField(query, { query = it })

        Surface(
            Modifier.fillMaxWidth().weight(1f).padding(bottom = 12.dp),
            shape = MaterialTheme.shapes.large,
            color = LocalBrand.current.card,
            border = BorderStroke(1.dp, scheme.outlineVariant),
        ) {
            if (shown.isEmpty()) {
                Column(
                    Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center,
                ) {
                    Image(painterResource(R.drawable.chibi_ok), null, Modifier.width(150.dp))
                    Spacer(Modifier.height(12.dp))
                    Text(
                        tr(if (entries.isEmpty()) R.string.logs_empty else R.string.logs_no_match),
                        style = MaterialTheme.typography.titleMedium, textAlign = TextAlign.Center,
                    )
                    BodyText(tr(if (entries.isEmpty()) R.string.logs_empty_detail else R.string.logs_no_match_detail))
                }
            } else {
                LogLines(shown, logs)
            }
        }
    }
}

@Composable
private fun LogLines(shown: List<LogEntry>, source: List<String>) {
    val scheme = MaterialTheme.colorScheme
    val list = rememberLazyListState()
    val scope = rememberCoroutineScope()
    val expanded = remember { mutableStateMapOf<LogEntry, Boolean>() }
    // 停在底部时跟随新日志，用户往上翻看时不打扰。
    var follow by remember { mutableStateOf(true) }
    LaunchedEffect(list) {
        var scrolled = false
        snapshotFlow { list.isScrollInProgress }.collect { scrolling ->
            if (scrolling) scrolled = true else if (scrolled) follow = !list.canScrollForward
        }
    }
    LaunchedEffect(source, shown.size) {
        if (follow && shown.isNotEmpty()) list.scrollToItem(shown.lastIndex)
    }
    Box(Modifier.fillMaxSize()) {
        LazyColumn(Modifier.fillMaxSize(), list, contentPadding = PaddingValues(vertical = 8.dp)) {
            items(shown.size) { index ->
                val entry = shown[index]
                if (entry.heading) {
                    Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp)) {
                        HorizontalDivider(color = scheme.outlineVariant)
                        Text(
                            entry.message, Modifier.padding(top = 8.dp),
                            style = MaterialTheme.typography.titleSmall, color = scheme.primary,
                        )
                    }
                } else {
                    val open = expanded[entry] == true
                    val tint = when (entry.level) {
                        LogLevel.INFO -> scheme.onSurface
                        LogLevel.WARNING -> LocalBrand.current.warning
                        LogLevel.ERROR -> scheme.error
                    }
                    Row(
                        Modifier.fillMaxWidth().clickable { expanded[entry] = !open }.padding(horizontal = 12.dp, vertical = 5.dp),
                    ) {
                        Text(
                            entry.time ?: tr(R.string.logs_app_line),
                            Modifier.width(62.dp),
                            style = LogStyle, fontFamily = FontFamily.Monospace,
                            color = if (entry.level == LogLevel.INFO) scheme.onSurfaceVariant else tint,
                        )
                        Text(
                            entry.message, Modifier.weight(1f),
                            style = LogStyle, color = tint,
                            fontWeight = if (entry.level == LogLevel.INFO) FontWeight.Normal else FontWeight.Medium,
                            maxLines = if (open) Int.MAX_VALUE else 4,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
            }
            item {
                Text(
                    tr(R.string.logs_footer),
                    Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp),
                    style = MaterialTheme.typography.labelSmall, color = scheme.onSurfaceVariant, textAlign = TextAlign.Center,
                )
            }
        }
        if (!follow) {
            Box(
                Modifier.align(Alignment.BottomEnd).padding(12.dp).size(48.dp).clip(CircleShape).background(scheme.primary)
                    .clickable(role = Role.Button, onClickLabel = tr(R.string.logs_to_bottom)) {
                        follow = true
                        scope.launch { list.scrollToItem(shown.size) }
                    },
                contentAlignment = Alignment.Center,
            ) {
                Icon(M7Icons.ArrowDown, tr(R.string.logs_to_bottom), tint = scheme.onPrimary)
            }
        }
    }
}

@Composable
private fun LevelChip(label: String, count: Int, selected: Boolean, tone: Tone, onClick: () -> Unit) {
    val scheme = MaterialTheme.colorScheme
    val colors = tone.colors()
    Row(
        Modifier
            .clip(CircleShape)
            .background(if (selected) colors.container else scheme.surfaceContainerHigh)
            .selectable(selected = selected, role = Role.RadioButton, onClick = onClick)
            .heightIn(min = 40.dp)
            .padding(horizontal = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            label, style = MaterialTheme.typography.labelLarge,
            color = if (selected) colors.content else scheme.onSurfaceVariant,
        )
        Spacer(Modifier.width(6.dp))
        Text(
            count.toString(), style = MaterialTheme.typography.labelMedium,
            color = if (selected) colors.accent else scheme.outline,
        )
    }
}

@Composable
private fun SearchField(value: String, onChange: (String) -> Unit) {
    val scheme = MaterialTheme.colorScheme
    BasicTextField(
        value, onChange,
        Modifier.fillMaxWidth().clip(CircleShape).background(scheme.surfaceContainerHigh).heightIn(min = 44.dp),
        textStyle = MaterialTheme.typography.bodyMedium.copy(color = scheme.onSurface),
        singleLine = true,
        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
        cursorBrush = SolidColor(scheme.primary),
        decorationBox = { field ->
            Row(Modifier.padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.weight(1f)) {
                    if (value.isEmpty()) {
                        Text(tr(R.string.logs_search), style = MaterialTheme.typography.bodyMedium, color = scheme.outline)
                    }
                    field()
                }
                if (value.isNotEmpty()) {
                    Text(
                        tr(R.string.logs_search_clear),
                        Modifier.clip(CircleShape).clickable(role = Role.Button) { onChange("") }.padding(horizontal = 8.dp, vertical = 6.dp),
                        style = MaterialTheme.typography.labelLarge, color = scheme.primary,
                    )
                }
            }
        },
    )
}

@Composable
private fun HelpList(current: String?) {
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(bottom = 16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        BodyText(tr(R.string.help_intro), Modifier.padding(horizontal = 4.dp))
        // 两个错误码共用一条说明时只列一次。
        val codes = remember(current) {
            val known = commonErrors.toMutableList()
            if (current != null && errorInfo(current)?.title !in known.map { errorInfo(it)?.title }) known.add(0, current)
            known
        }
        for (code in codes) {
            val info = errorInfo(code) ?: continue
            val active = current != null && errorInfo(current)?.title == info.title
            var open by rememberSaveable(code) { mutableStateOf(active) }
            PanelCard(onClick = { open = !open }, padding = PaddingValues(16.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        if (active) {
                            StatusPill(tr(R.string.help_current), Tone.ERROR, Modifier.padding(bottom = 6.dp))
                        }
                        Text(tr(info.title), style = MaterialTheme.typography.titleMedium)
                    }
                    Icon(
                        M7Icons.ExpandMore, null, Modifier.rotate(if (open) 180f else 0f),
                        tint = MaterialTheme.colorScheme.outline,
                    )
                }
                AnimatedVisibility(open) {
                    Column {
                        Text(tr(info.advice), Modifier.padding(top = 8.dp), style = MaterialTheme.typography.bodyMedium)
                        Text(
                            tr(R.string.error_code, code), Modifier.padding(top = 6.dp),
                            style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }
    }
}
