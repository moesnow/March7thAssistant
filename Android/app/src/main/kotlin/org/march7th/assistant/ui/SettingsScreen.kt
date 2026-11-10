package org.march7th.assistant.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import org.march7th.assistant.PermissionState
import org.march7th.assistant.R
import org.march7th.assistant.TaskState

@Composable
internal fun SettingsScreen(
    state: TaskState,
    device: DeviceInfo,
    themeMode: ThemeMode,
    actions: AppActions,
    navigator: Navigator,
) {
    val scheme = MaterialTheme.colorScheme
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        ScreenTitle(tr(R.string.settings_title))

        SectionLabel(tr(R.string.settings_run))
        PanelCard(padding = PaddingValues(0.dp)) {
            val ready = state.permission == PermissionState.READY
            val permission = tr(
                R.string.settings_permission_summary,
                tr(state.privilege.title), tr(permissionLabel(state.privilege, state.permission)),
            )
            val hint = rootPermissionHint(state.privilege, state.permission)
            SettingRow(
                tr(R.string.home_permission),
                icon = M7Icons.Shield,
                iconTone = if (ready) Tone.SUCCESS else Tone.WARNING,
                summary = if (hint == null) permission else "$permission\n${tr(hint)}",
                onClick = { navigator.open(SubPage.GUIDE) },
            )
            RowDivider()
            SwitchRow(
                tr(R.string.panel_off),
                state.config.panelOff,
                { actions.updateConfig(state.config.copy(panelOff = it)) },
                icon = M7Icons.ScreenOff,
                summary = tr(R.string.panel_off_summary),
                enabled = !state.busy,
            )
            RowDivider()
            SettingRow(
                tr(R.string.status_title),
                icon = M7Icons.Display,
                iconTone = if (state.displayId != null) Tone.ACTIVE else Tone.NEUTRAL,
                summary = runSummary(state),
                onClick = { navigator.open(SubPage.STATUS) },
            )
        }

        SectionLabel(tr(R.string.settings_appearance))
        PanelCard {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconBadge(M7Icons.Palette)
                Spacer(Modifier.width(14.dp))
                Text(tr(R.string.settings_theme), style = MaterialTheme.typography.titleMedium)
            }
            Spacer(Modifier.height(12.dp))
            Segmented(
                listOf(
                    ThemeMode.SYSTEM to tr(R.string.theme_system),
                    ThemeMode.LIGHT to tr(R.string.theme_light),
                    ThemeMode.DARK to tr(R.string.theme_dark),
                ),
                themeMode, actions.setThemeMode,
            )
        }

        SectionLabel(tr(R.string.settings_system))
        PanelCard(padding = PaddingValues(0.dp)) {
            if (device.sdk >= 33) {
                SettingRow(
                    tr(R.string.settings_notification),
                    icon = M7Icons.Notifications,
                    iconTone = if (device.notificationsAllowed) Tone.SUCCESS else Tone.WARNING,
                    summary = tr(
                        if (device.notificationsAllowed) R.string.settings_notification_on else R.string.settings_notification_off
                    ),
                    onClick = actions.openNotificationSettings,
                )
                RowDivider()
            }
            SettingRow(
                tr(R.string.settings_battery),
                icon = M7Icons.Battery,
                summary = tr(R.string.settings_battery_summary),
                onClick = actions.openAppSettings,
            )
        }

        SectionLabel(tr(R.string.settings_about))
        PanelCard(padding = PaddingValues(0.dp)) {
            Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                Image(painterResource(R.drawable.brand_logo), null, Modifier.size(52.dp).clip(RoundedCornerShape(14.dp)))
                Spacer(Modifier.width(14.dp))
                Column {
                    Text(tr(R.string.app_name), style = MaterialTheme.typography.titleMedium)
                    Text(
                        tr(R.string.settings_version, device.version),
                        style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant,
                    )
                }
            }
            RowDivider()
            SettingRow(
                tr(R.string.settings_project),
                summary = tr(R.string.settings_project_summary),
                onClick = actions.openProjectPage,
                trailing = { Icon(M7Icons.OpenInNew, null, Modifier.size(20.dp), tint = scheme.outline) },
            )
            RowDivider()
            SettingRow(
                tr(R.string.shizuku_manual),
                summary = tr(R.string.settings_manual_summary),
                onClick = actions.openShizukuManual,
                trailing = { Icon(M7Icons.OpenInNew, null, Modifier.size(20.dp), tint = scheme.outline) },
            )
        }
        Text(
            tr(R.string.settings_free),
            Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
            style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant, textAlign = TextAlign.Center,
        )
    }
}
