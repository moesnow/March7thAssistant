package org.march7th.assistant.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import org.march7th.assistant.PermissionState
import org.march7th.assistant.Privilege
import org.march7th.assistant.R
import org.march7th.assistant.TaskState

@Composable
internal fun GuideScreen(state: TaskState, device: DeviceInfo, actions: AppActions, navigator: Navigator) {
    val ready = state.permission == PermissionState.READY
    Column(Modifier.fillMaxSize()) {
        SubPageBar(tr(R.string.guide_title), navigator.back)
        Column(
            Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(start = 16.dp, end = 16.dp, bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            BodyText(tr(R.string.guide_intro), Modifier.padding(horizontal = 4.dp))
            Segmented(
                listOf(Privilege.SHIZUKU to tr(R.string.method_shizuku), Privilege.ROOT to tr(R.string.method_root)),
                state.privilege, actions.selectPrivilege, enabled = !state.busy,
            )
            if (state.busy) {
                Notice(tr(R.string.guide_locked), tone = Tone.WARNING)
            }
            PanelCard {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        tr(if (state.privilege == Privilege.SHIZUKU) R.string.guide_shizuku_heading else R.string.guide_root_heading),
                        Modifier.weight(1f), style = MaterialTheme.typography.titleMedium,
                    )
                    StatusPill(
                        tr(permissionLabel(state.privilege, state.permission)),
                        if (ready) Tone.SUCCESS else Tone.WARNING,
                    )
                }
                BodyText(
                    tr(if (state.privilege == Privilege.SHIZUKU) R.string.guide_shizuku_about else R.string.guide_root_about),
                    Modifier.padding(top = 4.dp, bottom = 16.dp),
                )
                if (state.privilege == Privilege.SHIZUKU) {
                    ShizukuSteps(state.permission, device, !state.busy, actions)
                } else {
                    RootSteps(state.permission, !state.busy, actions)
                }
            }
            if (ready) {
                PanelCard {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(tr(R.string.guide_ready_title), style = MaterialTheme.typography.titleMedium)
                            BodyText(tr(R.string.guide_ready_detail), Modifier.padding(top = 4.dp))
                        }
                        Image(painterResource(R.drawable.chibi_ok), null, Modifier.padding(start = 8.dp).width(112.dp))
                    }
                    Button({ navigator.openTab(Tab.HOME) }, Modifier.padding(top = 12.dp).fillMaxWidth().heightIn(min = 48.dp)) {
                        Text(tr(R.string.guide_back_home))
                    }
                }
            }

            SectionLabel(tr(R.string.guide_what_happens))
            PanelCard {
                TipRow(M7Icons.Display, tr(R.string.guide_happens_virtual))
                TipRow(M7Icons.Phone, tr(R.string.guide_happens_flash))
                TipRow(M7Icons.Game, tr(R.string.guide_happens_login))
                TipRow(M7Icons.Info, tr(R.string.guide_happens_account))
                TipRow(M7Icons.Notifications, tr(R.string.guide_happens_sound))
            }

            SectionLabel(tr(R.string.guide_stability))
            PanelCard {
                TipRow(
                    M7Icons.Warning, tr(R.string.guide_tip_miui),
                    tone = if (device.miui) Tone.WARNING else Tone.NEUTRAL,
                )
                TipRow(M7Icons.ScreenOff, tr(R.string.guide_tip_lock))
                TipRow(M7Icons.Stop, tr(R.string.guide_tip_clean))
                TipRow(M7Icons.Battery, tr(R.string.guide_tip_battery))
                if (device.sdk >= 33) {
                    TipRow(M7Icons.Notifications, tr(R.string.guide_tip_notification))
                }
                OutlinedButton(actions.openAppSettings, Modifier.padding(top = 8.dp).fillMaxWidth().heightIn(min = 48.dp)) {
                    Text(tr(R.string.open_app_settings))
                }
            }
        }
    }
}

