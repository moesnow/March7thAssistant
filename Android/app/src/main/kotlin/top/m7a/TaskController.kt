package top.m7a

import android.app.KeyguardManager
import android.content.Context
import android.content.Intent
import android.os.Build
import android.view.Display
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.os.Process
import android.os.SystemClock
import android.util.AtomicFile
import android.util.Log
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import org.json.JSONObject
import rikka.shizuku.Shizuku
import java.io.File
import java.io.OutputStream
import java.time.LocalDate
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.zip.ZipInputStream

enum class ServiceState { IDLE, RECOVERING, STARTING, CONNECTED, CLEANING }
enum class GameState { OFF, STARTING, FLASHING, RETURNING, READY, MANUAL_LOGIN }
enum class TaskPhase { IDLE, PREPARING, WAITING_FOR_GAME, RUNNING, STOPPING, CLEANING, SUCCEEDED, STOPPED, FAILED }

data class TaskState(
    val privilege: Privilege = Privilege.SHIZUKU,
    val permission: PermissionState = PermissionState.NOT_RUNNING,
    val service: ServiceState = ServiceState.IDLE,
    val displayId: Int? = null,
    val gameDisplayId: Int? = null,
    val game: GameState = GameState.OFF,
    /** 所选任务，每轮只执行一个。 */
    val task: TaskId = TaskId.ROUTINE,
    val phase: TaskPhase = TaskPhase.IDLE,
    val config: TaskConfig = TaskConfig(),
    val panelOff: Boolean = false,
    val errorCode: String? = null,
    val summary: String? = null,
    /** 本轮各步骤的结果，开始时按设置生成，保留到下一轮开始。 */
    val steps: List<StepResult> = emptyList(),
    /** Python 记下的上次完成每日实训和历战余响的时间（毫秒），没有记录时为空。 */
    val lastDailyDone: Long? = null,
    val lastEchoDone: Long? = null,
) {
    val busy: Boolean
        get() = service == ServiceState.RECOVERING || phase in setOf(
            TaskPhase.PREPARING, TaskPhase.WAITING_FOR_GAME, TaskPhase.RUNNING, TaskPhase.STOPPING, TaskPhase.CLEANING
        )
}

internal class TaskCleanup(private val onUnconfirmed: (Throwable) -> Unit) {
    var confirmed = true
        private set

    fun unconfirmed(error: Throwable) {
        confirmed = false
        onUnconfirmed(error)
    }

    fun finish(taskResult: String, close: () -> Unit): String {
        try {
            close()
        } catch (error: Exception) {
            unconfirmed(error)
        }
        return if (!confirmed && (taskResult == "success" || taskResult == "stopped")) "cleanup_pending" else taskResult
    }
}

/** 界面操作在主线程调用，任务和设备 I/O 串行执行。 */
class TaskController private constructor(private val context: Context) {
    private val main = Handler(Looper.getMainLooper())
    private val worker = Executors.newSingleThreadExecutor()
    private val prefs = context.getSharedPreferences("task-options", Context.MODE_PRIVATE)
    private val usage = UsageTelemetry.get(context)
    private val access = DeviceAccess(context) { detail ->
        Log.d("M7ADevice", detail)
        appLog(LogLevel.DEBUG, detail)
    }
    private val rootProbeInFlight = AtomicBoolean()
    private val marker = AtomicFile(File(context.filesDir, "active-task"))
    private val logFile = File(context.filesDir, "last-run.log")
    private val diagnostics = RunDiagnostics(context.filesDir)
    private val tracebackFallback = context.getString(R.string.logs_traceback_summary)
    private val logLock = Any()
    // 偏好键与早期版本不同名，旧键留在文件里也不会被读到。
    private val stateData = MutableStateFlow(
        TaskState(
            privilege = if (prefs.getBoolean("root", false)) Privilege.ROOT else Privilege.SHIZUKU,
            task = TaskId.entries.firstOrNull { it.name == prefs.getString(KEY_TASK, null) } ?: TaskId.ROUTINE,
            config = decodeTaskConfig(prefs.getString(KEY_CONFIG, null)),
            lastDailyDone = prefs.getLong(KEY_DAILY_DONE, 0).takeIf { it > 0 },
            lastEchoDone = prefs.getLong(KEY_ECHO_DONE, 0).takeIf { it > 0 },
        )
    )
    private val logData = MutableStateFlow(
        runCatching { logFile.readRunLog(LOG_LINES).map { it.forDisplay(tracebackFallback) } }.getOrDefault(emptyList())
    )
    private val previewData = MutableStateFlow<GamePreviewSource?>(null)
    private var active: TaskRun? = null

