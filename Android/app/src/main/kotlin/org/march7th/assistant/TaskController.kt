package org.march7th.assistant

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
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.zip.ZipInputStream

enum class TaskId { ROUTINE, DAILY, REWARDS, POWER }

/** 触屏清体力支持的副本类型。typeName 是共享配置和 instance_names.json 里的键，cost 是单次挑战的开拓力。 */
enum class InstanceType(val typeName: String, val cost: Int) {
    GOLDEN_CALYX("拟造花萼（金）", 10),
    CRIMSON_CALYX("拟造花萼（赤）", 10),
    STAGNANT_SHADOW("凝滞虚影", 30),
    CAVERN("侵蚀隧洞", 40),
}
enum class ServiceState { IDLE, RECOVERING, STARTING, CONNECTED, CLEANING }
enum class GameState { OFF, STARTING, FLASHING, RETURNING, READY, MANUAL_LOGIN }
enum class TaskPhase { IDLE, PREPARING, WAITING_FOR_GAME, RUNNING, STOPPING, CLEANING, SUCCEEDED, STOPPED, FAILED }

data class TaskConfig(
    val collectRewards: Boolean = true,
    val panelOff: Boolean = false,
    val muteGame: Boolean = true,
    val dispatch: Boolean = true,
    val mail: Boolean = true,
    val assist: Boolean = true,
    val message: Boolean = false,
    val synthesis: Boolean = true,
    val instanceType: InstanceType = InstanceType.GOLDEN_CALYX,
    val instanceName: String = "回忆之蕾",
    val waves: Int = 1,
    val reserve: Boolean = false,
    val fuel: Boolean = false,
    /** 支援角色在 character_names.json 里的键，按查找的先后排列。为空时不借用。 */
    val supports: List<String> = emptyList(),
    val borrowAlways: Boolean = false,
) {
    /** 供 Python 读取。 */
    fun supportKeys(): Array<String> = supports.toTypedArray()
}

/** 可选的副本或角色。id 写入配置，title 和 detail 用于显示。 */
class CatalogItem(val id: String, val title: String, val detail: String? = null)

/** 随 APK 打包的游戏数据里可选的副本和支援角色。 */
class Catalog(val instances: Map<InstanceType, List<CatalogItem>>, val characters: List<CatalogItem>)

data class TaskState(
    val privilege: Privilege = Privilege.SHIZUKU,
    val permission: PermissionState = PermissionState.NOT_RUNNING,
    val service: ServiceState = ServiceState.IDLE,
    val displayId: Int? = null,
    val gameDisplayId: Int? = null,
    val game: GameState = GameState.OFF,
    val task: TaskId = TaskId.DAILY,
    val phase: TaskPhase = TaskPhase.IDLE,
    val config: TaskConfig = TaskConfig(),
    val panelOff: Boolean = false,
    val errorCode: String? = null,
    val summary: String? = null,
) {
    val busy: Boolean
        get() = service == ServiceState.RECOVERING || phase in setOf(
            TaskPhase.PREPARING, TaskPhase.WAITING_FOR_GAME, TaskPhase.RUNNING, TaskPhase.STOPPING, TaskPhase.CLEANING
        )
}

/** 界面操作在主线程调用，任务和设备 I/O 串行执行。 */
class TaskController private constructor(private val context: Context) {
    private val main = Handler(Looper.getMainLooper())
    private val worker = Executors.newSingleThreadExecutor()
    private val prefs = context.getSharedPreferences("task-options", Context.MODE_PRIVATE)
    private val access = DeviceAccess(context)
    private val marker = AtomicFile(File(context.filesDir, "active-task"))
    private val logFile = File(context.filesDir, "last-run.log")
    private val logLock = Any()
    private val stateData = MutableStateFlow(
        TaskState(
            privilege = if (prefs.getBoolean("root", false)) Privilege.ROOT else Privilege.SHIZUKU,
            task = TaskId.entries.firstOrNull { it.name == prefs.getString("task", null) } ?: TaskId.DAILY,
            config = TaskConfig(
                collectRewards = prefs.getBoolean("collect-rewards", true),
                panelOff = prefs.getBoolean("panel-off", false),
                muteGame = prefs.getBoolean("mute-game", true),
                dispatch = prefs.getBoolean("dispatch", true),
                mail = prefs.getBoolean("mail", true),
                assist = prefs.getBoolean("assist", true),
                message = prefs.getBoolean("message", false),
                synthesis = prefs.getBoolean("synthesis", true),
                instanceType = InstanceType.entries.firstOrNull { it.name == prefs.getString("instance-type", null) }
                    ?: InstanceType.GOLDEN_CALYX,
                // 旧版本只保存拟造花萼（金）的选择。
                instanceName = prefs.getString("instance-name", null)
                    ?: mapOf("CREDITS" to "藏珍之蕾", "MATERIALS" to "以太之蕾")[prefs.getString("calyx", null)]
                    ?: "回忆之蕾",
                waves = prefs.getInt("waves", 1),
                reserve = prefs.getBoolean("reserve", false),
                fuel = prefs.getBoolean("fuel", false),
                supports = prefs.getString("supports", "")!!.split(',').filter { it.isNotEmpty() },
                borrowAlways = prefs.getBoolean("borrow-always", false),
            )
        )
    )
    private val logData = MutableStateFlow(
        runCatching { logFile.readRunLog(LOG_LINES) }.getOrDefault(emptyList())
    )
    private var active: TaskRun? = null

