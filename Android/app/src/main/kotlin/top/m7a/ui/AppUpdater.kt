package top.m7a.ui

import android.content.Context
import kotlinx.coroutines.flow.StateFlow
import top.m7a.R
import java.time.Instant
import java.time.LocalDate

internal enum class UpdateSource(val title: Int, val openLabel: Int, val pageUrl: String) {
    GITHUB(
        R.string.update_github, R.string.update_open_github,
        "https://github.com/moesnow/March7thAssistant/releases",
    ),
    MIRROR(
        R.string.update_mirror, R.string.update_open_mirror,
        "https://mirrorchyan.com/zh/projects?rid=March7thAssistant&os=android",
    ),
}

internal fun releasePageUrl(version: String): String = "${UpdateSource.GITHUB.pageUrl}/tag/${encodeVersion(version)}"

internal enum class UpdateChannel(val title: Int) {
    STABLE(R.string.update_channel_stable),
    BETA(R.string.update_channel_beta),
    ;

    val includesPrerelease: Boolean get() = this == BETA
    val mirrorQuery: String get() = if (includesPrerelease) "beta" else "stable"
}

internal data class UpdateRelease(
    val version: String,
    val publishedOn: LocalDate?,
    val notes: String,
    val sizeBytes: Long?,
    val sha256: String? = null,
)

internal sealed interface UpdateState {
    data object Idle : UpdateState
    data object Checking : UpdateState
    data object CheckFailed : UpdateState
    data object NoAndroidRelease : UpdateState
    data class Latest(val release: UpdateRelease?) : UpdateState
    data class Available(
        val release: UpdateRelease,
        val packageState: UpdatePackageState = UpdatePackageState.Idle,
    ) : UpdateState
}

internal sealed interface UpdatePackageState {
    data object Idle : UpdatePackageState
    data object Connecting : UpdatePackageState
    data class Downloading(val receivedBytes: Long, val totalBytes: Long?) : UpdatePackageState
    data object Verifying : UpdatePackageState
    data object Cancelling : UpdatePackageState
    data class DownloadFailed(val source: UpdateSource?, val problem: UpdateProblem = UpdateProblem.NETWORK) : UpdatePackageState
    data class Ready(val installStatus: InstallStatus = InstallStatus.READY) : UpdatePackageState
}

internal val UpdatePackageState?.busy: Boolean
    get() = this == UpdatePackageState.Connecting || this is UpdatePackageState.Downloading ||
        this == UpdatePackageState.Verifying || this == UpdatePackageState.Cancelling

internal enum class InstallStatus { READY, PERMISSION_REQUIRED, OPENED, FAILED }

internal enum class UpdateProblem(val text: Int, val needsNewCdk: Boolean = false) {
    NETWORK(R.string.update_download_failed),
    PACKAGE(R.string.update_bad_package),
    SPACE(R.string.update_space_required),
    MIRROR_UNAVAILABLE(R.string.update_mirror_unavailable),
    MIRROR_VERSION(R.string.update_mirror_version),
    CDK_EXPIRED(R.string.update_cdk_expired, true),
    CDK_INVALID(R.string.update_cdk_invalid, true),
    CDK_QUOTA(R.string.update_cdk_quota),
    CDK_MISMATCH(R.string.update_cdk_mismatch, true),
    CDK_BLOCKED(R.string.update_cdk_blocked, true),
}

/** 查询确定目标版本，切换下载来源时继续使用同一版本的公告。 */
internal interface UpdateChecker {
    val snapshot: StateFlow<UpdateSnapshot>
    fun check(automatic: Boolean = false)
    fun selectChannel(channel: UpdateChannel)
}

internal interface AppUpdater : UpdateChecker {
    suspend fun loadHistory(installedVersion: String, release: UpdateRelease, includePrerelease: Boolean): UpdateHistory =
        GitHubUpdateHistory.load(installedVersion, release, includePrerelease)

    suspend fun queryCdkExpiry(cdk: String): Instant = queryMirrorCdkExpiry(cdk)

    fun onCdkChanged()
    fun download(source: UpdateSource, cdk: String?)
    fun cancelDownload()
    fun install(context: Context)
}