    val state: StateFlow<TaskState> = stateData.asStateFlow()
    val logs: StateFlow<List<LogEntry>> = logData.asStateFlow()
    internal val preview: StateFlow<GamePreviewSource?> = previewData.asStateFlow()

    /** 首次读取时从 project.zip 解析，和任务实际使用的数据是同一份。 */
    val catalog: Catalog by lazy {
        runCatching { loadCatalog() }.getOrElse {
            Log.w("M7ATask", "Cannot read catalog", it)
            Catalog(emptyMap(), emptyList())
        }
    }

    init {
        worker.execute(usage::recoverInterrupted)
        refreshPermission()
        if (marker.baseFile.exists()) {
            stateData.update { it.copy(phase = TaskPhase.FAILED, errorCode = "interrupted") }
            recover()
        }
        // 旧版只保存了所选模式，升级后对原先选用 Root 的用户补做一次检查。
        if (state.value.privilege == Privilege.ROOT && prefs.getBoolean(KEY_ROOT_VERIFIED, true)) {
            checkRootPermission()
        }
        Shizuku.addBinderReceivedListenerSticky {
            refreshPermission()
            recover()
        }
        Shizuku.addBinderDeadListener { refreshPermission() }
        Shizuku.addRequestPermissionResultListener { code, _ ->
            if (code == DeviceAccess.PERMISSION_REQUEST) {
                refreshPermission()
                recover()
            }
        }
    }

    fun refreshPermission() {
        stateData.update { it.copy(permission = permissionFor(it.privilege)) }
    }

    private fun permissionFor(privilege: Privilege) =
        if (privilege == Privilege.ROOT && rootProbeInFlight.get()) PermissionState.CHECKING else access.state(privilege)

    fun selectPrivilege(privilege: Privilege): Boolean {
        if (state.value.busy) return false
        val edit = prefs.edit().putBoolean("root", privilege == Privilege.ROOT)
        if (privilege == Privilege.ROOT && !prefs.contains(KEY_ROOT_VERIFIED)) edit.putBoolean(KEY_ROOT_VERIFIED, false)
        edit.apply()
        stateData.update { it.copy(privilege = privilege, permission = permissionFor(privilege)) }
        recover()
        return true
    }

    fun requestPermission() {
        if (state.value.busy) return
        if (state.value.privilege == Privilege.ROOT) {
            checkRootPermission()
        } else {
            runCatching { access.requestShizukuPermission() }
            refreshPermission()
        }
    }

    private fun checkRootPermission() {
        if (!rootProbeInFlight.compareAndSet(false, true)) return
        refreshPermission()
        worker.execute {
            try {
                runCatching { access.probeRoot() }.onFailure { Log.w("M7ARoot", "Root check failed", it) }
                prefs.edit().putBoolean(KEY_ROOT_VERIFIED, access.state(Privilege.ROOT) == PermissionState.READY).apply()
            } finally {
                rootProbeInFlight.set(false)
                main.post {
                    refreshPermission()
                    recover()
                }
            }
        }
    }

    fun selectTask(task: TaskId): Boolean {
        if (state.value.busy) return false
        prefs.edit().putString(KEY_TASK, task.name).apply()
        stateData.update { it.copy(task = task) }
        return true
    }

    fun updateConfig(config: TaskConfig): Boolean {
        if (state.value.busy || !config.isValid) return false
        prefs.edit().putString(KEY_CONFIG, config.encode()).apply()
        stateData.update { it.copy(config = config) }
        return true
    }

