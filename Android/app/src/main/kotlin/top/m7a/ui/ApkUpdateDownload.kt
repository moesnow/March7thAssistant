package top.m7a.ui

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.net.URI
import java.security.MessageDigest
import java.util.concurrent.atomic.AtomicReference
import javax.net.ssl.HttpsURLConnection

internal class UpdateException(val problem: UpdateProblem) : IOException(problem.name)

internal data class ApkDownload(val url: URI, val size: Long, val sha256: String)

private val SHA256 = Regex("[0-9a-f]{64}")
private val CONTENT_RANGE = Regex("""bytes ([0-9]+)-([0-9]+)/([0-9]+)""")
private val REDIRECTS = setOf(301, 302, 303, 307, 308)
private const val MAX_APK_BYTES = 2L * 1024 * 1024 * 1024

internal fun normalizeUpdateSha256(text: String): String? =
    text.trim().lowercase().removePrefix("sha256:").trim().takeIf(SHA256::matches)

internal fun httpsUpdateUri(value: String): URI = try {
    URI(value).also {
        if (it.scheme != "https" || it.host.isNullOrEmpty() || it.rawUserInfo != null || it.rawFragment != null) {
            throw UpdateException(UpdateProblem.PACKAGE)
        }
    }
} catch (_: IllegalArgumentException) {
    throw UpdateException(UpdateProblem.PACKAGE)
} catch (_: java.net.URISyntaxException) {
    throw UpdateException(UpdateProblem.PACKAGE)
}

internal fun apkDownload(url: String, size: Long, digest: String): ApkDownload {
    if (size !in 1..MAX_APK_BYTES) throw UpdateException(UpdateProblem.PACKAGE)
    val hash = normalizeUpdateSha256(digest) ?: throw UpdateException(UpdateProblem.PACKAGE)
    return ApkDownload(httpsUpdateUri(url), size, hash)
}

/** Mirror酱始终从 0 开始。只有 GitHub 可以保留可校验的网络中断片段。 */
internal suspend fun transferApk(
    candidate: ApkDownload,
    part: File,
    source: UpdateSource,
    openConnection: (URI) -> HttpsURLConnection = ::openApkConnection,
    progress: suspend (Long, Long) -> Unit,
) {
    val resumable = source == UpdateSource.GITHUB
    try {
        if (!resumable || part.length() > candidate.size) part.delete()
        if (resumable && part.length() == candidate.size) return
        val offset = if (resumable) part.length() else 0L
        withDownloadConnection(candidate.url, offset, openConnection) { connection, status ->
            val start = when {
                status == 200 -> 0L
                status == 206 && offset > 0 -> {
                    if (!matchesContentRange(connection.getHeaderField("Content-Range"), offset, candidate.size)) {
                        throw UpdateException(UpdateProblem.PACKAGE)
                    }
                    offset
                }
                status == 206 || status == 416 -> throw UpdateException(UpdateProblem.PACKAGE)
                else -> throw UpdateException(UpdateProblem.NETWORK)
            }
            val remaining = candidate.size - start
            val length = connection.contentLengthLong
            if (length >= 0 && length != remaining) throw UpdateException(UpdateProblem.PACKAGE)
            val available = checkNotNull(part.parentFile).usableSpace + if (start == 0L) part.length() else 0L
            if (available < remaining) throw UpdateException(UpdateProblem.SPACE)
            progress(start, candidate.size)
            connection.inputStream.use { input ->
                FileOutputStream(part, start > 0).buffered().use { output ->
                    var received = start
                    var reportedAt = System.nanoTime()
                    val buffer = ByteArray(64 * 1024)
                    while (true) {
                        currentCoroutineContext().ensureActive()
                        val count = input.read(buffer)
                        if (count == -1) break
                        received += count
                        if (received > candidate.size) throw UpdateException(UpdateProblem.PACKAGE)
                        output.write(buffer, 0, count)
                        val now = System.nanoTime()
                        if (now - reportedAt >= 100_000_000 || received == candidate.size) {
                            progress(received, candidate.size)
                            reportedAt = now
                        }
                    }
                    if (received != candidate.size) throw UpdateException(UpdateProblem.NETWORK)
                }
            }
        }
    } catch (error: Exception) {
        if (!resumable || (error is UpdateException && error.problem == UpdateProblem.PACKAGE)) part.delete()
        currentCoroutineContext().ensureActive()
        throw error
    }
}

internal fun matchesContentRange(header: String?, offset: Long, total: Long): Boolean {
    val range = header?.let(CONTENT_RANGE::matchEntire) ?: return false
    val (start, end, size) = range.destructured
    return start.toLongOrNull() == offset && end.toLongOrNull() == total - 1 && size.toLongOrNull() == total
}

internal suspend fun matchesApkDigest(file: File, size: Long?, sha256: String): Boolean {
    if (!file.isFile || (size != null && file.length() != size)) return false
    val context = currentCoroutineContext()
    val expected = normalizeUpdateSha256(sha256) ?: return false
    val digest = MessageDigest.getInstance("SHA-256")
    file.inputStream().use { input ->
        val buffer = ByteArray(128 * 1024)
        while (true) {
            context.ensureActive()
            val count = input.read(buffer)
            if (count == -1) break
            digest.update(buffer, 0, count)
        }
    }
    return digest.digest().toHexString() == expected
}

private suspend fun withDownloadConnection(
    url: URI,
    offset: Long,
    openConnection: (URI) -> HttpsURLConnection,
    use: suspend (HttpsURLConnection, Int) -> Unit,
) {
    val context = currentCoroutineContext()
    var address = url
    repeat(6) {
        context.ensureActive()
        val connection = openConnection(address)
        val redirect = withUpdateConnection(connection) {
            connection.instanceFollowRedirects = false
            connection.useCaches = false
            connection.connectTimeout = 10_000
            connection.readTimeout = 15_000
            connection.setRequestProperty("Accept-Encoding", "identity")
            if (offset > 0) connection.setRequestProperty("Range", "bytes=$offset-")
            val status = connection.responseCode
            if (status in REDIRECTS) {
                val location = connection.getHeaderField("Location") ?: throw UpdateException(UpdateProblem.NETWORK)
                try {
                    httpsUpdateUri(address.resolve(location).toString())
                } catch (_: IllegalArgumentException) {
                    throw UpdateException(UpdateProblem.PACKAGE)
                }
            } else {
                context.ensureActive()
                use(connection, status)
                null
            }
        }
        address = redirect ?: return
    }
    throw UpdateException(UpdateProblem.NETWORK)
}

internal fun openApkConnection(address: URI) = address.toURL().openConnection() as HttpsURLConnection

/** 关闭阻塞的 HTTP 读操作，连接本身不依赖协程调度器来响应取消。 */
internal suspend fun <T> withUpdateConnection(
    connection: HttpsURLConnection, use: suspend () -> T,
): T {
    val context = currentCoroutineContext()
    val active = AtomicReference<HttpsURLConnection?>(connection)
    val cancelSignal = CoroutineScope(context).launch(Dispatchers.IO, start = CoroutineStart.UNDISPATCHED) {
        suspendCancellableCoroutine<Unit> { continuation ->
            continuation.invokeOnCancellation { runCatching { active.get()?.disconnect() } }
        }
    }
    try {
        context.ensureActive()
        return use()
    } finally {
        runCatching { active.getAndSet(null)?.disconnect() }
        cancelSignal.cancel()
    }
}
