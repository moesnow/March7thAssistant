package top.m7a.ui

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class UpdateCheckTest {
    @Test
    fun stableOnlyOffersPublishedAndroidStableReleases() {
        val entries = listOf(
            AndroidRelease(null, draft = false, prerelease = false),
            candidate("v2026.11.15", draft = true),
            candidate("v2026.11.14-beta"),
            candidate("v2026.11.11", prerelease = true),
            candidate("v2026.10.31"),
            candidate("v2026.11.8"),
        )

        assertEquals("v2026.11.8", selectAndroidRelease(entries, UpdateChannel.STABLE)?.version)
        assertEquals("v2026.11.14-beta", selectAndroidRelease(entries, UpdateChannel.BETA)?.version)
    }

    @Test
    fun betaAlsoOffersNewerStableVersion() {
        val entries = listOf(candidate("v2026.11.9-beta", prerelease = true), candidate("v2026.11.10"))

        assertEquals("v2026.11.10", selectAndroidRelease(entries, UpdateChannel.BETA)?.version)
    }

    @Test(timeout = 5000)
    fun switchingChannelCancelsPreviousCheckAndPersistsChoice() = runBlocking {
        val enteredStable = CompletableDeferred<Unit>()
        val stableResponse = CompletableDeferred<UpdateRelease>()
        val checks = mutableListOf<UpdateChannel>()
        val saved = mutableListOf<UpdateChannel>()
        val checker = UpdateCheckController(
            scope = this,
            initialChannel = UpdateChannel.STABLE,
            installedVersion = "v2026.11.7",
            findRelease = {
                checks += it
                if (it == UpdateChannel.STABLE) {
                    enteredStable.complete(Unit)
                    stableResponse.await()
                } else release("v2026.11.9-beta")
            },
            saveChannel = { saved += it },
        )

        checker.check(automatic = true)
        enteredStable.await()
        checker.check()
        checker.selectChannel(UpdateChannel.BETA)
        stableResponse.complete(release("v2026.11.8"))
        val result = checker.snapshot.first { it.state is UpdateState.Available }

        assertEquals(UpdateChannel.BETA, result.channel)
        assertEquals("v2026.11.9-beta", result.detectedVersion)
        assertEquals(listOf(UpdateChannel.STABLE, UpdateChannel.BETA), checks)
        assertEquals(listOf(UpdateChannel.BETA), saved)
    }

    @Test(timeout = 5000)
    fun offlineStartupKeepsPreviouslyDetectedVersion() = runBlocking {
        val checker = UpdateCheckController(
            scope = this,
            initialChannel = UpdateChannel.STABLE,
            installedVersion = "v2026.11.7",
            initialDetectedVersion = "v2026.11.8",
            findRelease = { error("offline") },
            saveChannel = {},
            saveDetectedVersion = { error("An unsuccessful check must not overwrite the cached version") },
        )
        checker.check(automatic = true)

        assertEquals("v2026.11.8", checker.snapshot.first { it.state == UpdateState.CheckFailed }.detectedVersion)
    }

    @Test(timeout = 5000)
    fun switchingToStableKeepsInstalledBetaWhenStableIsOlder() = runBlocking {
        val checker = UpdateCheckController(
            scope = this,
            initialChannel = UpdateChannel.BETA,
            installedVersion = "v2026.11.9-beta",
            initialDetectedVersion = "v2026.11.9-beta",
            findRelease = { release("v2026.11.8") },
            saveChannel = {},
        )
        assertNull(checker.snapshot.value.detectedVersion)
        checker.selectChannel(UpdateChannel.STABLE)

        val result = checker.snapshot.first { it.state is UpdateState.Latest }
        assertEquals(UpdateState.Latest(null), result.state)
        assertNull(result.detectedVersion)
    }

    private fun candidate(version: String, draft: Boolean = false, prerelease: Boolean = false) =
        AndroidRelease(release(version), draft, prerelease)

    private fun release(version: String) = UpdateRelease(version, null, "", null)
}
