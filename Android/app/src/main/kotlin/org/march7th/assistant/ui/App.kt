package org.march7th.assistant.ui

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.wrapContentWidth
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import org.march7th.assistant.Catalog
import org.march7th.assistant.LogCategory
import org.march7th.assistant.LogEntry
import org.march7th.assistant.Privilege
import org.march7th.assistant.R
import org.march7th.assistant.TaskConfig
import org.march7th.assistant.TaskId
import org.march7th.assistant.TaskState

/** 界面发出的操作。任务相关的都转给契约里的 TaskController，其余是系统跳转和界面偏好。 */
internal class AppActions(
    val start: () -> Unit,
    val stop: () -> Unit,
    val selectTask: (TaskId) -> Unit,
    val updateConfig: (TaskConfig) -> Unit,
    val selectPrivilege: (Privilege) -> Unit,
    val requestPermission: () -> Unit,
    val openShizuku: () -> Unit,
    val downloadShizuku: () -> Unit,
    val openShizukuManual: () -> Unit,
    val openProjectPage: () -> Unit,
    val openAppSettings: () -> Unit,
    val openNotificationSettings: () -> Unit,
    val exportLog: () -> Unit,
    val setThemeMode: (ThemeMode) -> Unit,
)

/** 不来自任务契约的界面状态。 */
internal class DeviceInfo(
    val sdk: Int,
    val release: String,
    val miui: Boolean,
    val notificationsAllowed: Boolean,
    val version: String,
)

internal enum class Tab(val label: Int, val icon: ImageVector) {
    HOME(R.string.tab_home, M7Icons.Home),
    TASKS(R.string.tab_tasks, M7Icons.Tasks),
    LOGS(R.string.tab_logs, M7Icons.Logs),
    SETTINGS(R.string.tab_settings, M7Icons.Settings),
}

internal enum class SubPage { GUIDE, STATUS, POWER_PLAN, TEAM_RULES }

/** 调试构建用模拟数据预览界面时的输入，见 debug 源集的 demoFrom。 */
internal class Demo(val state: TaskState, val logs: List<LogEntry>, val tab: Tab, val page: SubPage?, val theme: ThemeMode?)

internal class Navigator(val openTab: (Tab) -> Unit, val open: (SubPage) -> Unit, val back: () -> Unit)

@Composable
internal fun App(
    state: TaskState,
    logs: List<LogEntry>,
    catalog: () -> Catalog,
    device: DeviceInfo,
    themeMode: ThemeMode,
    actions: AppActions,
    initialTab: Tab = Tab.HOME,
    initialPage: SubPage? = null,
) {
    var tab by rememberSaveable { mutableStateOf(initialTab) }
    var page by rememberSaveable { mutableStateOf(initialPage) }
    // 每个页面的折叠状态和滚动位置单独保存，进出子页面后保持原样。
    val pages = rememberSaveableStateHolder()
    val latestTaskLog = logs.lastOrNull { it.category == LogCategory.TASK }?.message
    val navigator = Navigator(
        openTab = {
            page = null
            tab = it
        },
        open = { page = it },
        back = { page = null },
    )
    BackHandler(page != null) { page = null }
    BackHandler(page == null && tab != Tab.HOME) { tab = Tab.HOME }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        bottomBar = {
            if (page == null) {
                NavigationBar(containerColor = MaterialTheme.colorScheme.surfaceContainerLow) {
                    for (item in Tab.entries) {
                        NavigationBarItem(
                            selected = tab == item,
                            onClick = { tab = item },
                            icon = { Icon(item.icon, null) },
                            label = { Text(tr(item.label)) },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = MaterialTheme.colorScheme.onPrimaryContainer,
                                selectedTextColor = MaterialTheme.colorScheme.primary,
                                indicatorColor = MaterialTheme.colorScheme.primaryContainer,
                            ),
                        )
                    }
                }
            }
        },
    ) { padding ->
        AnimatedContent(
            targetState = page to tab,
            modifier = Modifier.fillMaxSize().padding(padding),
            transitionSpec = { fadeIn() togetherWith fadeOut() },
            label = "screen",
        ) { (currentPage, currentTab) ->
            // 横屏和平板上内容居中，不随屏幕拉宽。
            Box(Modifier.fillMaxSize().wrapContentWidth().widthIn(max = 640.dp)) {
                pages.SaveableStateProvider(currentPage?.name ?: currentTab.name) {
                    when (currentPage) {
                        SubPage.GUIDE -> GuideScreen(state, device, actions, navigator)
                        SubPage.STATUS -> StatusScreen(state, latestTaskLog, navigator)
                        SubPage.POWER_PLAN -> PowerPlanScreen(state, catalog, actions, navigator)
                        SubPage.TEAM_RULES -> TeamRulesScreen(state, catalog, actions, navigator)
                        null -> when (currentTab) {
                            Tab.HOME -> HomeScreen(state, latestTaskLog, actions, navigator)
                            Tab.TASKS -> TasksScreen(state, catalog, actions, navigator)
                            Tab.LOGS -> LogsScreen(state, logs, actions)
                            Tab.SETTINGS -> SettingsScreen(state, device, themeMode, actions, navigator)
                        }
                    }
                }
            }
        }
    }
}
