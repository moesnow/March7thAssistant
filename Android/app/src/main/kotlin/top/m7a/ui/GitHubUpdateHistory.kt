package top.m7a.ui

import android.util.Base64
import org.json.JSONObject

/** 使用目标 tag 的累计日志。 */
internal object GitHubUpdateHistory {
    private const val CACHE_MS = 10 * 60_000L
    private data class Cached(val history: UpdateHistory, val until: Long)
    private val cache = LinkedHashMap<Triple<String, UpdateRelease, Boolean>, Cached>(4, 0.75f, true)

    suspend fun load(installedVersion: String, release: UpdateRelease, includePrerelease: Boolean): UpdateHistory {
        requireUpdateRange(installedVersion, release.version)
        val key = Triple(installedVersion, release, includePrerelease)
        synchronized(cache) { cache[key]?.takeIf { it.until > now() } }?.let { return it.history }

        val history = GitHubUpdateApi.get("/contents/$CHANGELOG_PATH", "ref=${encodeVersion(release.version)}") { body ->
            val json = JSONObject(body)
            require(json.optString("type") == "file" && json.optString("encoding") == "base64")
            val document = Base64.decode(json.getString("content"), Base64.DEFAULT).decodeToString(throwOnInvalidSequence = true)
            collectUpdateHistory(document, installedVersion, release, includePrerelease)
        }
        synchronized(cache) {
            cache[key] = Cached(history, now() + CACHE_MS)
            if (cache.size > 4) cache.remove(cache.keys.first())
        }
        return history
    }

    private fun now() = System.nanoTime() / 1_000_000
}
