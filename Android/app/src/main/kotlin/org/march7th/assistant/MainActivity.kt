package org.march7th.assistant

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.march7th.assistant.ui.App
import org.march7th.assistant.ui.AppActions
import org.march7th.assistant.ui.DeviceInfo
import org.march7th.assistant.ui.M7ATheme
import org.march7th.assistant.ui.ThemeMode
import org.march7th.assistant.ui.demoFrom

/** 正式界面的宿主。任务状态和操作都走 TaskController，这里只处理系统权限、文件选择和外部跳转。 */
class MainActivity : ComponentActivity() {
    private val controller by lazy { TaskController.get(this) }
    private val preferences by lazy { getSharedPreferences("ui", MODE_PRIVATE) }
    private var themeMode by mutableStateOf(ThemeMode.SYSTEM)
    private var notificationsAllowed by mutableStateOf(true)

    private val notificationRequest = registerForActivityResult(ActivityResultContracts.RequestPermission()) {
        refreshNotifications()
        controller.start()
    }
    private val exportRequest = registerForActivityResult(ActivityResultContracts.CreateDocument("text/plain")) { target ->
        if (target != null) export(target)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        themeMode = ThemeMode.entries.firstOrNull { it.name == preferences.getString("theme", null) } ?: ThemeMode.SYSTEM
        val demo = demoFrom(intent)
        demo?.theme?.let { themeMode = it }
        val actions = actions()
        setContent {
            val dark = when (themeMode) {
                ThemeMode.SYSTEM -> isSystemInDarkTheme()
                ThemeMode.LIGHT -> false
                ThemeMode.DARK -> true
            }
            DisposableEffect(dark) {
                val bars = SystemBarStyle.auto(Color.TRANSPARENT, Color.TRANSPARENT) { dark }
                enableEdgeToEdge(bars, bars)
                onDispose {}
            }
            val state by controller.state.collectAsStateWithLifecycle()
            val logs by controller.logs.collectAsStateWithLifecycle()
            val device = remember(notificationsAllowed) {
                DeviceInfo(
                    sdk = Build.VERSION.SDK_INT,
                    release = Build.VERSION.RELEASE,
                    miui = listOf(Build.MANUFACTURER, Build.BRAND).any { it.lowercase() in XIAOMI_BRANDS },
                    notificationsAllowed = notificationsAllowed,
                    version = BuildConfig.VERSION_NAME,
                )
            }
            M7ATheme(dark) {
                if (demo != null) {
                    App(demo.state, demo.logs, controller::catalog, device, themeMode, actions, demo.tab, demo.page)
                } else {
                    App(state, logs, controller::catalog, device, themeMode, actions)
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        controller.refreshPermission()
        refreshNotifications()
    }

    private fun actions() = AppActions(
        start = ::start,
        stop = controller::stop,
        setTaskEnabled = { task, enabled -> controller.setTaskEnabled(task, enabled) },
        updateConfig = { controller.updateConfig(it) },
        selectPrivilege = { controller.selectPrivilege(it) },
        requestPermission = controller::requestPermission,
        openShizuku = {
            open(packageManager.getLaunchIntentForPackage(DeviceAccess.SHIZUKU_PACKAGE) ?: view(SHIZUKU_RELEASES))
        },
        downloadShizuku = { open(view(SHIZUKU_RELEASES)) },
        openShizukuManual = { open(view(tr(R.string.url_shizuku_manual))) },
        openProjectPage = { open(view(PROJECT_PAGE)) },
        openAppSettings = {
            open(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.fromParts("package", packageName, null)))
        },
        openNotificationSettings = {
            open(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, packageName))
        },
        exportLog = { runCatching { exportRequest.launch(LOG_NAME) }.onFailure { toast(R.string.no_app_to_open) } },
        setThemeMode = {
            themeMode = it
            preferences.edit().putString("theme", it.name).apply()
        },
    )

    /** Android 13 起先问一次通知权限，前台服务的进度和停止按钮靠它显示。无论是否允许都继续启动。 */
    private fun start() {
        if (Build.VERSION.SDK_INT >= 33 && !askedForNotifications &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            askedForNotifications = true
            notificationRequest.launch(Manifest.permission.POST_NOTIFICATIONS)
        } else {
            controller.start()
        }
    }

    private fun refreshNotifications() {
        notificationsAllowed = Build.VERSION.SDK_INT < 33 ||
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
    }

    private fun export(target: Uri) {
        lifecycleScope.launch {
            val saved = withContext(Dispatchers.IO) {
                runCatching { checkNotNull(contentResolver.openOutputStream(target)).use(controller::exportLog) }.isSuccess
            }
            toast(if (saved) R.string.log_saved else R.string.log_error)
        }
    }

    private fun view(url: String) = Intent(Intent.ACTION_VIEW, Uri.parse(url))

    private fun open(intent: Intent) {
        runCatching { startActivity(intent) }.onFailure { toast(R.string.no_app_to_open) }
    }

    private fun toast(message: Int) = Toast.makeText(this, tr(message), Toast.LENGTH_SHORT).show()

    companion object {
        // 系统文件选择器会给 text/plain 补 .txt，直接用 .txt 结尾免得出现双扩展名。
        private const val LOG_NAME = "march7th-android-log.txt"
        private const val SHIZUKU_RELEASES = "https://github.com/RikkaApps/Shizuku/releases/latest"
        private const val PROJECT_PAGE = "https://github.com/moesnow/March7thAssistant"
        private val XIAOMI_BRANDS = setOf("xiaomi", "redmi", "poco")
        private var askedForNotifications = false
    }
}