@Composable
private fun ShizukuSteps(permission: PermissionState, device: DeviceInfo, enabled: Boolean, actions: AppActions) {
    val position = when (permission) {
        PermissionState.NOT_INSTALLED -> 0
        PermissionState.NOT_RUNNING -> 1
        PermissionState.NOT_AUTHORIZED, PermissionState.NOT_CHECKED -> 2
        PermissionState.READY -> 3
    }
    fun stateOf(index: Int) = when {
        index < position -> StepState.DONE
        index == position -> StepState.CURRENT
        else -> StepState.PENDING
    }

    StepItem(1, tr(R.string.guide_install_title), stateOf(0)) {
        if (position == 0) {
            BodyText(tr(R.string.guide_install_detail), Modifier.padding(top = 4.dp))
            StepButton(tr(R.string.get_shizuku), actions.downloadShizuku, icon = true)
        } else {
            BodyText(tr(R.string.guide_install_done))
        }
    }
    StepItem(2, tr(R.string.guide_start_title), stateOf(1)) {
        when {
            position < 1 -> BodyText(tr(R.string.guide_start_pending))
            position > 1 -> BodyText(tr(R.string.guide_start_done))
            else -> {
                val legacy = device.sdk <= 29
                Text(
                    tr(R.string.guide_this_device, device.release),
                    Modifier.padding(top = 4.dp),
                    style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary,
                )
                BodyText(tr(if (legacy) R.string.guide_start_usb else R.string.guide_start_wireless), Modifier.padding(top = 4.dp))
                Notice(
                    tr(if (legacy) R.string.guide_start_usb_reboot else R.string.guide_start_wireless_reboot),
                    Modifier.padding(top = 10.dp), tone = Tone.WARNING,
                )
                StepButton(tr(R.string.open_shizuku), actions.openShizuku)
                Expandable(tr(if (legacy) R.string.guide_other_wireless else R.string.guide_other_usb)) {
                    BodyText(tr(if (legacy) R.string.guide_start_wireless else R.string.guide_start_usb))
                }
                TextButton(actions.openShizukuManual) {
                    Text(tr(R.string.shizuku_manual))
                    Spacer(Modifier.width(6.dp))
                    Icon(M7Icons.OpenInNew, null, Modifier.size(16.dp))
                }
            }
        }
    }
    StepItem(3, tr(R.string.guide_grant_title), stateOf(2), last = true) {
        when {
            position < 2 -> BodyText(tr(R.string.guide_grant_pending))
            position > 2 -> BodyText(tr(R.string.guide_grant_done))
            else -> {
                BodyText(tr(R.string.guide_grant_detail), Modifier.padding(top = 4.dp))
                StepButton(tr(R.string.authorize), actions.requestPermission, enabled = enabled)
                BodyText(tr(R.string.guide_grant_hint), Modifier.padding(top = 8.dp))
            }
        }
    }
}

@Composable
private fun RootSteps(permission: PermissionState, enabled: Boolean, actions: AppActions) {
    val ready = permission == PermissionState.READY
    StepItem(1, tr(R.string.guide_root_check_title), if (ready) StepState.DONE else StepState.CURRENT, last = true) {
        if (ready) {
            BodyText(tr(R.string.guide_root_done))
        } else {
            val hint = rootPermissionHint(Privilege.ROOT, permission)
            if (hint != null) {
                BodyText(tr(hint), Modifier.padding(top = 4.dp))
            } else if (permission == PermissionState.NOT_INSTALLED) {
                Notice(tr(R.string.guide_root_missing), Modifier.padding(top = 10.dp), tone = Tone.ERROR, icon = M7Icons.Error)
            }
            StepButton(tr(R.string.check_root), actions.requestPermission, enabled = enabled)
        }
    }
    Notice(tr(R.string.guide_root_experimental), Modifier.padding(top = 14.dp), tone = Tone.WARNING, icon = M7Icons.Warning)
}

@Composable
private fun StepButton(text: String, onClick: () -> Unit, enabled: Boolean = true, icon: Boolean = false) {
    Button(onClick, Modifier.padding(top = 12.dp).fillMaxWidth().heightIn(min = 48.dp), enabled = enabled) {
        Text(text)
        if (icon) {
            Spacer(Modifier.width(6.dp))
            Icon(M7Icons.OpenInNew, null, Modifier.size(16.dp))
        }
    }
}

@Composable
private fun Expandable(title: String, content: @Composable () -> Unit) {
    var open by rememberSaveable { mutableStateOf(false) }
    Column(Modifier.padding(top = 8.dp)) {
        Row(
            Modifier.fillMaxWidth().clickable(role = Role.Button) { open = !open }.heightIn(min = 48.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(title, Modifier.weight(1f), style = MaterialTheme.typography.labelLarge)
            Icon(M7Icons.ExpandMore, null, Modifier.rotate(if (open) 180f else 0f), tint = MaterialTheme.colorScheme.outline)
        }
        AnimatedVisibility(open) {
            Column {
                content()
                Spacer(Modifier.height(8.dp))
            }
        }
    }
}
