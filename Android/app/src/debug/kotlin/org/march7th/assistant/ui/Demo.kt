package org.march7th.assistant.ui

import android.content.Intent
import org.march7th.assistant.GameState
import org.march7th.assistant.LogCategory
import org.march7th.assistant.LogEntry
import org.march7th.assistant.LogLevel
import org.march7th.assistant.PermissionState
import org.march7th.assistant.Privilege
import org.march7th.assistant.ServiceState
import org.march7th.assistant.StepResult
import org.march7th.assistant.StepStatus
import org.march7th.assistant.TaskConfig
import org.march7th.assistant.TaskId
import org.march7th.assistant.TaskPhase
import org.march7th.assistant.TaskState
import org.march7th.assistant.finished
import org.march7th.assistant.onStepEvent
import org.march7th.assistant.plannedSteps

/**
 * 调试构建里用模拟数据看各个状态下的界面，不启动任务：
 * adb shell am start -n org.march7th.assistant/.MainActivity --es demo running --es tab LOGS --es page STATUS
 * demo 取下面的场景名，其余值当作错误码；task 取一个 TaskId，默认 ROUTINE；tab 取 Tab，page 取 SubPage，theme 取 ThemeMode。
 */
internal fun demoFrom(intent: Intent): Demo? {
    val name = intent.getStringExtra("demo") ?: return null
    val task = TaskId.entries.firstOrNull { it.name == intent.getStringExtra("task") } ?: TaskId.ROUTINE
    // 演示用周一，历战余响不会因为开始日期被跳过。
    val planned = plannedSteps(task, TaskConfig(), 1)
    val ready = TaskState(permission = PermissionState.READY, task = task)
    val live = ready.copy(service = ServiceState.CONNECTED, displayId = 65, gameDisplayId = 65, game = GameState.STARTING)
    val state = when (name) {
        "ready" -> ready
        "install" -> ready.copy(permission = PermissionState.NOT_INSTALLED)
        "start" -> ready.copy(permission = PermissionState.NOT_RUNNING)
        "grant" -> ready.copy(permission = PermissionState.NOT_AUTHORIZED)
        "root" -> ready.copy(privilege = Privilege.ROOT, permission = PermissionState.NOT_AUTHORIZED)
        "root-unchecked" -> ready.copy(privilege = Privilege.ROOT, permission = PermissionState.NOT_CHECKED)
        "idle" -> ready.copy(config = TaskConfig(powerEnable = false, rewardEnable = false, dailyEnable = false))
        "preparing" -> ready.copy(phase = TaskPhase.PREPARING, service = ServiceState.STARTING, steps = planned)
        "launching" -> live.copy(phase = TaskPhase.WAITING_FOR_GAME, steps = planned)
        "flashing" -> live.copy(phase = TaskPhase.WAITING_FOR_GAME, game = GameState.FLASHING, gameDisplayId = 0, steps = planned)
        "returning" -> live.copy(phase = TaskPhase.WAITING_FOR_GAME, game = GameState.RETURNING, steps = planned)
        "login" -> live.copy(phase = TaskPhase.WAITING_FOR_GAME, game = GameState.MANUAL_LOGIN, gameDisplayId = 0, steps = planned)
        "running" -> live.copy(phase = TaskPhase.RUNNING, game = GameState.READY, steps = running(task, planned))
        "panel" -> live.copy(phase = TaskPhase.RUNNING, game = GameState.READY, panelOff = true, steps = running(task, planned))
        "stopping" -> live.copy(phase = TaskPhase.STOPPING, game = GameState.READY, steps = running(task, planned))
        "cleaning" -> ready.copy(phase = TaskPhase.CLEANING, service = ServiceState.CLEANING, steps = running(task, planned))
        "done" -> ready.copy(phase = TaskPhase.SUCCEEDED, steps = done(planned), summary = summary(task))
        "partial" -> ready.copy(phase = TaskPhase.FAILED, errorCode = "task_failed", steps = partial(task, planned))
        "stopped" -> ready.copy(phase = TaskPhase.STOPPED, steps = running(task, planned).finished("stopped"))
        // 息屏和运行时错误发生在执行途中，其余错误发生在步骤开始之前。
        in MID_RUN_ERRORS -> ready.copy(phase = TaskPhase.FAILED, errorCode = name, steps = running(task, planned).finished(name))
        else -> ready.copy(phase = TaskPhase.FAILED, errorCode = name, steps = planned)
    }
    val logs = when {
        name in setOf("ready", "install", "start", "grant", "root", "root-unchecked", "idle") -> emptyList()
        state.phase == TaskPhase.FAILED ->
            SAMPLE + FAILURE + sample("21:47:10", "本轮结束：${state.errorCode}", LogLevel.ERROR, LogCategory.APP)
        state.phase == TaskPhase.SUCCEEDED ->
            SAMPLE + sample("21:47:02", "本轮结束：success", category = LogCategory.APP)
        else -> SAMPLE + sample("21:47:02", "ADB 看门狗 frames_resumed", category = LogCategory.DEVICE)
    }
    return Demo(
        state, logs,
        Tab.entries.firstOrNull { it.name == intent.getStringExtra("tab") } ?: Tab.HOME,
        SubPage.entries.firstOrNull { it.name == intent.getStringExtra("page") },
        ThemeMode.entries.firstOrNull { it.name == intent.getStringExtra("theme") },
    )
}

