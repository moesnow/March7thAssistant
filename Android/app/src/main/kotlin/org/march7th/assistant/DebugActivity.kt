package org.march7th.assistant

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.View
import android.view.WindowInsets
import android.widget.Button
import android.widget.CheckBox
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class DebugActivity : Activity() {
    private val controller by lazy { TaskController.get(this) }
    private val scope = CoroutineScope(Dispatchers.Main.immediate + SupervisorJob())
    private var observer: Job? = null
    private lateinit var access: TextView
    private lateinit var guide: TextView
    private lateinit var authorize: Button
    private lateinit var root: CheckBox
    private lateinit var panel: CheckBox
    private lateinit var start: Button
    private lateinit var stop: Button
    private lateinit var export: Button
    private lateinit var progress: TextView
    private lateinit var scroll: ScrollView
    private lateinit var log: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val content = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val margin = (16 * resources.displayMetrics.density).toInt()
        content.setOnApplyWindowInsetsListener { view, insets ->
            @Suppress("DEPRECATION")
            val bars = if (Build.VERSION.SDK_INT >= 30) insets.getInsets(WindowInsets.Type.systemBars()) else
                android.graphics.Insets.of(
                    insets.systemWindowInsetLeft, insets.systemWindowInsetTop,
                    insets.systemWindowInsetRight, insets.systemWindowInsetBottom
                )
            view.setPadding(margin + bars.left, margin + bars.top, margin + bars.right, margin + bars.bottom)
            insets
        }
        access = TextView(this).apply { textSize = 20f }
        guide = TextView(this)
        authorize = Button(this).apply { setOnClickListener { authorize() } }
        root = CheckBox(this).apply {
            text = tr(R.string.use_root)
            setOnClickListener { controller.selectPrivilege(if (isChecked) Privilege.ROOT else Privilege.SHIZUKU) }
        }
        panel = CheckBox(this).apply {
            text = tr(R.string.panel_off)
            setOnClickListener { controller.updateConfig(controller.state.value.config.copy(panelOff = isChecked)) }
        }
        start = Button(this).apply {
            text = tr(R.string.start_daily)
            setOnClickListener { startDaily() }
        }
        stop = Button(this).apply {
            text = tr(R.string.stop)
            setOnClickListener { controller.stop() }
        }
        export = Button(this).apply {
            text = tr(R.string.export_log)
            setOnClickListener { selectLogDestination() }
        }
        progress = TextView(this)
        log = TextView(this).apply { setTextIsSelectable(true) }
        scroll = ScrollView(this).apply { addView(log) }
        content.addView(access)
        content.addView(guide)
        content.addView(LinearLayout(this).apply {
            addView(root)
            addView(authorize)
        })
        content.addView(panel)
        content.addView(LinearLayout(this).apply {
            addView(start)
            addView(stop)
            addView(export)
        })
        content.addView(progress)
        content.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))
        setContentView(content)
    }

    override fun onStart() {
        super.onStart()
        observer = scope.launch {
            launch { controller.state.collect(::render) }
            launch {
                controller.logs.collect {
                    val atBottom = !scroll.canScrollVertically(1)
                    log.text = it.joinToString("\n")
                    if (atBottom) scroll.post { scroll.fullScroll(View.FOCUS_DOWN) }
                    export.isEnabled = it.isNotEmpty()
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        controller.refreshPermission()
    }

    override fun onStop() {
        observer?.cancel()
        super.onStop()
    }

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    private fun render(state: TaskState) {
        val shizuku = state.privilege == Privilege.SHIZUKU
        val permissionLabel = when (state.permission) {
            PermissionState.NOT_INSTALLED -> R.string.permission_missing
            PermissionState.NOT_RUNNING -> R.string.permission_inactive
            PermissionState.NOT_AUTHORIZED -> R.string.permission_denied
            PermissionState.READY -> R.string.permission_ready
        }
        val method = if (shizuku) "Shizuku" else "Root"
        access.text = tr(R.string.permission_line, method, tr(permissionLabel))
        guide.visibility = if (shizuku && state.permission != PermissionState.READY) View.VISIBLE else View.GONE
        guide.text = tr(if (Build.VERSION.SDK_INT <= 29) R.string.shizuku_usb else R.string.shizuku_wireless)
        authorize.text = tr(when {
            !shizuku -> R.string.check_root
            state.permission == PermissionState.NOT_INSTALLED -> R.string.get_shizuku
            state.permission == PermissionState.NOT_RUNNING -> R.string.open_shizuku
            else -> R.string.authorize
        })
        authorize.visibility = if (state.permission == PermissionState.READY) View.GONE else View.VISIBLE
        authorize.isEnabled = !state.busy
        root.isChecked = !shizuku
        root.isEnabled = !state.busy
        panel.isChecked = state.config.panelOff
        panel.isEnabled = !state.busy
        start.isEnabled = !state.busy && state.permission == PermissionState.READY
        stop.isEnabled = state.busy && state.service != ServiceState.RECOVERING &&
            state.phase !in setOf(TaskPhase.STOPPING, TaskPhase.CLEANING)
        val result = when (state.errorCode) {
            "game_not_installed" -> tr(R.string.game_missing)
            "manual_action_required" -> tr(R.string.manual_login)
            "keyguard_locked" -> tr(R.string.unlock)
            "interrupted" -> tr(R.string.interrupted)
            null -> tr(state.phase.label)
            else -> tr(R.string.error, state.errorCode)
        }
        progress.text = state.displayId?.let { tr(R.string.display_line, result, it) } ?: result
    }

    private fun authorize() {
        val state = controller.state.value
        if (state.privilege == Privilege.ROOT || state.permission == PermissionState.NOT_AUTHORIZED) {
            controller.requestPermission()
            return
        }
        val release = Uri.parse("https://github.com/RikkaApps/Shizuku/releases/latest")
        val open = if (state.permission == PermissionState.NOT_RUNNING)
            packageManager.getLaunchIntentForPackage(DeviceAccess.SHIZUKU_PACKAGE) else null
        startActivity(open ?: Intent(Intent.ACTION_VIEW, release))
    }

    private fun startDaily() {
        if (!controller.selectTask(TaskId.DAILY)) return
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED && !askedForNotifications
        ) {
            askedForNotifications = true
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), NOTIFICATIONS_REQUEST)
        } else {
            controller.start()
        }
    }

    @Deprecated("Activity API")
    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<String>, results: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, results)
        if (requestCode == NOTIFICATIONS_REQUEST) controller.start()
    }

    @Suppress("DEPRECATION")
    private fun selectLogDestination() {
        startActivityForResult(
            Intent(Intent.ACTION_CREATE_DOCUMENT)
                .addCategory(Intent.CATEGORY_OPENABLE)
                .setType("text/plain")
                .putExtra(Intent.EXTRA_TITLE, "march7th-android.log"),
            EXPORT_REQUEST
        )
    }

    @Deprecated("Activity API")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != EXPORT_REQUEST || resultCode != RESULT_OK) return
        val destination = data?.data ?: return
        scope.launch {
            val saved = withContext(Dispatchers.IO) {
                runCatching {
                    checkNotNull(contentResolver.openOutputStream(destination)).use(controller::exportLog)
                }.isSuccess
            }
            Toast.makeText(this@DebugActivity, tr(if (saved) R.string.log_saved else R.string.log_error), Toast.LENGTH_SHORT).show()
        }
    }

    companion object {
        private const val EXPORT_REQUEST = 1803
        private const val NOTIFICATIONS_REQUEST = 1804
        private var askedForNotifications = false
    }
}