    val state: StateFlow<TaskState> = stateData.asStateFlow()
    val logs: StateFlow<List<LogEntry>> = logData.asStateFlow()

    /** 首次读取时从 project.zip 解析，和任务实际使用的数据是同一份。 */
    val catalog: Catalog by lazy {
        runCatching { loadCatalog() }.getOrElse {
            Log.w("M7ATask", "Cannot read catalog", it)
            Catalog(emptyMap(), emptyList())
        }
    }

    init {
        refreshPermission()
        if (marker.baseFile.exists()) {
            stateData.update { it.copy(phase = TaskPhase.FAILED, errorCode = "interrupted") }
            recover()
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
        stateData.update { it.copy(permission = access.state(it.privilege)) }
    }

    fun selectPrivilege(privilege: Privilege): Boolean {
        if (state.value.busy) return false
        prefs.edit().putBoolean("root", privilege == Privilege.ROOT).apply()
        stateData.update { it.copy(privilege = privilege, permission = access.state(privilege)) }
        return true
    }

    fun requestPermission() {
        if (state.value.busy) return
        if (state.value.privilege == Privilege.ROOT) {
            worker.execute {
                runCatching { access.probeRoot() }
                refreshPermission()
            }
        } else {
            runCatching { access.requestShizukuPermission() }
            refreshPermission()
        }
    }

    fun selectTask(task: TaskId): Boolean {
        if (state.value.busy) return false
        prefs.edit().putString("task", task.name).apply()
        stateData.update { it.copy(task = task) }
        return true
    }

    fun updateConfig(config: TaskConfig): Boolean {
        if (state.value.busy || config.waves !in 1..MAX_WAVES || config.supports.size > MAX_SUPPORTS) return false
        prefs.edit()
            .putBoolean("collect-rewards", config.collectRewards)
            .putBoolean("panel-off", config.panelOff)
            .putBoolean("mute-game", config.muteGame)
            .putBoolean("dispatch", config.dispatch)
            .putBoolean("mail", config.mail)
            .putBoolean("assist", config.assist)
            .putBoolean("message", config.message)
            .putBoolean("synthesis", config.synthesis)
            .putString("instance-type", config.instanceType.name)
            .putString("instance-name", config.instanceName)
            .putInt("waves", config.waves)
            .putBoolean("reserve", config.reserve)
            .putBoolean("fuel", config.fuel)
            .putString("supports", config.supports.joinToString(","))
            .putBoolean("borrow-always", config.borrowAlways)
            .apply()
        stateData.update { it.copy(config = config) }
        return true
    }

    fun start(): Boolean {
        refreshPermission()
        recover()
        val snapshot = state.value
        if (snapshot.busy || snapshot.permission != PermissionState.READY) return false
        if (!context.hasPackage(DeviceAccess.GAME_PACKAGE)) return failToStart("game_not_installed")
        if (context.getSystemService(KeyguardManager::class.java).isKeyguardLocked) {
            return failToStart("keyguard_locked")
        }
        active = TaskRun(snapshot)
        stateData.update { it.copy(phase = TaskPhase.PREPARING, game = GameState.OFF, errorCode = null, summary = null) }
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
        synchronized(logLock) { logFile.inputStream().use { it.copyTo(output) } }
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
                    )
                }
                onFinished()
            }
        }
        return true
    }

    private fun failToStart(code: String): Boolean {
        stateData.update { it.copy(phase = TaskPhase.FAILED, errorCode = code, summary = null) }
        return false
    }

    private fun recover() {
        if (!marker.baseFile.exists() || state.value.busy) return
        val stale = runCatching { marker.readFully().decodeToString() }.getOrNull()
        if (stale == Privilege.SHIZUKU.name && access.state(Privilege.SHIZUKU) != PermissionState.READY) return
        stateData.update { it.copy(service = ServiceState.RECOVERING) }
        worker.execute {
            try {
                if (stale == Privilege.SHIZUKU.name) access.recoverShizuku()
                marker.delete()
                appLog(LogLevel.INFO, "已检查上次异常结束的设备端租约")
            } catch (error: Exception) {
                appLog(LogLevel.WARNING, "上次运行的清理仍待确认：${error.javaClass.simpleName}")
            } finally {
                stateData.update { it.copy(service = ServiceState.IDLE) }
            }
        }
    }

    private fun appLog(level: LogLevel, message: String) =
        appendLog(logEntry(System.currentTimeMillis(), level, LogCategory.APP, message))

    private fun appendLog(entry: LogEntry) {
        synchronized(logLock) {
            runCatching { logFile.appendText(entry.toLogText(), Charsets.UTF_8) }.onFailure {
                Log.w("M7ATask", "Cannot write task log", it)
            }
            logData.update { (it + entry).takeLast(LOG_LINES) }
        }
    }

    inner class TaskRun internal constructor(private val snapshot: TaskState) {
        internal var started = false
        internal val cancelled = AtomicBoolean()
        internal val stopTimeout = Runnable { if (active === this) Process.killProcess(Process.myPid()) }
        private var device: DeviceLease? = null
        private var deviceError: String? = null
        private var movingBack = false
        internal var summary: String? = null
            private set
        private val token = newToken()

        internal fun execute(): String {
            val wake = context.getSystemService(PowerManager::class.java)
                .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "${context.packageName}:task")
            var result = "runtime_error"
            var cleanupConfirmed = true
            try {
                synchronized(logLock) {
                    logFile.writeText("")
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
                wake.acquire(20 * 60 * 1000L)
                result = if (isCancelled()) "stopped" else runPython()
            } catch (error: Exception) {
                appLog(LogLevel.ERROR, "任务执行失败：${error.message}")
                result = if (isCancelled()) "stopped" else "runtime_error"
            } finally {
                cleaning()
                try {
                    device?.close()
                } catch (error: Exception) {
                    cleanupConfirmed = false
                    result = "cleanup_pending"
                    appLog(LogLevel.ERROR, "设备端服务清理超时：${error.message}")
                } finally {
                    if (wake.isHeld) wake.release()
                    if (cleanupConfirmed) marker.delete()
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
            val result = module.callAttr(
                "run", workspace.path, token, Build.VERSION.SDK_INT, Build.VERSION.RELEASE, Build.MODEL,
                "x86_64" in Build.SUPPORTED_ABIS, snapshot.task.name, snapshot.config, language, this
            ).toString()
            return if (result == "runtime_error") deviceError ?: result else result
        }

        // 以下方法由同一工作线程上的 Python 调用。
        fun isCancelled(): Boolean = cancelled.get()

        fun log(timeMs: Long, level: String, category: String, message: String, heading: Boolean) {
            appendLog(logEntry(timeMs, LogLevel.valueOf(level), LogCategory.valueOf(category), message, heading))
        }

        fun reportSummary(text: String) {
            summary = text
        }

        fun openDevice(): Int {
            stateData.update { it.copy(service = ServiceState.STARTING) }
            try {
                val boot = SystemClock.elapsedRealtime()
                val opened = access.open(snapshot.privilege, token)
                device = opened
                appLog(LogLevel.INFO, "设备端服务启动耗时 ${SystemClock.elapsedRealtime() - boot} ms")
                return opened.port
            } catch (error: DeviceFailure) {
                deviceError = error.code
                throw error
            }
        }

        fun displayReady(id: Int) {
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

        fun gameReady() {
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
        const val MAX_WAVES = 24
        const val MAX_SUPPORTS = 6
        private const val LOG_LINES = 200
        private const val INSTANCE_NAMES = "assets/config/instance_names.json"
        private const val CHARACTER_NAMES = "assets/config/character_names.json"
        @Volatile private var instance: TaskController? = null

        fun get(context: Context): TaskController = instance ?: synchronized(this) {
            instance ?: TaskController(context.applicationContext).also { instance = it }
        }
    }
}