private val MID_RUN_ERRORS = setOf("device_asleep", "runtime_error")
private const val POWER_SUMMARY = "已完成 6 次挑战，剩余开拓力 3/300"
private const val DAILY_SUMMARY = "每日实训活跃度 500/500"

/** 日常做到第二个启用的步骤，单个任务正在进行它唯一的一步。 */
private fun running(task: TaskId, planned: List<StepResult>): List<StepResult> = when (task) {
    TaskId.ROUTINE -> planned
        .onStepEvent("清体力", "started", null).onStepEvent("清体力", "succeeded", POWER_SUMMARY)
        .onStepEvent("日常领奖", "started", null)
    else -> planned.onStepEvent(planned.single().name, "started", null)
}

private fun done(planned: List<StepResult>): List<StepResult> = planned.map { step ->
    if (step.status != StepStatus.PENDING) {
        step
    } else {
        step.copy(
            status = StepStatus.DONE,
            detail = when (step.name) {
                "清体力" -> POWER_SUMMARY
                "每日实训" -> DAILY_SUMMARY
                else -> null
            },
        )
    }
}

private fun summary(task: TaskId) = when (task) {
    TaskId.ROUTINE -> "$POWER_SUMMARY；$DAILY_SUMMARY"
    TaskId.DAILY -> DAILY_SUMMARY
    TaskId.POWER -> POWER_SUMMARY
}

/** 领奖一步失败，其余照常完成；单个任务就是唯一的一步失败。 */
private fun partial(task: TaskId, planned: List<StepResult>): List<StepResult> {
    val failing = if (task == TaskId.ROUTINE) "日常领奖" else planned.single().name
    val reason = if (task == TaskId.ROUTINE) "邮件失败：未确认邮箱附件状态" else "每日实训页：400 档礼盒点击后仍显示可领取"
    return done(planned).map { if (it.name == failing) it.copy(status = StepStatus.FAILED, detail = reason) else it }
}

private fun sample(
    time: String, message: String, level: LogLevel = LogLevel.INFO, category: LogCategory = LogCategory.TASK,
    heading: Boolean = false,
) = LogEntry(time, level, category, message, heading)

private val SAMPLE = listOf(
    sample("21:44:15", "Python 启动与资源准备耗时 2080 ms", category = LogCategory.APP),
    sample("21:44:15", "强制使用 ONNXRuntime(CPU) 初始化 OCR", LogLevel.WARNING),
    sample("21:44:16", "OCR 运行时就绪，用时 1.94 秒"),
    sample("21:44:17", "设备端服务启动耗时 1081 ms", category = LogCategory.APP),
    sample("21:44:17", "已创建 1280×720 虚拟屏，display 65"),
    sample("21:44:52", "ADB 看门狗 task_display_changed：display 65 → 0", category = LogCategory.DEVICE),
    sample("21:44:53", "ADB 看门狗 move_back_succeeded：display 65", category = LogCategory.DEVICE),
    sample("21:45:37", "ADB 已点按标题进入"),
    sample("21:46:10", "游戏画面就绪，用时 113.2 秒"),
    sample("21:46:10", "开始触屏每日实训", heading = true),
    sample("21:46:11", "当前界面：主界面"),
    sample("21:46:19", "切换到：星际和平指南-每日实训"),
    sample("21:46:22", "当前活跃度 300/500"),
    sample("21:47:01", "派遣委托或收取1次委托奖励：已完成"),
    sample("21:47:01", "档位奖励：100 档已领取，200 档已领取，300 档已领取，400 档未达成，500 档未达成"),
    sample("21:47:01", "每日实训活跃度 300/500"),
)

private val FAILURE = listOf(
    sample("21:47:03", "切换界面超时，正在重试", LogLevel.WARNING),
    sample("21:47:09", "邮件失败：未确认邮箱附件状态", LogLevel.ERROR),
)
