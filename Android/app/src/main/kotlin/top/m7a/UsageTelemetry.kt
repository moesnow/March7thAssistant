package top.m7a

import android.content.Context
import android.content.SharedPreferences
import android.os.Build
import android.os.SystemClock
import android.util.Log
import java.net.URI
import java.time.Instant
import java.time.ZoneOffset
import java.util.UUID
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledFuture
import java.util.concurrent.TimeUnit
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec
import javax.net.ssl.HttpsURLConnection

internal enum class UsageStage { PREFLIGHT, PREPARING, OCR, DEVICE_SERVICE, GAME_START, TASK, CLEANUP }

internal enum class UsageOutcome { SUCCESS, PARTIAL, FAILED, STOPPED, INTERRUPTED }

private const val TELEMETRY_URL = "https://api.m7a.top/telemetry"
private const val FLUSH_DELAY = 30L
private const val MAX_QUEUE = 200
private const val BATCH_SIZE = 50
private const val MAX_EVENT_AGE_SECONDS = 55 * 60L

private val reportedErrors = setOf(
    "permission_unavailable", "game_not_installed", "keyguard_locked", "foreground_start",
    "service_busy", "service_start", "shizuku_unsupported", "root_unavailable", "protocol_mismatch", "service_version",
    "shell_context_init_failed", "display_failed", "display_exists", "no_display", "launch_failed", "game_start_timeout", "game_exited",
    "manual_action_required", "move_back_failed", "device_asleep", "inject_denied", "inject_failed",
    "disconnected", "timeout", "invalid_response", "frame_clock_unavailable", "frame_timeout", "virtual_display_black", "game_not_on_display",
    "template_missing", "task_failed", "runtime_error", "cleanup_pending", "interrupted",
)
private val reportedTimings = setOf("ocr_init_seconds", "device_service_seconds", "game_ready_seconds")

private fun randomId(): String = UUID.randomUUID().toString().replace("-", "")

/** 与桌面端一致，服务端用 events、batch_id 的紧凑 UTF-8 JSON 验签。 */
internal fun signedUsageBatch(events: List<Map<String, Any?>>, batchId: String, secret: String): ByteArray {
    val payload = linkedMapOf<String, Any?>("events" to events, "batch_id" to batchId)
    val mac = Mac.getInstance("HmacSHA256")
    mac.init(SecretKeySpec(secret.encodeToByteArray(), "HmacSHA256"))
    val signature = mac.doFinal(Json.encode(payload).encodeToByteArray()).joinToString("") { "%02x".format(it) }
    return Json.encode(payload + ("signature" to signature)).encodeToByteArray()
}

/** 仅保留安装随机标识、固定字段和少量待发事件。任务线程不执行网络请求。 */
internal class UsageTelemetry private constructor(context: Context) {
    private val prefs = context.getSharedPreferences("anonymous-usage", Context.MODE_PRIVATE)
    private val lock = Any()
    private val worker = Executors.newSingleThreadScheduledExecutor()
    private var scheduled: ScheduledFuture<*>? = null
    private var connection: HttpsURLConnection? = null
    private var generation = 0
    private var retrySeconds = FLUSH_DELAY
    private var registered = false

    val enabled: Boolean get() = prefs.getBoolean("enabled", true)

    class Run internal constructor(val id: String, val startedMs: Long, val properties: Map<String, Any?>)

    private val environment = mapOf(
        "client_platform" to "android",
        "os_version" to "Android ${Build.VERSION.RELEASE}".take(32),
        "android_sdk" to Build.VERSION.SDK_INT,
        "manufacturer" to Build.MANUFACTURER.trim().take(40),
        "device_model" to Build.MODEL.trim().take(64),
        "cpu_arch" to Build.SUPPORTED_ABIS.firstOrNull().orEmpty().take(16),
    ).filterValues { it != "" }

    fun setEnabled(value: Boolean) {
        synchronized(lock) {
            if (enabled == value) return
            generation++
            val edit = prefs.edit().putBoolean("enabled", value)
            if (!value) {
                scheduled?.cancel(false)
                scheduled = null
                runCatching { connection?.disconnect() }
                connection = null
                retrySeconds = FLUSH_DELAY
                edit.remove("queue").remove("active-run").remove("batch")
            }
            edit.apply()
        }
        if (value) appOpened()
    }

    fun appOpened() {
        if (!collecting()) return
        worker.execute {
            record {
                val day = Instant.now().atOffset(ZoneOffset.ofHours(8)).toLocalDate().toString()
                if (prefs.getString("active-day", null) == day) {
                    schedule()
                    return@record
                }
                enqueue(listOf(event("app_startup")), prefs.edit().putString("active-day", day))
            }
        }
    }

