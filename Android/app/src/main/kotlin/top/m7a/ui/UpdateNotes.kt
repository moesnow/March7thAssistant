package top.m7a.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.LinkAnnotation
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextLinkStyles
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.withLink
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CancellationException
import top.m7a.R

@Composable
internal fun UpdateNotes(
    release: UpdateRelease,
    installedVersion: String,
    includePrerelease: Boolean,
    loadHistory: Boolean,
    updater: AppUpdater,
    openUrl: (String) -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    var history by remember(installedVersion, release, includePrerelease, updater) { mutableStateOf<UpdateHistory?>(null) }
    var loadFailed by remember(installedVersion, release, includePrerelease, updater) { mutableStateOf(false) }
    var visibleCount by rememberSaveable(installedVersion, release.version) { mutableIntStateOf(10) }
    val latest = remember(release) { listOf(VersionNote(release.version, cleanUpdateNote(release.notes))) }
    val sections = history?.sections ?: latest

    LaunchedEffect(installedVersion, release, includePrerelease, loadHistory, updater) {
        if (!loadHistory) return@LaunchedEffect
        try {
            history = updater.loadHistory(installedVersion, release, includePrerelease)
        } catch (error: CancellationException) {
            throw error
        } catch (_: Exception) {
            loadFailed = true
        }
    }

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        FlowRow(
            Modifier.fillMaxWidth().padding(start = 4.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(
                tr(R.string.update_notes), Modifier.align(Alignment.CenterVertically).semantics { heading() },
                style = MaterialTheme.typography.titleMedium,
            )
            if (loadHistory) {
                TextButton(onClick = { openUrl(changelogUrl(release.version)) }) {
                    Text(tr(R.string.update_notes_full))
                }
            }
        }
        val status = when {
            loadFailed -> R.string.update_notes_failed
            history?.partial == true -> R.string.update_notes_partial
            loadHistory && history == null -> R.string.update_notes_loading
            else -> null
        }
        if (status != null) {
            Column(
                Modifier.fillMaxWidth().padding(horizontal = 4.dp).semantics { liveRegion = LiveRegionMode.Polite },
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                if (status == R.string.update_notes_loading) LinearProgressIndicator(Modifier.fillMaxWidth())
                BodyText(tr(status))
            }
        }
        for ((index, section) in sections.take(visibleCount).withIndex()) {
            PanelCard {
                Row(
                    Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        section.version, Modifier.weight(1f).semantics { heading() },
                        style = MaterialTheme.typography.titleMedium, color = scheme.primary,
                    )
                    if (index == 0) release.publishedOn?.let {
                        Text(it.toString(), style = MaterialTheme.typography.labelMedium, color = scheme.onSurfaceVariant)
                    }
                }
                if (section.markdown.isNotBlank()) {
                    Column(Modifier.padding(top = 10.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        for (source in section.markdown.lineSequence().map { it.trim() }.filter { it.isNotEmpty() }) {
                            val bullet = source.startsWith("- ") || source.startsWith("* ") || source.startsWith("+ ")
                            val note = if (bullet) source.drop(2) else source
                            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                if (bullet) Box(Modifier.padding(top = 8.dp).size(5.dp).background(scheme.primary, CircleShape))
                                NoteText(note, openUrl)
                            }
                        }
                    }
                }
            }
        }
        if (sections.size > visibleCount) {
            TextButton(onClick = { visibleCount += 10 }, modifier = Modifier.align(Alignment.CenterHorizontally)) {
                Text(tr(R.string.update_notes_more, sections.size - visibleCount))
            }
        }
    }
}

private val noteMarkup = Regex("""\[([^\]]+)]\((https://[^\s)]+)\)|`([^`]+)`""")

@Composable
private fun NoteText(note: String, openUrl: (String) -> Unit) {
    val scheme = MaterialTheme.colorScheme
    val text = remember(note, scheme.primary, openUrl) {
        buildAnnotatedString {
            var offset = 0
            for (markup in noteMarkup.findAll(note)) {
                append(note.substring(offset, markup.range.first))
                val (label, url, code) = markup.destructured
                if (url.isNotEmpty()) {
                    val style = SpanStyle(color = scheme.primary, textDecoration = TextDecoration.Underline)
                    withLink(LinkAnnotation.Url(url, TextLinkStyles(style = style)) { openUrl(url) }) { append(label) }
                } else {
                    pushStyle(SpanStyle(fontFamily = FontFamily.Monospace))
                    append(code)
                    pop()
                }
                offset = markup.range.last + 1
            }
            append(note.substring(offset))
        }
    }
    Text(text, style = MaterialTheme.typography.bodyMedium, color = scheme.onSurfaceVariant)
}