    fun start(): Boolean {
        refreshPermission()
        val snapshot = state.value
        if (snapshot.busy || snapshot.permission == PermissionState.CHECKING) return false
        if (snapshot.permission != PermissionState.READY) {
            usage.preflightError(snapshot.task, snapshot.privilege, "permission_unavailable")
            return false
        }
        val steps = plannedSteps(snapshot.task, snapshot.config, LocalDate.now().dayOfWeek.value)
        if (steps.idle) return false
        if (!context.hasPackage(DeviceAccess.GAME_PACKAGE)) return failToStart("game_not_installed")
        if (context.getSystemService(KeyguardManager::class.java).isKeyguardLocked) {
            return failToStart("keyguard_locked")
        }
        active = TaskRun(snapshot)
        stateData.update {
            it.copy(phase = TaskPhase.PREPARING, game = GameState.OFF, errorCode = null, summary = null, steps = steps)
        }
        return try {
            context.startForegroundService(Intent(context, TaskRunnerService::class.java))
            true
        } catch (_: RuntimeException) {
            active = null
            failToStart("foreground_start")
        }
    }

    fun stop() {
        val run = active ?: return
        if (!run.cancelled.compareAndSet(false, true)) return
        if (state.value.phase != TaskPhase.CLEANING) stateData.update { it.copy(phase = TaskPhase.STOPPING) }
        // Python 和 native OCR 无法安全地从别的线程终止。超时结束整个宿主，租约随宿主一起关闭。
        main.postDelayed(run.stopTimeout, 60_000)
    }

    /** 在 I/O 线程调用，复制当前一轮的 UTF-8 日志。流由调用者关闭。 */
    fun exportLog(output: OutputStream) {
        synchronized(logLock) {
            logFile.inputStream().use { it.copyTo(output) }
            diagnostics.exportTo(output)
        }
    }

    internal fun begin(onFinished: () -> Unit): Boolean {
        val run = active ?: return false
        if (run.started) return true
        run.started = true
        worker.execute {
            val result = run.execute()
            main.post {
                main.removeCallbacks(run.stopTimeout)
                active = null
                stateData.update {
                    it.copy(
                        permission = access.state(it.privilege),
                        service = ServiceState.IDLE,
                        displayId = null,
                        gameDisplayId = null,
                        panelOff = false,
                        game = if (result == "manual_action_required") GameState.MANUAL_LOGIN else GameState.OFF,
                        phase = when (result) {
                            "success" -> TaskPhase.SUCCEEDED
                            "stopped" -> TaskPhase.STOPPED
                            else -> TaskPhase.FAILED
                        },
                        errorCode = result.takeUnless { it == "success" || it == "stopped" },
                        summary = run.summary.takeIf { result == "success" },
                        steps = it.steps.finished(result),
                    )
                }
                onFinished()
            }
        }
        return true
    }

    private fun failToStart(code: String): Boolean {
        val current = state.value
        usage.preflightError(current.task, current.privilege, code)
        // 没开始的一轮不显示上一轮的步骤结果。
        stateData.update { it.copy(phase = TaskPhase.FAILED, errorCode = code, summary = null, steps = emptyList()) }
        return false
    }

    internal fun recover() {
        if (!marker.baseFile.exists() || state.value.busy) return
        val saved = runCatching { Privilege.valueOf(marker.readFully().decodeToString()) }.getOrNull()
        val privilege = listOfNotNull(saved, state.value.privilege)
            .firstOrNull { access.state(it) == PermissionState.READY } ?: return
        stateData.update { it.copy(service = ServiceState.RECOVERING) }
        worker.execute {
            try {
                access.recoverAudio(privilege)
                marker.delete()
                appLog(LogLevel.INFO, "已完成上次运行的音频恢复检查")
            } catch (error: Exception) {
                appLog(LogLevel.WARNING, "上次运行的音频恢复仍待确认：${error.message}")
            } finally {
                stateData.update { it.copy(service = ServiceState.IDLE) }
            }
        }
    }

    private fun appLog(level: LogLevel, message: String) =
        appendLog(logEntry(System.currentTimeMillis(), level, LogCategory.APP, message))

    private fun appendLog(entry: LogEntry) {
        synchronized(logLock) {
            runCatching {
                if (entry.level == LogLevel.DEBUG) diagnostics.append(entry)
                else logFile.appendText(entry.toLogText(), Charsets.UTF_8)
            }.onFailure {
                Log.w("M7ATask", "Cannot write task log", it)
            }
            if (entry.level != LogLevel.DEBUG) {
                logData.update { (it + entry.forDisplay(tracebackFallback)).takeLast(LOG_LINES) }
            }
        }
    }