    fun startTask(task: TaskId, privilege: Privilege, panelOff: Boolean): Run? = record {
        val id = randomId()
        val properties = environment + mapOf(
            "run_id" to id,
            "task_id" to task.name.lowercase(),
            "privilege" to privilege.name.lowercase(),
            "panel_off" to panelOff,
            "game_runtime" to "adb_game",
        )
        val run = Run(id, SystemClock.elapsedRealtime(), properties)
        val active = activePayload(run, UsageStage.PREPARING, emptyMap())
        enqueue(listOf(event("task_start", properties)), prefs.edit().putString("active-run", active))
        run
    }

    fun taskStage(run: Run?, stage: UsageStage, timings: Map<String, Long>) {
        if (run == null) return
        record {
            if (activeRun()?.get("run_id") == run.id) {
                check(prefs.edit().putString("active-run", activePayload(run, stage, timings)).commit())
            }
        }
    }

    fun finishTask(
        run: Run?,
        outcome: UsageOutcome,
        stage: UsageStage,
        reason: String,
        step: StepId?,
        timings: Map<String, Long>,
    ) {
        if (run == null) return
        record {
            if (activeRun()?.get("run_id") != run.id) return@record
            val elapsed = SystemClock.elapsedRealtime() - run.startedMs
            complete(
                run.properties, outcome,
                stage.name.lowercase(), reason, step,
                seconds(timings + ("duration_seconds" to elapsed)),
            )
        }
    }

    fun preflightError(task: TaskId, privilege: Privilege, code: String) {
        record {
            val fields = mapOf("task_id" to task.name.lowercase(), "privilege" to privilege.name.lowercase())
            enqueue(listOf(event("error", fields + errorFields("preflight", code, null))))
        }
    }

    /** 已经落盘的任务开始事件在同一进程里只有一个终态。重开进程时补齐明确中断的一轮。 */
    fun recoverInterrupted() {
        record {
            val active = activeRun() ?: return@record
            val timings = (active["timings"] as? Map<*, *>).orEmpty()
            complete(
                active - setOf("stage", "version", "timings"), UsageOutcome.INTERRUPTED,
                active["stage"] as? String ?: "preparing", "interrupted", null,
                seconds(reportedTimings.mapNotNull { name -> (timings[name] as? Long)?.let { name to it } }.toMap()),
                active["version"] as? String ?: BuildConfig.VERSION_NAME,
            )
        }
    }

    private fun complete(
        properties: Map<String, Any?>,
        outcome: UsageOutcome,
        stage: String,
        reason: String,
        step: StepId?,
        timings: Map<String, Double>,
        version: String = BuildConfig.VERSION_NAME,
    ) {
        val success = outcome == UsageOutcome.SUCCESS
        val events = mutableListOf(event("task_complete", properties + timings + mapOf(
            "outcome" to outcome.name.lowercase(), "success" to success,
        ), version))
        if (!success && outcome != UsageOutcome.STOPPED) {
            events += event("error", properties + errorFields(stage, reason, step), version)
        }
        enqueue(events, prefs.edit().remove("active-run"))
    }

    private fun errorFields(stage: String, code: String, step: StepId?) = buildMap {
        put("stage", stage)
        put("error_type", code.takeIf { it in reportedErrors } ?: "other")
        if (step != null) put("step_id", step.name.lowercase())
    }

    private fun collecting() = enabled && !BuildConfig.DEBUG

    private fun seconds(timings: Map<String, Long>) = timings.mapValues { Math.round(it.value / 100.0) / 10.0 }

    private fun activePayload(run: Run, stage: UsageStage, timings: Map<String, Long>) = Json.encode(
        run.properties + mapOf("stage" to stage.name.lowercase(), "version" to BuildConfig.VERSION_NAME, "timings" to timings),
    )

    private inline fun <T> record(action: () -> T): T? = runCatching {
        synchronized(lock) { if (collecting()) action() else null }
    }.onFailure {
        Log.w("M7AUsage", "Cannot store anonymous usage statistics")
    }.getOrNull()

    @Suppress("UNCHECKED_CAST")
    private fun activeRun() = prefs.getString("active-run", null)?.let { Json.decode(it) as? Map<String, Any?> }

    @Suppress("UNCHECKED_CAST")
    private fun readQueue(): List<Map<String, Any?>> {
        val saved = prefs.getString("queue", null) ?: return emptyList()
        val events = runCatching { Json.decode(saved) as? List<Map<String, Any?>> }.getOrNull().orEmpty()
        val cutoff = Instant.now().minusSeconds(MAX_EVENT_AGE_SECONDS)
        return events.filter { event ->
            runCatching { Instant.parse(event["timestamp"] as String) >= cutoff }.getOrDefault(false)
        }
    }

