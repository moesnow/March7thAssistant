package top.m7a.ui

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.net.SocketTimeoutException
import java.net.URI
import javax.net.ssl.HttpsURLConnection
import kotlin.coroutines.CoroutineContext

/** GitHub 公开接口和桌面端使用的备用地址。响应须通过调用方校验才能采用。 */
internal object GitHubUpdateApi {
    private const val HOST = "api.github.com"
    private const val REPOSITORY = "/repos/moesnow/March7thAssistant"
    private const val MAX_BYTES = 2 * 1024 * 1024
    private val bases = listOf("https://$HOST", "https://github.kotori.top/https://$HOST")
    private val acceptedPaths = mapOf(
        "$REPOSITORY/releases" to "/repositories/680196753/releases",
        "$REPOSITORY/contents/$CHANGELOG_PATH" to "/repositories/680196753/contents/$CHANGELOG_PATH",
    )

    suspend fun <T> get(path: String, query: String, decode: (String) -> T): T =
        withContext(Dispatchers.IO) {
            val deadline = now() + 5_000L
            var lastError: Exception? = null
            for (base in bases) {
                ensureActive()
                if (now() >= deadline) break
                try {
                    return@withContext decode(fetch(base, path, query, deadline, coroutineContext))
                } catch (error: CancellationException) {
                    throw error
                } catch (error: Exception) {
                    lastError = error
                }
            }
            throw IOException("无法读取 GitHub 发布信息", lastError)
        }

    private fun fetch(base: String, path: String, query: String, deadline: Long, context: CoroutineContext): String {
        val expectedPath = "$REPOSITORY$path"
        var uri = URI("$base$expectedPath?$query")
        repeat(3) {
            context.ensureActive()
            val remaining = deadline - now()
            if (remaining <= 0) throw SocketTimeoutException("读取 GitHub 发布信息超时")
            val connection = uri.toURL().openConnection() as HttpsURLConnection
            try {
                connection.connectTimeout = minOf(1_000L, remaining).toInt()
                connection.readTimeout = connection.connectTimeout
                connection.instanceFollowRedirects = false
                connection.setRequestProperty("Accept", "application/vnd.github+json")
                connection.setRequestProperty("User-Agent", "March7thAssistant-Android")
                val status = connection.responseCode
                if (status in setOf(301, 302, 303, 307, 308)) {
                    val redirect = uri.resolve(requireNotNull(connection.getHeaderField("Location")))
                    require(
                        redirect.scheme == "https" && redirect.rawAuthority == HOST &&
                            (redirect.path == expectedPath || redirect.path == acceptedPaths[expectedPath]) &&
                            redirect.rawQuery == query,
                    )
                    uri = redirect
                    return@repeat
                }
                if (status != 200) throw IOException("GitHub 发布接口 HTTP $status")
                val body = ByteArrayOutputStream()
                connection.inputStream.use { input ->
                    val buffer = ByteArray(16 * 1024)
                    while (true) {
                        context.ensureActive()
                        if (now() >= deadline) throw SocketTimeoutException("读取 GitHub 发布信息超时")
                        val size = input.read(buffer)
                        if (size < 0) break
                        require(body.size() + size <= MAX_BYTES) { "GitHub 发布响应过大" }
                        body.write(buffer, 0, size)
                    }
                }
                return body.toByteArray().decodeToString(throwOnInvalidSequence = true)
            } finally {
                connection.disconnect()
            }
        }
        throw IOException("GitHub 发布接口重定向次数过多")
    }

    private fun now() = System.nanoTime() / 1_000_000
}
