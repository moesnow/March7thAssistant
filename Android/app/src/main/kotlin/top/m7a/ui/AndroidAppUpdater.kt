package top.m7a.ui

import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.core.content.FileProvider
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import top.m7a.TaskController
import java.io.File
import java.net.URI
import javax.net.ssl.HttpsURLConnection

class UpdateApkProvider : FileProvider()

internal fun apkInstallIntent(context: Context, apk: File): Intent {
    val uri = FileProvider.getUriForFile(context, "${context.packageName}.update-apk", apk)
    return Intent(Intent.ACTION_VIEW).apply {
        setDataAndType(uri, "application/vnd.android.package-archive")
        clipData = ClipData.newRawUri(apk.name, uri)
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }
}

internal fun unknownApkSourcesIntent(context: Context) =
    Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.fromParts("package", context.packageName, null))

internal class AndroidAppUpdater(
    private val scope: CoroutineScope,
    private val checker: UpdateCheckController,
    private val packages: UpdateApkStore,
    private val resolveApk: suspend (UpdateChannel, UpdateRelease, UpdateSource, String?) -> ApkDownload = ::resolveUpdateApk,
    private val openConnection: (URI) -> HttpsURLConnection = ::openApkConnection,
) : AppUpdater, UpdateChecker by checker {
    private var transfer: Job? = null

    override fun onCdkChanged() {
        val failed = (snapshot.value.state as? UpdateState.Available)?.packageState as? UpdatePackageState.DownloadFailed
        if (failed?.source == UpdateSource.MIRROR && failed.problem.needsNewCdk) {
            checker.updatePackageState(UpdatePackageState.Idle)
        }
    }

    override fun download(source: UpdateSource, cdk: String?) {
        val update = snapshot.value
        val available = update.state as? UpdateState.Available ?: return
        if (available.packageState.busy || available.packageState is UpdatePackageState.Ready) return
        checker.updatePackageState(UpdatePackageState.Connecting)
        transfer = scope.launch {
            val result = try {
                val release = available.release
                val apk = resolveApk(update.channel, release, source, cdk)
                packages.download(release, apk, source, openConnection) { state ->
                    withContext(Dispatchers.Main.immediate) { checker.updatePackageState(state) }
                }
                UpdatePackageState.Ready()
            } catch (error: CancellationException) {
                throw error
            } catch (error: MirrorCdkError) {
                UpdatePackageState.DownloadFailed(source, error.updateProblem())
            } catch (error: UpdateException) {
                UpdatePackageState.DownloadFailed(source, error.problem)
            } catch (_: Exception) {
                UpdatePackageState.DownloadFailed(source)
            }
            ensureActive()
            checker.updatePackageState(result)
        }
    }

    override fun cancelDownload() {
        val job = transfer ?: return
        val phase = (snapshot.value.state as? UpdateState.Available)?.packageState
        if (!job.isActive || !phase.busy || phase == UpdatePackageState.Cancelling) return
        checker.updatePackageState(UpdatePackageState.Cancelling)
        scope.launch {
            job.cancelAndJoin()
            checker.updatePackageState(UpdatePackageState.Idle)
        }
    }

    override fun install(context: Context) {
        val available = snapshot.value.state as? UpdateState.Available ?: return
        if (available.packageState !is UpdatePackageState.Ready || TaskController.get(context).state.value.busy) return
        val manager = context.packageManager
        try {
            if (!manager.canRequestPackageInstalls()) {
                context.startActivity(unknownApkSourcesIntent(context))
                checker.updatePackageState(UpdatePackageState.Ready(InstallStatus.PERMISSION_REQUIRED))
                return
            }
        } catch (_: Exception) {
            checker.updatePackageState(UpdatePackageState.Ready(InstallStatus.FAILED))
            return
        }

        checker.updatePackageState(UpdatePackageState.Verifying)
        scope.launch {
            val apk = try {
                packages.verifiedApk(available.release)
            } catch (error: CancellationException) {
                throw error
            } catch (_: Exception) {
                checker.updatePackageState(UpdatePackageState.DownloadFailed(null, UpdateProblem.PACKAGE))
                return@launch
            }
            if (TaskController.get(context).state.value.busy) {
                checker.updatePackageState(UpdatePackageState.Ready())
                return@launch
            }
            val status = try {
                context.startActivity(apkInstallIntent(context, apk))
                InstallStatus.OPENED
            } catch (_: Exception) {
                InstallStatus.FAILED
            }
            checker.updatePackageState(UpdatePackageState.Ready(status))
        }
    }
}

private suspend fun resolveUpdateApk(
    channel: UpdateChannel, release: UpdateRelease, source: UpdateSource, cdk: String?,
): ApkDownload {
    val expected = githubApkDownload(release)
    return if (source == UpdateSource.GITHUB) expected else mirrorApkDownload(channel, release, cdk.orEmpty())
}
