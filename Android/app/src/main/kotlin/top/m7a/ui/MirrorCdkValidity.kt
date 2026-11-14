package top.m7a.ui

import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.IOException
import java.net.URL
import java.time.Duration
import java.time.Instant
import javax.net.ssl.HttpsURLConnection

internal class MirrorCdkError(val code: Int) : IOException("Mirror酱接口请求失败（$code）")

internal fun MirrorCdkError.updateProblem(): UpdateProblem = when (code) {
    7001 -> UpdateProblem.CDK_EXPIRED
    7002 -> UpdateProblem.CDK_INVALID
    7003 -> UpdateProblem.CDK_QUOTA
    7004 -> UpdateProblem.CDK_MISMATCH
    7005 -> UpdateProblem.CDK_BLOCKED
    8001, 8002, 8003, 8004, 8009 -> UpdateProblem.MIRROR_UNAVAILABLE
    else -> UpdateProblem.NETWORK
}

internal fun remainingCdkDays(expiresAt: Instant, now: Instant): Long? =
    Duration.between(now, expiresAt).takeUnless { it.isZero || it.isNegative }?.toDays()

/** CDK 随项目校验。先取最新版本再带 CDK 查询有效期，避免请求下载地址。 */
internal suspend fun queryMirrorCdkExpiry(cdk: String): Instant = withContext(Dispatchers.IO) {
    val version = mirrorCdkData().getString("version_name")
    ensureActive()
    val expires = mirrorCdkData(cdk, version).optLong("cdk_expired_time")
    if (expires <= 0) throw IOException("未返回 CDK 到期时间")
    Instant.ofEpochSecond(expires)
}

/** 查询不带 CDK，只有确实要取 APK 时才请求带 CDK 的下载地址。 */
internal suspend fun mirrorApkDownload(channel: UpdateChannel, release: UpdateRelease, cdk: String): ApkDownload =
    withContext(Dispatchers.IO) {
        if (cdk.isBlank()) throw UpdateException(UpdateProblem.CDK_INVALID)
        requireMirrorTarget(release, mirrorCdkData(channel = channel).getString("version_name"))
        ensureActive()
        val data = mirrorCdkData(cdk = cdk, channel = channel)
        val url = data.optString("url")
        if (url.isBlank()) throw UpdateException(UpdateProblem.MIRROR_UNAVAILABLE)
        resolveMirrorApk(release, data.getString("version_name"), data.optString("update_type"),
            url, data.optLong("filesize"), data.optString("sha256"))
    }

private fun requireMirrorTarget(release: UpdateRelease, version: String) {
    val target = UpdateVersion.parse(release.version)
    if (target == null || UpdateVersion.parse(version) != target) throw UpdateException(UpdateProblem.MIRROR_VERSION)
}

internal fun resolveMirrorApk(
    release: UpdateRelease, version: String, type: String, url: String, size: Long, sha256: String,
): ApkDownload {
    requireMirrorTarget(release, version)
    if (type.isNotEmpty() && type != "full") throw UpdateException(UpdateProblem.PACKAGE)
    val download = apkDownload(url, size, sha256)
    if (download.sha256 != release.sha256 || download.size != release.sizeBytes) {
        throw UpdateException(UpdateProblem.MIRROR_VERSION)
    }
    return download
}

private suspend fun mirrorCdkData(cdk: String? = null, version: String? = null, channel: UpdateChannel? = null): JSONObject {
    val context = currentCoroutineContext()
    val url = Uri.parse("https://mirrorchyan.com/api/resources/March7thAssistant/latest").buildUpon()
        .appendQueryParameter("user_agent", "m7a_app_android")
        .apply {
            if (cdk != null) appendQueryParameter("cdk", cdk)
            if (version != null) appendQueryParameter("current_version", version)
            if (channel != null) {
                appendQueryParameter("os", "android")
                appendQueryParameter("channel", channel.mirrorQuery)
            }
        }.build()
    val connection = URL(url.toString()).openConnection() as HttpsURLConnection
    return withUpdateConnection(connection) {
        connection.connectTimeout = 5_000
        connection.readTimeout = 5_000
        connection.instanceFollowRedirects = false
        // 含 CDK 的响应只用于这次查询，避免 HTTP 缓存保存请求 URL。
        connection.useCaches = false
        connection.setRequestProperty("Accept", "application/json")
        val status = connection.responseCode
        val stream = (if (status == 200) connection.inputStream else connection.errorStream)
            ?: throw IOException("Mirror酱 HTTP $status")
        val json = stream.bufferedReader(Charsets.UTF_8).use {
            val body = StringBuilder()
            val buffer = CharArray(4096)
            val deadline = System.nanoTime() + 5_000_000_000L
            while (true) {
                context.ensureActive()
                if (System.nanoTime() >= deadline) throw IOException("Mirror酱接口请求超时")
                val count = it.read(buffer)
                if (count < 0) break
                if (body.length + count > 256 * 1024) throw IOException("Mirror酱接口响应过大")
                body.append(buffer, 0, count)
            }
            JSONObject(body.toString())
        }
        val code = json.getInt("code")
        if (code != 0) throw MirrorCdkError(code)
        if (status != 200) throw IOException("Mirror酱 HTTP $status")
        json.getJSONObject("data")
    }
}
