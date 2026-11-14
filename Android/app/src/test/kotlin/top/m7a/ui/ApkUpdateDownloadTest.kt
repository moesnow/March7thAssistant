package top.m7a.ui

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.ByteArrayInputStream
import java.io.IOException
import java.io.InputStream
import java.net.URI
import java.net.URL
import java.security.MessageDigest
import java.security.cert.Certificate
import java.util.concurrent.CountDownLatch
import javax.net.ssl.HttpsURLConnection

class ApkUpdateDownloadTest {
    @get:Rule val temporary = TemporaryFolder()
    private val bytes = "signed apk fixture".encodeToByteArray()
    private val digest = MessageDigest.getInstance("SHA-256").digest(bytes).toHexString()
    private val apk = apkDownload("https://example.test/update.apk", bytes.size.toLong(), "sha256:$digest")

    @Test
    fun mirrorAlwaysStartsAtZeroAndNeverUsesRange() = runBlocking {
        val part = temporary.newFile().apply { writeText("stale bytes") }
        val transport = Response(200, bytes)
        val offsets = mutableListOf<Long>()

        transferApk(apk, part, UpdateSource.MIRROR, { transport }) { count, _ -> offsets += count }

        assertNull(transport.range)
        assertEquals(0L, offsets.first())
        assertArrayEquals(bytes, part.readBytes())
        assertTrue(matchesApkDigest(part, apk.size, apk.sha256))
        assertFalse(matchesApkDigest(part, apk.size, "0".repeat(64)))
    }

    @Test
    fun retryKeepsGitHubPartialButDiscardsMirrorPartial() = runBlocking {
        val github = temporary.newFile()
        val mirror = temporary.newFile()
        for ((file, source) in listOf(github to UpdateSource.GITHUB, mirror to UpdateSource.MIRROR)) {
            val incomplete = Response(200, bytes.copyOf(7), length = apk.size)
            assertNotNull(runCatching { transferApk(apk, file, source, { incomplete }) { _, _ -> } }.exceptionOrNull())
        }
        assertEquals(7L, github.length())
        assertFalse(mirror.exists())
        val response = Response(206, bytes.copyOfRange(7, bytes.size), contentRange = "bytes 7-${bytes.lastIndex}/${bytes.size}")

        transferApk(apk, github, UpdateSource.GITHUB, { response }) { _, _ -> }

        assertEquals("bytes=7-", response.range)
        assertArrayEquals(bytes, github.readBytes())
    }

    @Test
    fun githubReplacesPartialIfServerSendsAFullResponse() = runBlocking {
        val part = temporary.newFile().apply { writeText("old") }
        val response = Response(200, bytes)

        transferApk(apk, part, UpdateSource.GITHUB, { response }) { _, _ -> }

        assertEquals("bytes=3-", response.range)
        assertArrayEquals(bytes, part.readBytes())
    }

    @Test
    fun mirrorRejectsPartialResponseAndGitHubRejectsMismatchedRange() = runBlocking {
        for (source in UpdateSource.entries) {
            val part = temporary.newFile().apply { writeBytes(bytes.copyOf(7)) }
            val response = Response(206, bytes.copyOfRange(7, bytes.size), contentRange = "bytes 8-${bytes.lastIndex}/${bytes.size}")
            val error = runCatching { transferApk(apk, part, source, { response }) { _, _ -> } }.exceptionOrNull()

            assertEquals(UpdateProblem.PACKAGE, (error as? UpdateException)?.problem)
            assertFalse(part.exists())
        }
    }

    @Test(timeout = 5000)
    fun cancellingMirrorClosesTheConnectionAndRemovesThePartialFile() = runBlocking {
        val part = temporary.newFile()
        val reading = CompletableDeferred<Unit>()
        val closed = CountDownLatch(1)
        val response = object : Response(200, bytes) {
            override fun getInputStream() = object : InputStream() {
                override fun read(): Int {
                    reading.complete(Unit)
                    closed.await()
                    throw IOException("disconnected")
                }
            }
            override fun disconnect() { closed.countDown() }
        }
        val job = launch(Dispatchers.IO) { transferApk(apk, part, UpdateSource.MIRROR, { response }) { _, _ -> } }

        reading.await()
        job.cancelAndJoin()

        assertFalse(part.exists())
        assertEquals(0L, closed.count)
    }

    @Test
    fun mirrorRequiresTheSelectedVersionAndMatchingReleaseDigestAndSize() {
        val release = UpdateRelease("v2026.11.15", null, "", apk.size, apk.sha256)
        val url = "https://example.test/update.apk"

        assertEquals(apk, resolveMirrorApk(release, release.version, "full", url, apk.size, apk.sha256))
        for ((version, hash, size) in listOf(
            Triple("v2026.11.14", apk.sha256, apk.size),
            Triple(release.version, "a".repeat(64), apk.size),
            Triple(release.version, apk.sha256, apk.size - 1),
        )) {
            val error = runCatching { resolveMirrorApk(release, version, "full", url, size, hash) }.exceptionOrNull()
            assertEquals(UpdateProblem.MIRROR_VERSION, (error as? UpdateException)?.problem)
        }
        val error = runCatching { resolveMirrorApk(release, release.version, "incremental", url, apk.size, apk.sha256) }.exceptionOrNull()
        assertEquals(UpdateProblem.PACKAGE, (error as? UpdateException)?.problem)
    }

    private open class Response(
        private val code: Int,
        private val body: ByteArray,
        private val length: Long = body.size.toLong(),
        private val contentRange: String? = null,
    ) : HttpsURLConnection(URL("https://example.test/update.apk")) {
        val range: String? get() = getRequestProperty("Range")
        override fun getResponseCode() = code
        override fun getContentLengthLong() = length
        override fun getHeaderField(name: String) = contentRange.takeIf { name == "Content-Range" }
        override fun getInputStream(): InputStream = ByteArrayInputStream(body)
        override fun connect() = Unit
        override fun disconnect() = Unit
        override fun usingProxy() = false
        override fun getCipherSuite() = ""
        override fun getLocalCertificates(): Array<Certificate>? = null
        override fun getServerCertificates(): Array<Certificate>? = null
    }
}
