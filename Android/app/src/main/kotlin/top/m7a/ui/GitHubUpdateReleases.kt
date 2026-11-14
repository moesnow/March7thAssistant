package top.m7a.ui

import kotlinx.coroutines.withTimeoutOrNull
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.URI
import java.time.Instant
import java.time.ZoneId

internal const val ANDROID_ASSET = "March7thAssistant_full_android.apk"
private const val PAGE_SIZE = 30

internal data class AndroidRelease(
    val details: UpdateRelease?,
    val draft: Boolean,
    val prerelease: Boolean,
)

/** 按版本号挑选安卓发布，公测通道同时接受正式版。 */
internal fun selectAndroidRelease(releases: List<AndroidRelease>, channel: UpdateChannel): UpdateRelease? =
    releases.asSequence()
        .filterNot { it.draft }
        .mapNotNull { candidate ->
            val details = candidate.details ?: return@mapNotNull null
            val version = UpdateVersion.parse(details.version) ?: return@mapNotNull null
            val prerelease = candidate.prerelease || version.isPrerelease
            if (prerelease && !channel.includesPrerelease) null else version to details
        }
        .maxByOrNull { it.first }
        ?.second

internal object GitHubUpdateReleases {
    private data class Lookup(val release: UpdateRelease?)

    suspend fun latest(channel: UpdateChannel): UpdateRelease? {
        val result = withTimeoutOrNull(12_000L) { Lookup(findLatest(channel)) }
            ?: throw IOException("查找安卓发布超时")
        return result.release
    }

    private suspend fun findLatest(channel: UpdateChannel): UpdateRelease? {
        // 同一发布列表可同时包含只发桌面包的版本，按页寻找包含指定 APK 的发布。
        val candidates = mutableListOf<AndroidRelease>()
        var page = 1
        while (true) {
            val (releases, hasMore) = GitHubUpdateApi.get("/releases", "per_page=$PAGE_SIZE&page=$page") { body ->
                val entries = JSONArray(body)
                val releases = (0 until entries.length()).map { androidRelease(entries.getJSONObject(it)) }
                releases to (entries.length() == PAGE_SIZE)
            }
            candidates.addAll(releases)
            // 公测选择也要覆盖可能在后一页发布的正式版。
            val stable = selectAndroidRelease(candidates, UpdateChannel.STABLE)
            if (stable != null || !hasMore) {
                return if (channel.includesPrerelease) selectAndroidRelease(candidates, channel) else stable
            }
            page++
        }
    }

    private fun androidRelease(entry: JSONObject): AndroidRelease {
        val version = entry.getString("tag_name")
        require(version.isNotBlank())
        val assets = entry.getJSONArray("assets")
        val apk = (0 until assets.length()).asSequence().mapNotNull(assets::optJSONObject)
            .firstOrNull { it.optString("name") == ANDROID_ASSET && it.optLong("size") > 0 }
        val details = apk?.let {
            val publishedOn = entry.optString("published_at").takeIf(String::isNotBlank)?.let { published ->
                runCatching { Instant.parse(published).atZone(ZoneId.systemDefault()).toLocalDate() }.getOrNull()
            }
            UpdateRelease(
                version, publishedOn, entry.optString("body", ""), it.getLong("size"),
                normalizeUpdateSha256(it.optString("digest")),
            )
        }
        return AndroidRelease(
            details, draft = entry.optBoolean("draft"), prerelease = entry.optBoolean("prerelease"),
        )
    }
}

internal fun githubApkDownload(release: UpdateRelease): ApkDownload {
    val version = URI(null, null, "/${release.version}", null).rawPath.substring(1)
    return apkDownload(
        "${UpdateSource.GITHUB.pageUrl}/download/$version/$ANDROID_ASSET",
        release.sizeBytes ?: 0L, release.sha256.orEmpty(),
    )
}
