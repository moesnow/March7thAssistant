package top.m7a

import android.os.IBinder
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertSame
import org.junit.Assert.assertThrows
import org.junit.Test
import java.lang.reflect.Proxy

class DeviceAccessTest {
    @Test
    fun closesServiceAndUnlinksTheRegisteredListener() {
        val service = ServiceBinder()
        closeUserService(service.binder, timeoutMs = 0, destroy = service::reportDeath)
        assertEquals(1, service.unlinks)
    }

    @Test
    fun doesNotRegisterOrUnlinkWhenServiceIsAlreadyDead() {
        val service = ServiceBinder(alive = false)
        closeUserService(service.binder, timeoutMs = 0) { error("unexpected destroy") }
        assertEquals(0, service.links)
        assertEquals(0, service.unlinks)
    }

    @Test
    fun failedRegistrationDoesNotUnlinkOrHideItsError() {
        val failure = SecurityException("link failed")
        val service = ServiceBinder(linkFailure = failure)
        val error = assertThrows(SecurityException::class.java) {
            closeUserService(service.binder, timeoutMs = 0) { error("unexpected destroy") }
        }
        assertSame(failure, error)
        assertEquals(1, service.links)
        assertEquals(0, service.unlinks)
    }

    @Test
    fun missingListenerIsHarmlessAfterShutdownWasConfirmed() {
        val service = ServiceBinder(unlinkFailure = NoSuchElementException())
        closeUserService(service.binder, timeoutMs = 0, destroy = service::reportDeath)
        assertEquals(1, service.unlinks)
    }

    @Test
    fun missingListenerDoesNotHideARealShutdownTimeout() {
        val service = ServiceBinder(unlinkFailure = NoSuchElementException())
        val error = assertThrows(DeviceFailure::class.java) {
            closeUserService(service.binder, timeoutMs = 0) {}
        }
        assertEquals("cleanup_pending", error.code)
        assertEquals("cleanup_pending (等待 Shizuku 设备端服务退出超时)", error.message)
        assertEquals(1, service.unlinks)
    }

    @Test
    fun exceptionFromDestroyIsNotTreatedAsAMissingListener() {
        val failure = NoSuchElementException("destroy failed")
        val service = ServiceBinder(unlinkFailure = NoSuchElementException())
        val error = assertThrows(NoSuchElementException::class.java) {
            closeUserService(service.binder, timeoutMs = 0) { throw failure }
        }
        assertSame(failure, error)
        assertEquals(1, service.unlinks)
    }

    @Test
    fun shutdownTimeoutAndStartupTimeoutAreReportedSeparately() {
        val service = ServiceBinder(unlinkFailure = NoSuchElementException())
        val errors = mutableListOf<Throwable>()
        val cleanup = TaskCleanup { errors.add(it) }
        val result = cleanup.finish("game_start_timeout") {
            closeUserService(service.binder, timeoutMs = 0) {}
        }
        assertEquals("game_start_timeout", result)
        assertFalse(cleanup.confirmed)
        assertEquals("cleanup_pending", (errors.single() as DeviceFailure).code)
    }

    private class ServiceBinder(
        alive: Boolean = true,
        linkFailure: Exception? = null,
        unlinkFailure: Exception? = null,
    ) {
        var links = 0
            private set
        var unlinks = 0
            private set
        private var listener: IBinder.DeathRecipient? = null

        val binder = Proxy.newProxyInstance(
            IBinder::class.java.classLoader, arrayOf(IBinder::class.java),
        ) { _, method, args ->
            when (method.name) {
                "isBinderAlive" -> alive
                "linkToDeath" -> {
                    links++
                    linkFailure?.let { throw it }
                    listener = args[0] as IBinder.DeathRecipient
                    null
                }
                "unlinkToDeath" -> {
                    unlinks++
                    assertSame(listener, args[0])
                    listener = null
                    unlinkFailure?.let { throw it }
                    true
                }
                else -> error("unexpected Binder call ${method.name}")
            }
        } as IBinder

        fun reportDeath() = checkNotNull(listener).binderDied()
    }
}