    inner class TaskRun internal constructor(private val snapshot: TaskState) {
        internal var started = false
        internal val cancelled = AtomicBoolean()
        internal val stopTimeout = Runnable { if (active === this) Process.killProcess(Process.myPid()) }
        private var device: DeviceLease? = null
        private var deviceError: String? = null
        private val cleanup = TaskCleanup { error ->
            appLog(LogLevel.ERROR, context.getString(R.string.log_task_cleanup_unconfirmed, error))
        }
        private var audioPending = marker.baseFile.exists()
        private var movingBack = false
        private var usageRun: UsageTelemetry.Run? = null
        private var usageStage = UsageStage.PREPARING
        private val timings = mutableMapOf<String, Long>()
        internal var summary: String? = null
            private set
        private val token = newToken()

        internal fun execute(): String {
            val wake = context.getSystemService(PowerManager::class.java)
                .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "${context.packageName}:task")
                .apply { setReferenceCounted(false) }
            val renewal = WakeLockRenewal(
                acquire = wake::acquire,
                release = { if (wake.isHeld) wake.release() },
                now = SystemClock::uptimeMillis,
                postAtTime = { task, time -> main.postAtTime(task, time) },
                removeCallbacks = main::removeCallbacks,
                onRenewalError = { error ->
                    appLog(LogLevel.WARNING, context.getString(
                        R.string.log_wake_lock_renewal_failed, error.message ?: error.javaClass.simpleName,
                    ))
                },
            )
            var result = "runtime_error"
            try {
                usageRun = usage.startTask(snapshot.task, snapshot.privilege, snapshot.config.panelOff)
                synchronized(logLock) {
                    logFile.writeText("")
                    diagnostics.clear()
                    logData.value = emptyList()
                }
                val markerStream = marker.startWrite()
                try {
                    markerStream.write(snapshot.privilege.name.toByteArray())
                    marker.finishWrite(markerStream)
                } catch (error: Exception) {
                    marker.failWrite(markerStream)
                    throw error
                }
                renewal.start()
                result = if (isCancelled()) "stopped" else runPython()
            } catch (error: Exception) {
                appLog(LogLevel.ERROR, "任务执行失败：${error.message}")
                result = if (isCancelled()) "stopped" else "runtime_error"
            } finally {
                val taskResult = result
                try {
                    result = cleanup.finish(taskResult) {
                        renewal.use {
                            cleaning()
                            device?.close()
                        }
                    }
                } finally {
                    val steps = state.value.steps
                    val outcome = when {
                        result == "success" -> UsageOutcome.SUCCESS
                        result == "stopped" -> UsageOutcome.STOPPED
                        result == "task_failed" && steps.any { it.status == StepStatus.DONE } -> UsageOutcome.PARTIAL
                        else -> UsageOutcome.FAILED
                    }
                    usage.finishTask(
                        usageRun, outcome, if (result == taskResult) usageStage else UsageStage.CLEANUP,
                        result, steps.firstOrNull { it.status == StepStatus.FAILED }?.step, timings,
                    )
                    if (cleanup.confirmed && !audioPending) marker.delete()
                }
                val level = if (result == "success" || result == "stopped") LogLevel.INFO else LogLevel.ERROR
                appLog(level, "本轮结束：$result")
            }
            return result
        }

        private fun runPython(): String {
            val boot = SystemClock.elapsedRealtime()
            val workspace = prepareRuntime()
            val module = Python.getInstance().getModule("android_task")
            appLog(LogLevel.INFO, "Python 启动与资源准备耗时 ${SystemClock.elapsedRealtime() - boot} ms")
            val locale = context.resources.configuration.locales[0]
            val language = when (locale.language) {
                "zh" -> if (locale.country in listOf("TW", "HK", "MO") || locale.script == "Hant") "zh_TW" else "zh_CN"
                "ja" -> "ja_JP"
                "ko" -> "ko_KR"
                else -> "en_US"
            }
            val config = snapshot.config
            val settings = Json.encode(config.toSettings(catalog))
            val result = module.callAttr(
                "run", workspace.path, token, Build.VERSION.SDK_INT, Build.VERSION.RELEASE, Build.MODEL,
                "x86_64" in Build.SUPPORTED_ABIS, snapshot.task.name, settings, config.panelOff, config.muteGame,
                language, this
            ).toString()
            return if (result == "runtime_error") deviceError ?: result else result
        }

