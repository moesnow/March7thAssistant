package top.m7a.ui

import java.net.URLEncoder
import java.util.TreeMap

internal data class VersionNote(val version: String, val markdown: String)

internal data class UpdateHistory(val sections: List<VersionNote>, val partial: Boolean)

internal const val CHANGELOG_PATH = "assets/docs/Changelog.md"

internal fun changelogUrl(version: String) =
    "https://github.com/moesnow/March7thAssistant/blob/${encodeVersion(version)}/$CHANGELOG_PATH"

internal fun encodeVersion(version: String): String = URLEncoder.encode(version, Charsets.UTF_8.name())

internal fun requireUpdateRange(installedVersion: String, targetVersion: String) {
    val installed = requireNotNull(UpdateVersion.parse(installedVersion))
    val target = requireNotNull(UpdateVersion.parse(targetVersion))
    require(installed < target) { "更新记录区间无效" }
}

private val hiddenBlock = Regex("""<!--\s*m7a:hide\s*-->.*?<!--\s*/m7a:hide\s*-->""", RegexOption.DOT_MATCHES_ALL)
private val image = Regex("""!\[.*?]\(.*?\)""")
private val versionHeading = Regex("""^##[ \t]+([^ \t#]+)(?:[ \t]+#+)?[ \t]*$""")
private val fenceStart = Regex("""^ {0,3}(`{3,}|~{3,})""")

internal fun cleanUpdateNote(markdown: String) = image.replace(hiddenBlock.replace(markdown, ""), "").trim()

private fun parseChangelog(document: String): TreeMap<UpdateVersion, VersionNote> {
    val versions = TreeMap<UpdateVersion, VersionNote>()
    var current: UpdateVersion? = null
    var title = ""
    var fence: String? = null
    val notes = StringBuilder()

    fun finishSection() {
        current?.let { versions.putIfAbsent(it, VersionNote(title, notes.toString().trim())) }
        notes.clear()
    }

    for (line in cleanUpdateNote(document.removePrefix("\uFEFF")).lineSequence()) {
        val marker = fenceStart.find(line)?.groupValues?.get(1)
        val activeFence = fence
        when {
            activeFence != null -> {
                if (marker != null && marker[0] == activeFence[0] && marker.length >= activeFence.length) fence = null
            }
            marker != null -> fence = marker
            line.startsWith("## ") || line.startsWith("##\t") -> {
                finishSection()
                title = versionHeading.matchEntire(line)?.groupValues?.get(1).orEmpty()
                current = UpdateVersion.parse(title)
                continue
            }
        }
        if (current != null) notes.appendLine(line)
    }
    finishSection()
    return versions
}

internal fun collectUpdateHistory(
    document: String,
    installedVersion: String,
    release: UpdateRelease,
    includePrerelease: Boolean,
): UpdateHistory {
    val installed = requireNotNull(UpdateVersion.parse(installedVersion))
    val target = requireNotNull(UpdateVersion.parse(release.version))
    require(installed < target) { "更新记录区间无效" }
    val versions = parseChangelog(document)
    require(versions.isNotEmpty() && versions.lastKey() <= target) { "累计更新日志与目标版本不一致" }
    val recorded = versions[target]
    require(recorded != null || target.isPrerelease) { "累计更新日志未包含目标版本" }

    val latest = VersionNote(release.version, cleanUpdateNote(release.notes).ifEmpty { recorded?.markdown.orEmpty() })
    val skipped = versions.subMap(installed, false, target, false).descendingMap()
        .filterKeys { includePrerelease || !it.isPrerelease }.values
    return UpdateHistory(listOf(latest) + skipped, partial = recorded == null || versions.firstKey() > installed)
}
