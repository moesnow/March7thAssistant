package top.m7a.ui

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

internal data class UpdateSnapshot(
    val channel: UpdateChannel,
    val state: UpdateState = UpdateState.Idle,
    val detectedVersion: String? = null,
)

/** 启动检查、手动检查和切换通道共用同一份状态。由界面线程调用。 */
internal class UpdateCheckController(
    private val scope: CoroutineScope,
    initialChannel: UpdateChannel,
    private val installedVersion: String,
    private val findRelease: suspend (UpdateChannel) -> UpdateRelease?,
    private val saveChannel: (UpdateChannel) -> Unit,
    initialDetectedVersion: String? = null,
    private val saveDetectedVersion: (String?) -> Unit = {},
    initialState: UpdateState = UpdateState.Idle,
    private val restorePackage: suspend (UpdateRelease?) -> Boolean = { false },
) : UpdateChecker {
    private val installed = requireNotNull(UpdateVersion.parse(installedVersion))
    private val initialVersion = initialDetectedVersion?.takeIf { tag ->
        UpdateVersion.parse(tag)?.let { it > installed && (initialChannel.includesPrerelease || !it.isPrerelease) } == true
    }
    private val data = MutableStateFlow(
        UpdateSnapshot(initialChannel, initialState, (initialState as? UpdateState.Available)?.release?.version ?: initialVersion),
    )
    override val snapshot: StateFlow<UpdateSnapshot> = data.asStateFlow()
    private var request: Job? = null

    override fun check(automatic: Boolean) {
        val current = data.value
        if (current.state == UpdateState.Checking || request?.isActive == true) return
        if ((current.state as? UpdateState.Available)?.packageState.busy) return
        if (automatic && current.state != UpdateState.Idle) return
        val channel = current.channel
        data.update { it.copy(state = UpdateState.Checking) }
        request = scope.launch {
            val result = try {
                resultFor(findRelease(channel))
            } catch (error: CancellationException) {
                throw error
            } catch (_: Exception) {
                UpdateState.CheckFailed
            }
            ensureActive()
            val detectedVersion = when (result) {
                is UpdateState.Available -> result.release.version
                UpdateState.CheckFailed -> current.detectedVersion
                else -> null
            }
            if (result != UpdateState.CheckFailed) saveDetectedVersion(detectedVersion)
            data.value = UpdateSnapshot(channel, result, detectedVersion)
        }
    }

    override fun selectChannel(channel: UpdateChannel) {
        if (channel == data.value.channel) return
        if ((data.value.state as? UpdateState.Available)?.packageState.busy) return
        request?.cancel()
        request = null
        saveChannel(channel)
        data.value = UpdateSnapshot(channel)
        check()
    }

    fun updatePackageState(state: UpdatePackageState) {
        data.update { current ->
            val available = current.state as? UpdateState.Available ?: return@update current
            if (available.packageState == UpdatePackageState.Cancelling && state != UpdatePackageState.Idle) return@update current
            current.copy(state = available.copy(packageState = state))
        }
    }

    private suspend fun resultFor(release: UpdateRelease?): UpdateState {
        val target = release?.let { requireNotNull(UpdateVersion.parse(it.version)) }
        if (release != null && target != null && target > installed) {
            val cached = if (restorePackage(release)) UpdatePackageState.Ready() else UpdatePackageState.Idle
            return UpdateState.Available(release, cached)
        }
        restorePackage(null)
        return if (release == null) UpdateState.NoAndroidRelease else UpdateState.Latest(release.takeIf { target == installed })
    }
}