        // 以下方法由同一工作线程上的 Python 调用。
        fun isCancelled(): Boolean = cancelled.get()

        private fun observeStage(stage: UsageStage) {
            usageStage = stage
            usage.taskStage(usageRun, stage, timings)
        }

        fun ocrStarting() = observeStage(UsageStage.OCR)

        fun ocrReady(elapsedMs: Long) {
            timings["ocr_init_seconds"] = elapsedMs
            usage.taskStage(usageRun, usageStage, timings)
        }

        fun log(timeMs: Long, level: String, category: String, message: String, heading: Boolean) {
            appendLog(logEntry(timeMs, LogLevel.valueOf(level), LogCategory.valueOf(category), message, heading))
        }

        fun reportSummary(text: String) {
            summary = text
        }

        /** state 是 started、succeeded 或 failed。detail 是成功时的摘要或失败的原因，可能为空。 */
        fun reportStep(name: String, state: String, detail: String?) {
            stateData.update { it.copy(steps = it.steps.onStepEvent(name, state, detail)) }
        }

        /** 体力计划的剩余次数和完成时间。不回写的话，已经打掉的次数下一轮会被恢复。 */
        fun reportProgress(json: String) {
            val progress = parseProgress(json)
            if (progress == null) {
                appLog(LogLevel.WARNING, "任务进度无法解析，体力计划保持不变")
                return
            }
            stateData.update {
                it.copy(
                    config = progress.plan?.let { plan -> it.config.copy(powerPlan = plan) } ?: it.config,
                    lastDailyDone = progress.lastDailyDone,
                    lastEchoDone = progress.lastEchoDone,
                )
            }
            val saved = state.value
            // 任务线程同步保存，确保已回报的进度在强杀后仍可读取。
            val persisted = prefs.edit()
                .putString(KEY_CONFIG, saved.config.encode())
                .putLong(KEY_DAILY_DONE, saved.lastDailyDone ?: 0)
                .putLong(KEY_ECHO_DONE, saved.lastEchoDone ?: 0)
                .commit()
            if (!persisted) {
                appLog(LogLevel.WARNING, context.getString(R.string.log_task_progress_write_failed))
            }
        }

        fun openDevice(): Int {
            observeStage(UsageStage.DEVICE_SERVICE)
            stateData.update { it.copy(service = ServiceState.STARTING) }
            try {
                val boot = SystemClock.elapsedRealtime()
                val opened = access.open(snapshot.privilege, token, ::isCancelled)
                device = opened
                val elapsed = SystemClock.elapsedRealtime() - boot
                timings["device_service_seconds"] = elapsed
                appLog(LogLevel.INFO, "设备端服务启动耗时 ${elapsed} ms")
                return opened.port
            } catch (error: DeviceFailure) {
                deviceError = error.code
                appLog(LogLevel.ERROR, "启动设备端服务：${error.message}")
                error.suppressed.forEach(cleanup::unconfirmed)
                throw error
            }
        }

        fun audioRecoveryPending(pending: Boolean) {
            audioPending = pending
        }

        fun previewReady(port: Int) {
            previewData.value = GamePreviewSource(port, token)
        }

        fun displayReady(id: Int) {
            observeStage(UsageStage.GAME_START)
            stateData.update {
                it.copy(
                    service = ServiceState.CONNECTED, displayId = id, game = GameState.STARTING,
                    phase = if (isCancelled()) it.phase else TaskPhase.WAITING_FOR_GAME
                )
            }
        }

        fun gameEvent(event: String, display: Int) {
            when (event) {
                "move_back_started" -> movingBack = true
                "move_back_succeeded", "move_back_failed", "game_exited" -> movingBack = false
            }
            val location = display.takeIf { it >= 0 }
            stateData.update {
                when (event) {
                    "watchdog_started", "sdk_window_shown" -> if (location != null) it.withGameDisplay(location) else it
                    "task_display_changed" -> it.withGameDisplay(location)
                    "move_back_succeeded" -> it.copy(
                        game = if (it.phase == TaskPhase.RUNNING) GameState.READY else GameState.STARTING,
                        gameDisplayId = it.displayId
                    )
                    "manual_action_required" -> it.copy(game = GameState.MANUAL_LOGIN, gameDisplayId = location ?: it.gameDisplayId)
                    "game_exited" -> it.copy(game = GameState.OFF, gameDisplayId = null)
                    else -> it
                }
            }
        }

