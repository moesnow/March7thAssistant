package top.m7a

import org.junit.Assert.*
import org.junit.Test
import java.io.File
import java.io.FilterOutputStream
import java.util.concurrent.CompletableFuture
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger

class ShizukuAccessTest {
    private val token = "one-shot-secret-for-protocol"
    private val java = ProcessHandle.current().info().command().orElseThrow()

    private fun child(mode: String): Process {
        val classes = File(checkNotNull(DeviceProcessFixture::class.java.protectionDomain).codeSource.location.toURI())
        return ProcessBuilder(java, "-cp", classes.path, DeviceProcessFixture::class.java.name, mode).start()
    }

    @Test
    fun onlyTheInstalledLauncherAndApkAreArgumentsForEitherUid() {
        val launcher = File(java)
        val apk = "/data/app/a 'quoted' path & more/base.apk"
        for (uid in listOf(2000, 0)) {
            assertArrayEquals(arrayOf(launcher.absolutePath, apk), shizukuLaunchArgs(13, uid, launcher, apk, false))
            assertArrayEquals(arrayOf(launcher.absolutePath, apk, "--recover-audio"), shizukuLaunchArgs(13, uid, launcher, apk, true))
        }
        for ((api, uid) in listOf(14 to 2000, 13 to 10001)) {
            assertEquals("shizuku_unsupported", assertThrows(DeviceFailure::class.java) {
                shizukuLaunchArgs(api, uid, launcher, apk, false)
            }.code)
        }
        assertEquals("service_start", assertThrows(DeviceFailure::class.java) {
            shizukuLaunchArgs(13, 2000, File(launcher, "missing"), apk, false)
        }.code)
    }

    @Test
    fun stderrFloodCannotBlockOrAnnounceAnEndpointAndNextStartWaitsForExit() {
        val count = AtomicInteger()
        val access = ShizukuAccess({ recovery ->
            count.incrementAndGet()
            child(if (recovery) "audio" else "stderr")
        }, {})
        access.open(token).use {
            assertEquals(4321, it.port)
            assertEquals("cleanup_pending", assertThrows(DeviceFailure::class.java) { access.open("next") }.code)
            assertEquals("cleanup_pending", assertThrows(DeviceFailure::class.java) { access.recoverAudio() }.code)
            assertEquals(1, count.get())
        }
        access.recoverAudio()
        access.open("next").close()
        assertEquals(3, count.get())
    }

    @Test
    fun observesEarlyExitBusyAndMalformedPortWithoutTryingAnotherRoute() {
        for ((mode, detail) in listOf("early-exit" to "exit=126", "busy" to "service_busy", "invalid-port" to "有效监听端口")) {
            val proc = child(mode)
            val failure = assertThrows(DeviceFailure::class.java) { ShizukuAccess({ proc }, {}).open(token) }
            assertEquals(if (mode == "busy") "service_busy" else "service_start", failure.code)
            assertTrue(failure.message.orEmpty(), failure.message.orEmpty().contains(detail))
            assertFalse(failure.message.orEmpty().contains(token))
            if (mode == "invalid-port") assertTrue(failure.message.orEmpty().contains("[已脱敏]"))
            assertFalse(proc.isAlive)
        }
    }

    @Test
    fun anUnconfirmedExitBlocksAnyNewLauncherUntilTheOriginalProcessIsGone() {
        val child = child("normal")
        val lingering = object : Process() {
            override fun getOutputStream() = object : FilterOutputStream(child.outputStream) {
                override fun close() {} // 模拟 EOF 与终止请求均延迟。
            }
            override fun getInputStream() = child.inputStream
            override fun getErrorStream() = child.errorStream
            override fun waitFor(timeout: Long, unit: TimeUnit) = !child.isAlive
            override fun waitFor() = child.waitFor()
            override fun exitValue() = child.exitValue()
            override fun destroy() {}
        }
        val calls = AtomicInteger()
        val access = ShizukuAccess({ if (calls.incrementAndGet() == 1) lingering else child("normal") }, {})
        try {
            val lease = access.open(token)
            assertEquals("cleanup_pending", assertThrows(DeviceFailure::class.java) { lease.close() }.code)
            assertEquals("cleanup_pending", assertThrows(DeviceFailure::class.java) { access.open("new") }.code)
            assertEquals(1, calls.get())
        } finally {
            child.outputStream.close()
            child.destroy()
            assertTrue(child.waitFor(3, TimeUnit.SECONDS))
        }
        access.open("new").close()
    }

    @Test
    fun bothProtocolWaitsExpireAndReturnTheirOwnPipes() {
        for ((mode, stage) in listOf("no-ready" to "请求令牌", "no-port" to "监听端口")) {
            val proc = child(mode)
            val access = ShizukuAccess({ proc }, {}, startTimeoutMs = 1200)
            val failure = assertThrows(DeviceFailure::class.java) { access.open(token) }
            assertTrue(failure.message.orEmpty(), failure.message.orEmpty().contains("${stage}超时"))
            assertTrue(proc.waitFor(2, TimeUnit.SECONDS))
            assertEquals(0, proc.exitValue())
        }
    }

    @Test
    fun lateCreationAfterStopOrTimeoutCanOnlyReceiveEof() {
        for (stop in listOf(true, false)) {
            val entered = CountDownLatch(1)
            val permitReturn = CountDownLatch(1)
            val late = CompletableFuture<Process>()
            val reaped = CountDownLatch(1)
            val cancelled = AtomicBoolean()
            val calls = AtomicInteger()
            val access = ShizukuAccess({
                if (calls.incrementAndGet() == 1) {
                    entered.countDown()
                    check(permitReturn.await(5, TimeUnit.SECONDS))
                    child("no-ready").also(late::complete)
                } else child("normal")
            }, { if (it == "已回收迟到的 Shizuku 进程") reaped.countDown() }, startTimeoutMs = 1500)
            val outcome = CompletableFuture.supplyAsync {
                assertThrows(DeviceFailure::class.java) { access.open(token, cancelled::get) }
            }
            assertTrue(entered.await(2, TimeUnit.SECONDS))
            cancelled.set(stop)
            try {
                assertEquals(if (stop) "stopped" else "service_start", outcome.get(3, TimeUnit.SECONDS).code)
                assertEquals("cleanup_pending", assertThrows(DeviceFailure::class.java) { access.open("next") }.code)
                assertEquals(1, calls.get())
            } finally {
                permitReturn.countDown()
            }
            assertTrue(reaped.await(3, TimeUnit.SECONDS))
            assertEquals(0, late.get().exitValue())
            access.open("next").use { assertEquals(4321, it.port) }
        }
    }

    @Test
    fun permissionAndInterfaceFailuresPreserveTheirCauseAndPermitALaterStart() {
        for (code in listOf("permission_unavailable", "shizuku_unsupported", "service_start")) {
            val attempts = AtomicInteger()
            val access = ShizukuAccess({
                if (attempts.incrementAndGet() == 1) throw DeviceFailure(code, "create")
                child("normal")
            }, {})
            assertEquals(code, assertThrows(DeviceFailure::class.java) { access.open(token) }.code)
            assertEquals(1, attempts.get())
            access.open("next").close()
        }
    }
}
