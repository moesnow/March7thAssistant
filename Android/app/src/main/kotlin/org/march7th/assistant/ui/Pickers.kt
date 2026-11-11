package org.march7th.assistant.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Checkbox
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import org.march7th.assistant.CatalogItem
import org.march7th.assistant.R

@Composable
private fun ChoiceText(choice: CatalogItem) {
    Column(Modifier.padding(vertical = 8.dp)) {
        Text(choice.title, style = MaterialTheme.typography.bodyLarge)
        choice.detail?.let {
            Text(
                it, style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

/** 单选列表，点选即生效。副本这类选项多于 8 个的列表带搜索框，按名称和说明筛选。 */
@Composable
internal fun ChoiceDialog(
    title: String,
    choices: List<CatalogItem>,
    selected: String?,
    onSelect: (String) -> Unit,
    onDismiss: () -> Unit,
    searchable: Boolean = choices.size > 8,
) {
    var query by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        confirmButton = { TextButton(onClick = onDismiss) { Text(tr(R.string.cancel)) } },
        title = { Text(title) },
        text = {
            Column {
                if (searchable) {
                    OutlinedTextField(
                        query, { query = it }, Modifier.fillMaxWidth().padding(bottom = 8.dp),
                        placeholder = { Text(tr(R.string.instance_search)) },
                        leadingIcon = { Icon(M7Icons.Search, null) },
                        singleLine = true,
                    )
                }
                val keyword = query.trim()
                val visible = if (keyword.isEmpty()) choices else choices.filter {
                    it.title.contains(keyword, ignoreCase = true) || it.detail?.contains(keyword, ignoreCase = true) == true
                }
                val start = visible.indexOfFirst { it.id == selected }.coerceAtLeast(0)
                LazyColumn(state = rememberLazyListState(initialFirstVisibleItemIndex = start)) {
                    items(visible, key = { it.id }) { choice ->
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .selectable(selected = choice.id == selected, role = Role.RadioButton) { onSelect(choice.id) }
                                .heightIn(min = 56.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            RadioButton(choice.id == selected, null, Modifier.padding(end = 16.dp))
                            ChoiceText(choice)
                        }
                    }
                }
            }
        },
    )
}

/** 一行文字输入，确定后才写回。 */
@Composable
internal fun TextDialog(
    title: String,
    initial: String,
    label: String,
    hint: String,
    onConfirm: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    var text by remember { mutableStateOf(initial) }
    AlertDialog(
        onDismissRequest = onDismiss,
        confirmButton = { TextButton(onClick = { onConfirm(text.trim()) }) { Text(tr(R.string.confirm)) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text(tr(R.string.cancel)) } },
        title = { Text(title) },
        text = {
            Column {
                OutlinedTextField(
                    text, { text = it }, Modifier.fillMaxWidth(),
                    label = { Text(label) }, singleLine = true,
                )
                Text(
                    hint, Modifier.padding(top = 8.dp),
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        },
    )
}

/** 打开有消耗或不可恢复的选项前确认一次。 */
@Composable
internal fun ConfirmDialog(title: String, body: String, onConfirm: () -> Unit, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        icon = { Icon(M7Icons.Warning, null, tint = LocalBrand.current.warning) },
        confirmButton = { TextButton(onClick = onConfirm) { Text(tr(R.string.confirm)) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text(tr(R.string.cancel)) } },
        title = { Text(title) },
        text = { Text(body) },
    )
}

/** 多选列表，结果保持点选的先后顺序，最多选 limit 项。 */
@Composable
internal fun MultiChoiceDialog(
    title: String,
    choices: List<CatalogItem>,
    selected: List<String>,
    limit: Int,
    onConfirm: (List<String>) -> Unit,
    onDismiss: () -> Unit,
) {
    var picked by remember { mutableStateOf(selected) }
    var query by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        confirmButton = { TextButton(onClick = { onConfirm(picked) }) { Text(tr(R.string.confirm)) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text(tr(R.string.cancel)) } },
        title = { Text(title) },
        text = {
            Column {
                Text(
                    tr(R.string.option_supports_count, picked.size, limit),
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                OutlinedTextField(
                    query, { query = it }, Modifier.fillMaxWidth().padding(vertical = 8.dp),
                    placeholder = { Text(tr(R.string.option_supports_search)) }, singleLine = true,
                )
                val keyword = query.trim()
                val visible = if (keyword.isEmpty()) choices else choices.filter { it.title.contains(keyword, ignoreCase = true) }
                LazyColumn {
                    items(visible, key = { it.id }) { choice ->
                        val checked = choice.id in picked
                        val available = checked || picked.size < limit
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .toggleable(value = checked, enabled = available, role = Role.Checkbox) {
                                    picked = if (it) picked + choice.id else picked - choice.id
                                }
                                .heightIn(min = 52.dp)
                                .alpha(if (available) 1f else 0.5f),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Checkbox(checked, null, Modifier.padding(end = 16.dp), enabled = available)
                            ChoiceText(choice)
                        }
                    }
                }
            }
        },
    )
}
