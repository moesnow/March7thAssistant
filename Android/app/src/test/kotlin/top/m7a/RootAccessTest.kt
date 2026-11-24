package top.m7a

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import org.march7th.deviceservice.AppServer
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.InputStream
import java.io.PipedInputStream
import java.io.PipedOutputStream
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

class RootAccessTest {
    @Test
    fun probeRequiresRootForTheLauncher() {
        for (uid in listOf(2000, 0)) {
            val process = FakeSu { line ->
                assertEquals("exec /system/bin/id -u", line)
                emit("$uid")
                exit(0)
            }
            val access = rootAccess(process)
            access.probe()
            val expected = if (uid == 0) PermissionState.READY else PermissionState.NOT_AUTHORIZED
            assertEquals(expected, access.permission)
        }
    }

    @Test
    fun recheckDoesNotKeepAnEarlierReadyStateWhenTheProbeFails() {
        var canStart = true
        val access = RootAccess(LAUNCHER, startProcess = {
            check(canStart)
            FakeSu {
                emit("0")
                exit(0)
            }
        }, warn = {})
        access.probe()
        assertEquals(PermissionState.READY, access.permission)

        canStart = false
        assertThrows(IllegalStateException::class.java) { access.probe() }
        assertEquals(PermissionState.NOT_AUTHORIZED, access.permission)
    }

    @Test
    fun sendsTokenAfterAppServerTakesStdinAndClosesLeaseWithEof() {
        val process = FakeSu { line ->
            if (lines.size == 1) {
                val quoted = "'/data/app/it'\\''s here/base.apk'"
                assertEquals(
                    "exec '$QUOTED_LAUNCHER' --root $quoted",
                    line,
                )
                emit("M7A_APP_PORT 1111", AppServer.ROOT_STDIN_READY)
            } else {
                assertEquals(TOKEN, line)
                emit("M7A_APP_PORT 4321")
            }
        }
        rootAccess(process).open("/data/app/it's here/base.apk", TOKEN).use { lease ->
            assertEquals(4321, lease.port)
            assertEquals(2, process.lines.size)
            assertFalse(process.stdinClosed)
        }
        assertTrue(process.stdinClosed)
        assertEquals(0, process.exitValue())
    }

    @Test
    fun wrongUidExitPreservesDiagnosticsWithoutWritingToken() {
        val process = FakeSu {
            emit("invalid Root service entry: uid=0, argc=1")
            exit(2)
        }
        val access = rootAccess(process)
        val error = assertThrows(DeviceFailure::class.java) { access.open(APK, TOKEN) }
        assertEquals("root_unavailable", error.code)
        assertEquals(PermissionState.NOT_AUTHORIZED, access.permission)
        assertTrue(error.message.orEmpty().contains("exit=2"))
        assertTrue(error.message.orEmpty().contains("uid=0"))
        assertEquals(1, process.lines.size)
        assertFalse(process.lines.single().contains(TOKEN))
        assertTrue(process.stdinClosed)
    }

    @Test
    fun startupFailureRedactsTokenInOutput() {
        val process = FakeSu {
            if (lines.size == 1) {
                emit(AppServer.ROOT_STDIN_READY)
            } else {
                emit("error reading session $TOKEN")
                exit(3)
            }
        }
        val error = assertThrows(DeviceFailure::class.java) { rootAccess(process).open(APK, TOKEN) }
        assertEquals("service_start", error.code)
        assertTrue(error.message.orEmpty().contains("exit=3"))
        assertTrue(error.message.orEmpty().contains("error reading session [已脱敏]"))
        assertFalse(error.message.orEmpty().contains(TOKEN))
        assertTrue(process.stdinClosed)
    }

    @Test
    fun filePreparationFailurePreservesTheCauseWithoutSendingTheTokenOrRevokingRoot() {
        val probe = FakeSu {
            emit("0")
            exit(0)
        }
        val process = FakeSu {
            emit(
                "prepare service files: chown: Permission denied (errno=13): /data/local/tmp/m7a-device-service.lock",
                "M7A_APP_FILES_FAILED",
            )
            exit(1)
        }
        val children = listOf(probe, process).iterator()
        val access = RootAccess(LAUNCHER, startProcess = { children.next() }, warn = {})
        access.probe()
        val failure = assertThrows(DeviceFailure::class.java) { access.open(APK, TOKEN) }
        assertEquals("service_start", failure.code)
        assertTrue(failure.message.orEmpty().contains("chown: Permission denied (errno=13)"))
        assertEquals(PermissionState.READY, access.permission)
        assertEquals(1, process.lines.size)
        assertFalse(process.lines.single().contains(TOKEN))
    }