        private fun TaskState.withGameDisplay(location: Int?) = copy(
            gameDisplayId = location,
            game = when {
                game == GameState.MANUAL_LOGIN -> game
                location == null -> GameState.OFF
                location == Display.DEFAULT_DISPLAY && displayId != null && location != displayId -> GameState.FLASHING
                location != displayId || movingBack -> GameState.RETURNING
                phase == TaskPhase.RUNNING -> GameState.READY
                else -> GameState.STARTING
            },
        )

        fun gameReady(elapsedMs: Long) {
            timings["game_ready_seconds"] = elapsedMs
            observeStage(UsageStage.TASK)
            stateData.update {
                it.copy(
                    game = GameState.READY, gameDisplayId = it.displayId,
                    phase = if (isCancelled()) it.phase else TaskPhase.RUNNING
                )
            }
        }

        fun panelChanged(off: Boolean) {
            stateData.update { it.copy(panelOff = off) }
        }

        fun cleaning() {
            // 保留任务产生错误时的阶段，并为清理期间的进程中断记录实际阶段。
            if (state.value.service != ServiceState.CLEANING) usage.taskStage(usageRun, UsageStage.CLEANUP, timings)
            previewData.value = null
            stateData.update { it.copy(service = ServiceState.CLEANING, phase = TaskPhase.CLEANING) }
        }
    }

    private fun loadCatalog(): Catalog {
        val files = HashMap<String, JSONObject>()
        ZipInputStream(context.assets.open("project.zip").buffered()).use { zip ->
            while (files.size < 2) {
                val entry = zip.nextEntry ?: break
                if (entry.name == INSTANCE_NAMES || entry.name == CHARACTER_NAMES) {
                    files[entry.name] = JSONObject(zip.readBytes().decodeToString())
                }
            }
        }
        val instances = files.getValue(INSTANCE_NAMES)
        val characters = files.getValue(CHARACTER_NAMES)
        return Catalog(
            InstanceType.entries.associateWith { type ->
                val names = instances.getJSONObject(type.typeName)
                names.keys().asSequence().filter { it != "无" }.map { CatalogItem(it, it, names.getString(it)) }.toList()
            },
            characters.keys().asSequence().map { CatalogItem(it, characters.getString(it)) }.toList(),
        )
    }

    private fun prepareRuntime(): File {
        val workspace = File(context.filesDir, "project").apply { mkdirs() }
        if (!Python.isStarted()) {
            // 配置和日志在同一私有目录，升级时只刷新 APK 提供的目录。
            for (directory in listOf("assets", "module", "tasks", "utils")) {
                check(File(workspace, directory).deleteRecursively())
            }
            ZipInputStream(context.assets.open("project.zip").buffered()).use { zip ->
                while (true) {
                    val entry = zip.nextEntry ?: break
                    val target = File(workspace, entry.name).canonicalFile
                    check(target.toPath().startsWith(workspace.canonicalFile.toPath()))
                    if (entry.isDirectory) {
                        target.mkdirs()
                    } else {
                        target.parentFile?.mkdirs()
                        target.outputStream().use { zip.copyTo(it) }
                    }
                }
            }
            Python.start(AndroidPlatform(context))
        }
        return workspace
    }

    companion object {
        // 更早的版本用过 task 和 tasks，这里换一个没用过的名字。
        private const val KEY_TASK = "selected-task"
        private const val KEY_CONFIG = "task-config"
        private const val KEY_ROOT_VERIFIED = "root-probe-verified"
        private const val KEY_DAILY_DONE = "last-daily-done"
        private const val KEY_ECHO_DONE = "last-echo-done"
        private const val LOG_LINES = 200
        private const val INSTANCE_NAMES = "assets/config/instance_names.json"
        private const val CHARACTER_NAMES = "assets/config/character_names.json"
        @Volatile private var instance: TaskController? = null

        fun get(context: Context): TaskController = instance ?: synchronized(this) {
            instance ?: TaskController(context.applicationContext).also { instance = it }
        }
    }
}
