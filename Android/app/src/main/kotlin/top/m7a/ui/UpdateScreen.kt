package top.m7a.ui

import android.text.format.Formatter
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.DialogProperties
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import top.m7a.R
import top.m7a.UpdatePreferences
import java.time.Instant

@Composable
internal fun UpdateScreen(
    installedVersion: String,
    taskBusy: Boolean,
    update: UpdateSnapshot,
    updater: AppUpdater,
    preferences: UpdatePreferences,
    openUrl: (String) -> Unit,
    onBack: () -> Unit,
) {
    val state = update.state
    val available = state as? UpdateState.Available
    val packageState = available?.packageState
    val release = available?.release ?: (state as? UpdateState.Latest)?.release
    var source by remember(preferences) { mutableStateOf(preferences.source) }
    var hasCdk by remember(preferences) { mutableStateOf(preferences.hasCdk) }
    var cdkPrompt by remember { mutableStateOf<CdkPrompt?>(null) }
    var cdkBusy by remember { mutableStateOf(false) }
    var cdkError by remember { mutableStateOf<Int?>(null) }
    var cdkQuerying by remember { mutableStateOf(false) }
    var cdkDays by remember { mutableStateOf<Int?>(null) }
    var cdkQueryError by remember { mutableStateOf<Int?>(null) }
    val scope = rememberCoroutineScope()

    fun editCdk(prompt: CdkPrompt) {
        cdkError = null
        cdkQueryError = null
        cdkDays = null
        cdkPrompt = prompt
    }

    fun updateCdk(value: String?) {
        val prompt = cdkPrompt ?: return
        if (cdkBusy) return
        cdkBusy = true
        cdkError = null
        scope.launch {
            try {
                if (value == null) preferences.removeCdk() else preferences.saveCdk(value)
                hasCdk = value != null
            } catch (error: CancellationException) {
                throw error
            } catch (_: Exception) {
                cdkError = if (value == null) R.string.update_cdk_remove_failed else R.string.update_cdk_save_failed
                return@launch
            } finally {
                cdkBusy = false
            }
            cdkPrompt = null
            updater.onCdkChanged()
            if (value != null) {
                when (prompt) {
                    CdkPrompt.EDIT -> updater.check()
                    CdkPrompt.DOWNLOAD -> updater.download(UpdateSource.MIRROR, value)
                }
            }
        }
    }

    fun queryCdk() {
        if (cdkBusy || cdkQuerying) return
        if (!hasCdk) {
            editCdk(CdkPrompt.EDIT)
            return
        }
        cdkQuerying = true
        scope.launch {
            try {
                val cdk = try {
                    preferences.readCdk()
                } catch (error: CancellationException) {
                    throw error
                } catch (_: Exception) {
                    editCdk(CdkPrompt.EDIT)
                    cdkError = R.string.update_cdk_read_failed
                    return@launch
                }
                if (cdk == null) {
                    hasCdk = false
                    editCdk(CdkPrompt.EDIT)
                    return@launch
                }
                val expiry = updater.queryCdkExpiry(cdk)
                val days = remainingCdkDays(expiry, Instant.now())
                cdkDays = days?.coerceAtMost(Int.MAX_VALUE.toLong())?.toInt()
                if (days == null) cdkQueryError = R.string.update_cdk_expired
            } catch (error: CancellationException) {
                throw error
            } catch (error: MirrorCdkError) {
                cdkQueryError = when (error.code) {
                    7001 -> R.string.update_cdk_expired
                    7002 -> R.string.update_cdk_invalid
                    7003 -> R.string.update_cdk_quota
                    7004 -> R.string.update_cdk_mismatch
                    7005 -> R.string.update_cdk_blocked
                    else -> R.string.update_cdk_query_failed
                }
            } catch (_: Exception) {
                cdkQueryError = R.string.update_cdk_query_failed
            } finally {
                cdkQuerying = false
            }
        }
    }

    fun download() {
        if (cdkBusy || packageState.busy) return
        val failed = packageState as? UpdatePackageState.DownloadFailed
        if (source == UpdateSource.GITHUB) {
            updater.download(UpdateSource.GITHUB, null)
            return
        }
        if (!hasCdk || (failed?.source == UpdateSource.MIRROR && failed.problem.needsNewCdk)) {
            editCdk(CdkPrompt.DOWNLOAD)
            return
        }
        cdkBusy = true
        scope.launch {
            val value = try {
                preferences.readCdk()
            } catch (error: CancellationException) {
                throw error
            } catch (_: Exception) {
                editCdk(CdkPrompt.DOWNLOAD)
                cdkError = R.string.update_cdk_read_failed
                return@launch
            } finally {
                cdkBusy = false
            }
            if (value == null) {
                hasCdk = false
                editCdk(CdkPrompt.DOWNLOAD)
            } else {
                updater.download(UpdateSource.MIRROR, value)
            }
        }
    }

    Column(Modifier.fillMaxSize()) {
        SubPageBar(tr(R.string.update_title), onBack)
        Column(
            Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            UpdateVersionCard(installedVersion, state)
            when (state) {
                UpdateState.CheckFailed -> {
                    val lastDetected = update.detectedVersion
                    val message = if (lastDetected == null) tr(R.string.update_check_failed)
                    else tr(R.string.update_check_failed_cached, lastDetected)
                    Notice(message, Modifier.semantics { liveRegion = LiveRegionMode.Polite }, Tone.ERROR)
                }
                UpdateState.NoAndroidRelease -> Notice(
                    tr(R.string.update_no_android_release), Modifier.semantics { liveRegion = LiveRegionMode.Polite },
                )
                else -> Unit
            }
            PanelCard {
                Text(tr(R.string.update_channel), style = MaterialTheme.typography.titleMedium)
                Segmented(
                    UpdateChannel.entries.map { it to tr(it.title) }, update.channel, updater::selectChannel,
                    modifier = Modifier.padding(top = 10.dp),
                    enabled = !cdkBusy && !packageState.busy,
                )
                if (update.channel == UpdateChannel.BETA) {
                    BodyText(tr(R.string.update_channel_beta_detail), Modifier.padding(top = 8.dp))
                }
            }
            if (packageState !is UpdatePackageState.Ready) {
                UpdateSourcePicker(
                    source = source,
                    select = {
                        source = it
                        preferences.source = it
                    },
                    hasCdk = hasCdk,
                    editCdk = { editCdk(CdkPrompt.EDIT) },
                    packageState = packageState,
                    cdkBusy = cdkBusy,
                    queryCdk = ::queryCdk,
                    openUrl = openUrl,
                )
            }
            if (release != null && (available != null || release.notes.isNotBlank())) {
                UpdateNotes(
                    release = release,
                    installedVersion = installedVersion,
                    includePrerelease = update.channel.includesPrerelease,
                    loadHistory = available != null,
                    updater = updater,
                    openUrl = openUrl,
                )
            }
        }

        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        Column(
            Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            val githubUrl = (release?.version ?: update.detectedVersion)?.let(::releasePageUrl) ?: UpdateSource.GITHUB.pageUrl
            val mirrorUrl = "${UpdateSource.MIRROR.pageUrl}&channel=${update.channel.mirrorQuery}"
            val selectedUrl = if (source == UpdateSource.GITHUB) githubUrl else mirrorUrl
            val context = LocalContext.current
            if (available != null) {
                PackageAction(
                    available, source, taskBusy, cdkBusy, updater::cancelDownload,
                    install = { updater.install(context) }, download = ::download,
                )
                TextButton(onClick = { openUrl(githubUrl) }) { Text(tr(R.string.update_open_github)) }
            } else {
                val checking = state == UpdateState.Checking
                BigActionButton(
                    tr(if (checking) R.string.update_checking else R.string.update_check),
                    { updater.check() }, enabled = !checking, loading = checking,
                )
                if (source == UpdateSource.GITHUB || update.detectedVersion != null) {
                    TextButton(onClick = { openUrl(githubUrl) }) { Text(tr(R.string.update_open_github)) }
                } else {
                    TextButton(onClick = { openUrl(selectedUrl) }) { Text(tr(source.openLabel)) }
                }
            }
        }
    }

    val prompt = cdkPrompt
    if (prompt != null) {
        CdkDialog(prompt, hasCdk, cdkBusy, cdkError, { cdkPrompt = null }, ::updateCdk)
    }
    if (cdkQuerying || cdkDays != null || cdkQueryError != null) {
        val dismiss = {
            if (!cdkQuerying) {
                cdkDays = null
                cdkQueryError = null
            }
        }
        AlertDialog(
            onDismissRequest = dismiss,
            title = { Text(tr(R.string.update_cdk_days)) },
            text = {
                if (cdkQuerying) {
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                        BodyText(tr(R.string.update_cdk_querying))
                    }
                } else {
                    val error = cdkQueryError
                    val days = cdkDays ?: 0
                    BodyText(when {
                        error != null -> tr(error)
                        days == 0 -> tr(R.string.update_cdk_expires_today)
                        else -> pluralStringResource(R.plurals.update_cdk_remaining, days, days)
                    })
                }
            },
            confirmButton = {
                TextButton(onClick = dismiss, enabled = !cdkQuerying) { Text(tr(R.string.confirm)) }
            },
        )
    }
}