    private fun event(
        name: String, properties: Map<String, Any?> = emptyMap(), version: String = BuildConfig.VERSION_NAME,
    ): Map<String, Any?> {
        val id = prefs.getString("install-id", null) ?: randomId().also {
            check(prefs.edit().putString("install-id", it).putString("secret", randomId() + randomId()).commit())
        }
        return mapOf(
            "event" to name, "uuid" to id, "event_id" to randomId(),
            "timestamp" to Instant.now().toString(), "version" to version,
            "properties" to environment + properties,
        )
    }

    private fun enqueue(events: List<Map<String, Any?>>, edit: SharedPreferences.Editor = prefs.edit()) {
        val updated = (readQueue() + events).takeLast(MAX_QUEUE)
        check(edit.putString("queue", Json.encode(updated)).commit())
        schedule()
    }

    private fun schedule(delay: Long = FLUSH_DELAY) {
        if (scheduled != null) return
        val expected = generation
        scheduled = worker.schedule({ flush(expected) }, delay, TimeUnit.SECONDS)
    }

    private fun flush(expectedGeneration: Int) {
        val batch = record {
            if (generation != expectedGeneration) return@record null
            val events = readQueue()
            if (events.isEmpty()) {
                prefs.edit().remove("queue").remove("batch").apply()
                return@record null
            }
            val id = checkNotNull(prefs.getString("install-id", null))
            val secret = checkNotNull(prefs.getString("secret", null))
            val queuedBatch = prefs.getString("batch", null)?.let {
                runCatching { Json.decode(it) as? Map<*, *> }.getOrNull()
            }
            val previousId = queuedBatch?.get("id") as? String
            @Suppress("UNCHECKED_CAST")
            val previousEvents = queuedBatch?.get("events") as? List<Map<String, Any?>>
            if (!previousId.isNullOrEmpty() && !previousEvents.isNullOrEmpty()) {
                Batch(generation, id, secret, previousId, previousEvents, registered)
            } else {
                val batchId = randomId()
                val batchEvents = events.take(BATCH_SIZE)
                check(prefs.edit().putString("batch", Json.encode(mapOf("id" to batchId, "events" to batchEvents))).commit())
                Batch(generation, id, secret, batchId, batchEvents, registered)
            }
        } ?: run {
            synchronized(lock) {
                if (generation == expectedGeneration) {
                    scheduled = null
                    if (collecting() && readQueue().isNotEmpty()) schedule()
                }
            }
            return
        }
        val status = runCatching {
            if (!batch.registered) {
                val registration = Json.encode(mapOf(
                    "uuid" to batch.id, "secret" to batch.secret, "client_platform" to "android",
                )).encodeToByteArray()
                val response = post("/register", registration, batch.generation)
                if (response != 200 && response != 201) return@runCatching response
                synchronized(lock) { if (generation == batch.generation) registered = true }
            }
            post("", signedUsageBatch(batch.events, batch.batchId, batch.secret), batch.generation)
        }.getOrDefault(0)
        synchronized(lock) {
            if (!collecting() || generation != batch.generation) return
            scheduled = null
            val permanent = status in 400..499 && status != 408 && status != 429
            if (status == 204 || permanent) {
                val sent = batch.events.mapTo(hashSetOf()) { it["event_id"] }
                prefs.edit().remove("batch").putString("queue", Json.encode(readQueue().filterNot { it["event_id"] in sent })).apply()
                retrySeconds = FLUSH_DELAY
            } else {
                retrySeconds = (retrySeconds * 2).coerceAtMost(300L)
            }
            if (readQueue().isNotEmpty()) schedule(retrySeconds)
        }
    }

    private data class Batch(
        val generation: Int, val id: String, val secret: String, val batchId: String,
        val events: List<Map<String, Any?>>, val registered: Boolean,
    )

    private fun post(path: String, body: ByteArray, expectedGeneration: Int): Int {
        val request = (URI.create(TELEMETRY_URL + path).toURL().openConnection() as HttpsURLConnection).apply {
            requestMethod = "POST"
            doOutput = true
            instanceFollowRedirects = false
            connectTimeout = 5000
            readTimeout = 5000
            setRequestProperty("Content-Type", "application/json")
            setFixedLengthStreamingMode(body.size)
        }
        try {
            synchronized(lock) {
                if (!collecting() || generation != expectedGeneration) return 0
                connection = request
            }
            request.outputStream.use {
                if (synchronized(lock) { !collecting() || generation != expectedGeneration }) return 0
                it.write(body)
            }
            return request.responseCode
        } finally {
            synchronized(lock) { if (connection === request) connection = null }
            request.disconnect()
        }
    }

    companion object {
        @Volatile private var instance: UsageTelemetry? = null

        fun get(context: Context): UsageTelemetry = instance ?: synchronized(this) {
            instance ?: UsageTelemetry(context.applicationContext).also { instance = it }
        }
    }
}