    @Test
    fun busyResponseKeepsItsErrorCode() {
        val process = FakeSu {
            if (lines.size == 1) {
                emit(AppServer.ROOT_STDIN_READY)
            } else {
                emit("M7A_APP_BUSY")
                exit(3)
            }
        }
        val error = assertThrows(DeviceFailure::class.java) { rootAccess(process).open(APK, TOKEN) }
        assertEquals(AppServer.BUSY, error.code)
        assertTrue(error.message.orEmpty().contains("exit=3"))
        assertTrue(process.stdinClosed)
    }

    @Test
    fun startupFailureKeepsItsCodeWhenRootCleanupTimesOut() {
        val process = FakeSu(exitsOnStdinClose = false) {
            if (lines.size == 1) {
                emit(AppServer.ROOT_STDIN_READY)
            } else {
                emit("M7A_APP_BUSY")
            }
        }
        val failure = assertThrows(DeviceFailure::class.java) { rootAccess(process).open(APK, TOKEN) }
        assertEquals(AppServer.BUSY, failure.code)
        val cleanup = failure.suppressed.single() as DeviceFailure
        assertEquals("cleanup_pending", cleanup.code)
        assertTrue(cleanup.message.orEmpty().contains("等待 Root 设备端服务退出超时"))
        assertTrue(process.stdinClosed)
    }

    @Test
    fun audioRecoveryUsesItsOwnEntryWithoutStartingATask() {
        val process = FakeSu { line ->
            assertEquals("exec '$QUOTED_LAUNCHER' --root '$APK' --recover-audio", line)
            exit(0)
        }
        rootAccess(process).recoverAudio(APK)
        assertEquals(1, process.lines.size)
        assertTrue(process.stdinClosed)
    }

    @Test
    fun audioRecoveryFailureIsReportedToTheCaller() {
        val process = FakeSu {
            emit("audio restore failed")
            exit(3)
        }
        val failure = assertThrows(DeviceFailure::class.java) { rootAccess(process).recoverAudio(APK) }
        assertEquals("cleanup_pending", failure.code)
        assertTrue(failure.message.orEmpty().contains("audio restore failed"))
    }

    private fun rootAccess(process: FakeSu) = RootAccess(LAUNCHER, startProcess = { argv ->
        assertEquals(listOf("su", "0"), argv)
        process
    }, warn = {})

    private class FakeSu(
        private val exitsOnStdinClose: Boolean = true,
        private val onInput: FakeSu.(String) -> Unit,
    ) : Process() {
        val lines = mutableListOf<String>()
        var stdinClosed = false
            private set
        private val output = PipedOutputStream()
        private val fromSu = PipedInputStream(output)
        private val exited = CountDownLatch(1)
        private var code = 0
        private val toSu = object : ByteArrayOutputStream() {
            override fun flush() {
                val line = toString(Charsets.UTF_8).removeSuffix("\n")
                reset()
                lines.add(line)
                onInput(line)
            }

            override fun close() {
                stdinClosed = true
                if (exitsOnStdinClose) exit(0)
            }
        }

        fun emit(vararg lines: String) {
            output.write(lines.joinToString("\n", postfix = "\n").toByteArray(Charsets.UTF_8))
            output.flush()
        }

        fun exit(status: Int) {
            if (exited.count == 0L) return
            code = status
            output.close()
            exited.countDown()
        }

        override fun getInputStream() = fromSu
        override fun getOutputStream() = toSu
        override fun getErrorStream(): InputStream = InputStream.nullInputStream()
        override fun waitFor(): Int {
            exited.await()
            return code
        }
        override fun waitFor(timeout: Long, unit: TimeUnit) =
            if (stdinClosed && !exitsOnStdinClose) !isAlive else exited.await(timeout, unit)
        override fun exitValue(): Int {
            if (exited.count != 0L) throw IllegalThreadStateException()
            return code
        }
        override fun destroy() = exit(143)
    }

    private companion object {
        val LAUNCHER = File("/data/app/it's here/lib/libm7a_launcher.so")
        val QUOTED_LAUNCHER = LAUNCHER.absolutePath.replace("'", "'\\''")
        const val APK = "/data/app/base.apk"
        const val TOKEN = "test-token-for-stdin-only"
    }
}