@Composable
private fun UpdateVersionCard(installedVersion: String, state: UpdateState) {
    val available = state as? UpdateState.Available
    val scheme = MaterialTheme.colorScheme
    val brand = LocalBrand.current
    val label = when (state) {
        is UpdateState.Available -> R.string.update_available
        is UpdateState.Latest -> if (state.release == null) R.string.update_no_newer_release else R.string.update_latest
        else -> R.string.update_current
    }
    Column(
        Modifier.fillMaxWidth().clip(MaterialTheme.shapes.large)
            .background(Brush.horizontalGradient(listOf(brand.heroStart, brand.heroEnd)))
            .padding(horizontal = 20.dp, vertical = 18.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(tr(label), style = MaterialTheme.typography.labelLarge, color = scheme.primary)
        Text(available?.release?.version ?: installedVersion, style = MaterialTheme.typography.headlineMedium)
        if (available != null) BodyText(tr(R.string.update_installed, installedVersion))
    }
}

@Composable
private fun UpdateSourcePicker(
    source: UpdateSource,
    select: (UpdateSource) -> Unit,
    hasCdk: Boolean,
    editCdk: () -> Unit,
    packageState: UpdatePackageState?,
    cdkBusy: Boolean,
    queryCdk: () -> Unit,
    openUrl: (String) -> Unit,
) {
    val transferring = packageState.busy
    val mirror = source == UpdateSource.MIRROR
    PanelCard {
        Text(tr(R.string.update_source), style = MaterialTheme.typography.titleMedium)
        BodyText(tr(R.string.update_same_package), Modifier.padding(top = 2.dp))
        Segmented(
            UpdateSource.entries.map { it to tr(it.title) }, source, select,
            modifier = Modifier.padding(top = 10.dp), enabled = !transferring && !cdkBusy,
        )
        Column(Modifier.padding(top = 12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(
                tr(if (mirror) R.string.update_mirror_benefit else R.string.update_github_benefit),
                style = MaterialTheme.typography.titleMedium,
            )
            BodyText(tr(if (mirror) R.string.update_mirror_detail else R.string.update_github_detail))
        }
        if (mirror && !transferring) {
            HorizontalDivider(Modifier.padding(top = 12.dp), color = MaterialTheme.colorScheme.outlineVariant)
            Row(Modifier.fillMaxWidth().padding(top = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                BodyText(tr(if (hasCdk) R.string.update_cdk_saved else R.string.update_cdk_unset), Modifier.weight(1f))
                TextButton(onClick = editCdk, enabled = !cdkBusy) {
                    Text(tr(if (hasCdk) R.string.update_cdk_manage else R.string.update_cdk_add))
                }
            }
            FlowRow(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(4.dp, Alignment.CenterHorizontally),
            ) {
                TextButton(onClick = { openUrl("https://mirrorchyan.com/?source=m7a-app") }) { Text(tr(R.string.update_cdk_get)) }
                TextButton(onClick = queryCdk, enabled = !cdkBusy) { Text(tr(R.string.update_cdk_days)) }
                TextButton(onClick = { openUrl("https://pd.qq.com/g/MirrorChyan") }) { Text(tr(R.string.update_mirror_feedback)) }
            }
            Text(
                tr(R.string.update_mirror_support), Modifier.padding(top = 4.dp),
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun PackageAction(
    available: UpdateState.Available,
    source: UpdateSource,
    taskBusy: Boolean,
    cdkBusy: Boolean,
    cancel: () -> Unit,
    install: () -> Unit,
    download: () -> Unit,
) {
    when (val state = available.packageState) {
        UpdatePackageState.Connecting -> {
            BodyText(tr(R.string.update_preparing_download))
            LinearProgressIndicator(Modifier.fillMaxWidth())
            TextButton(onClick = cancel) { Text(tr(R.string.update_cancel_download)) }
        }
        is UpdatePackageState.Downloading -> {
            val total = state.totalBytes?.takeIf { it > 0 }
            val received = fileSize(state.receivedBytes)
            val progress = if (total == null) received else tr(R.string.update_progress, received, fileSize(total))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(tr(R.string.update_downloading), style = MaterialTheme.typography.titleSmall)
                BodyText(progress)
            }
            if (total == null) {
                LinearProgressIndicator(Modifier.fillMaxWidth())
            } else {
                LinearProgressIndicator(
                    progress = { (state.receivedBytes.toFloat() / total).coerceIn(0f, 1f) },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            TextButton(onClick = cancel) { Text(tr(R.string.update_cancel_download)) }
        }
        UpdatePackageState.Cancelling -> BigActionButton(tr(R.string.update_cancelling), {}, enabled = false, loading = true)
        UpdatePackageState.Verifying -> BigActionButton(tr(R.string.update_verifying), {}, enabled = false, loading = true)
        is UpdatePackageState.Ready -> {
            val hint = when {
                taskBusy -> R.string.update_install_wait
                state.installStatus == InstallStatus.OPENED -> R.string.update_install_confirm
                state.installStatus == InstallStatus.PERMISSION_REQUIRED -> R.string.update_install_permission
                state.installStatus == InstallStatus.FAILED -> R.string.update_install_failed
                else -> R.string.update_ready
            }
            BodyText(tr(hint), Modifier.semantics { liveRegion = LiveRegionMode.Polite })
                    BigActionButton(tr(R.string.update_install), install, enabled = !taskBusy)
        }
        else -> {
            val size = available.release.sizeBytes?.let { fileSize(it) }
            val failed = (state as? UpdatePackageState.DownloadFailed)?.takeIf { it.source == null || it.source == source }
            if (failed != null) {
                BodyText(tr(failed.problem.text), Modifier.semantics { liveRegion = LiveRegionMode.Polite })
            }
            val label = when {
                failed?.problem?.needsNewCdk == true -> tr(R.string.update_cdk_replace)
                failed != null -> tr(R.string.update_retry)
                size != null -> tr(R.string.update_download_size, size)
                else -> tr(R.string.update_download)
            }
            BigActionButton(label, download, icon = M7Icons.Download, enabled = !cdkBusy)
        }
    }
}

@Composable
private fun fileSize(bytes: Long) = Formatter.formatShortFileSize(LocalContext.current, bytes)

private enum class CdkPrompt(val confirmLabel: Int) {
    EDIT(R.string.update_cdk_save), DOWNLOAD(R.string.update_cdk_save_download),
}

@Composable
private fun CdkDialog(
    prompt: CdkPrompt,
    hasCdk: Boolean,
    busy: Boolean,
    error: Int?,
    dismiss: () -> Unit,
    save: (String?) -> Unit,
) {
    var value by remember { mutableStateOf("") }
    val submit = { if (!busy && value.isNotBlank()) save(value.trim()) }
    AlertDialog(
        onDismissRequest = { if (!busy) dismiss() },
        properties = DialogProperties(dismissOnClickOutside = false),
        title = { Text(tr(R.string.update_cdk)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value, { value = it }, Modifier.fillMaxWidth(), enabled = !busy,
                    label = { Text(tr(if (hasCdk) R.string.update_cdk_replace_input else R.string.update_cdk_input)) },
                    singleLine = true, visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
                    keyboardActions = KeyboardActions(onDone = { submit() }),
                )
                if (error != null) Notice(tr(error), tone = Tone.ERROR)
                if (hasCdk) {
                    TextButton(onClick = { save(null) }, enabled = !busy) {
                        Text(tr(R.string.update_cdk_remove), color = MaterialTheme.colorScheme.error)
                    }
                }
            }
        },
        confirmButton = { TextButton(submit, enabled = !busy && value.isNotBlank()) { Text(tr(prompt.confirmLabel)) } },
        dismissButton = { TextButton(dismiss, enabled = !busy) { Text(tr(R.string.cancel)) } },
    )
}
