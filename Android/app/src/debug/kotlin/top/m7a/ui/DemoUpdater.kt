package top.m7a.ui

import android.content.Intent
import android.content.Context
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.platform.LocalContext
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import top.m7a.UpdatePreferences
import java.io.IOException
import java.time.Instant
import java.time.LocalDate
import java.time.temporal.ChronoUnit

/** adb shell am start … --es demo ready --es tab SETTINGS --es page UPDATE --es update available */
@Composable
internal fun rememberDemoUpdater(intent: Intent, preferences: UpdatePreferences): AppUpdater {
    val scene = intent.getStringExtra("update") ?: "idle"
    val scope = rememberCoroutineScope()
    val assets = LocalContext.current.assets
    return remember(scene, scope, assets, preferences) {
        val changelog = assets.open("Changelog.md").bufferedReader(Charsets.UTF_8).useLines { lines ->
            lines.dropWhile { it != "## $BETA_VERSION" }.joinToString("\n")
        }
        fun release(version: String, day: Int) = UpdateRelease(
            version, LocalDate.of(2026, 11, day),
            changelog.lineSequence().dropWhile { it != "## $version" }.drop(1)
                .takeWhile { !it.startsWith("## ") }.joinToString("\n").trim(),
            187_600_000,
        )
        val stable = release(STABLE_VERSION, 8)
        val beta = release(BETA_VERSION, 9)
        val installedVersion = demoInstalledVersion(scene)
        val update = if (preferences.channel.includesPrerelease) beta else stable
        val checker = UpdateCheckController(
            scope = scope,
            initialChannel = preferences.channel,
            installedVersion = installedVersion,
            findRelease = { channel ->
                delay(750)
                when (scene) {
                    "offline" -> throw IOException("演示更新检查失败")
                    "latest" -> stable.copy(version = installedVersion)
                    else -> if (channel.includesPrerelease) beta else stable
                }
            },
            saveChannel = { preferences.channel = it },
            initialState = when (scene) {
                "available", "history", "history-error", "history-partial", "history-many", "history-live" ->
                    UpdateState.Available(update)
                "failed" -> UpdateState.CheckFailed
                "latest" -> UpdateState.Latest(null)
                "ready" -> UpdateState.Available(update, UpdatePackageState.Ready())
                else -> UpdateState.Idle
            },
        )
        if (scene == "discovery") checker.check(automatic = true)
        DemoUpdater(scene, scope, checker, changelog)
    }
}

private const val STABLE_VERSION = "v2026.11.8"
private const val BETA_VERSION = "v2026.11.9-beta"

internal fun demoInstalledVersion(scene: String): String = when (scene) {
    "discovery", "history", "history-error", "history-partial", "history-live" -> "v2026.10.16"
    "history-many" -> "v2026.1.19"
    else -> "v2026.11.7"
}

private class DemoUpdater(
    private val scene: String,
    private val scope: CoroutineScope,
    private val checker: UpdateCheckController,
    private val changelog: String,
) : AppUpdater, UpdateChecker by checker {
    private var transfer: Job? = null

    override suspend fun loadHistory(installedVersion: String, release: UpdateRelease, includePrerelease: Boolean): UpdateHistory {
        if (scene == "history-live") return super.loadHistory(installedVersion, release, includePrerelease)
        delay(600)
        if (scene == "history-error") throw IOException("演示历史更新记录请求失败")
        return withContext(Dispatchers.Default) {
            val fromTarget = changelog.lineSequence().dropWhile { it != "## ${release.version}" }.joinToString("\n")
            val document = if (scene == "history-partial") fromTarget.substringBefore("\n## $installedVersion\n") else fromTarget
            collectUpdateHistory(document, installedVersion, release, includePrerelease)
        }
    }

    override suspend fun queryCdkExpiry(cdk: String): Instant {
        if (scene == "cdk-live") return super.queryCdkExpiry(cdk)
        delay(500)
        if (cdk == "PREVIEW-EXPIRED") throw MirrorCdkError(7001)
        return Instant.now().plus(26, ChronoUnit.DAYS).plusSeconds(60)
    }

    override fun onCdkChanged() {
        val available = snapshot.value.state as? UpdateState.Available ?: return
        val failed = available.packageState as? UpdatePackageState.DownloadFailed
        if (failed?.source == UpdateSource.MIRROR && failed.problem.needsNewCdk) {
            checker.updatePackageState(UpdatePackageState.Idle)
        }
    }

    override fun download(source: UpdateSource, cdk: String?) {
        if (transfer?.isActive == true) return
        val available = snapshot.value.state as? UpdateState.Available ?: return
        if (source == UpdateSource.MIRROR && (cdk.isNullOrBlank() || cdk == "PREVIEW-EXPIRED")) {
            checker.updatePackageState(UpdatePackageState.DownloadFailed(UpdateSource.MIRROR, UpdateProblem.CDK_EXPIRED))
            return
        }
        val total = checkNotNull(available.release.sizeBytes)
        checker.updatePackageState(UpdatePackageState.Downloading(0, total))
        transfer = scope.launch {
            if (scene == "download-failed") {
                delay(600)
                checker.updatePackageState(UpdatePackageState.DownloadFailed(source))
                return@launch
            }
            for (tick in 1..20) {
                delay(500)
                checker.updatePackageState(UpdatePackageState.Downloading(total * tick / 20, total))
            }
            checker.updatePackageState(UpdatePackageState.Verifying)
            delay(900)
            checker.updatePackageState(UpdatePackageState.Ready())
        }
    }

    override fun cancelDownload() {
        transfer?.cancel()
        checker.updatePackageState(UpdatePackageState.Idle)
    }

    override fun install(context: Context) {
        checker.updatePackageState(UpdatePackageState.Ready(InstallStatus.OPENED))
    }
}
