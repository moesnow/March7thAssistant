package org.march7th.assistant.ui

import android.content.Intent
import org.march7th.assistant.GameState
import org.march7th.assistant.PermissionState
import org.march7th.assistant.Privilege
import org.march7th.assistant.ServiceState
import org.march7th.assistant.TaskId
import org.march7th.assistant.TaskPhase
import org.march7th.assistant.TaskState

/**
 * 调试构建里用模拟数据看各个状态下的界面，不启动任务：
 * adb shell am start -n org.march7th.assistant/.MainActivity --es demo running --es tab LOGS --es page STATUS
 * demo 取下面的场景名，其余值当作错误码；task 取 TaskId，tab 取 Tab，page 取 SubPage，theme 取 ThemeMode。
 */
internal fun demoFrom(intent: Intent): Demo? {
    val name = intent.getStringExtra("demo") ?: return null
    val task = TaskId.entries.firstOrNull { it.name == intent.getStringExtra("task") } ?: TaskId.DAILY
    val ready = TaskState(permission = PermissionState.READY, task = task)
    val live = ready.copy(service = ServiceState.CONNECTED, displayId = 65, gameDisplayId = 65, game = GameState.STARTING)
    val state = when (name) {
        "ready" -> ready
        "install" -> ready.copy(permission = PermissionState.NOT_INSTALLED)
        "start" -> ready.copy(permission = PermissionState.NOT_RUNNING)
        "grant" -> ready.copy(permission = PermissionState.NOT_AUTHORIZED)
        "root" -> ready.copy(privilege = Privilege.ROOT, permission = PermissionState.NOT_AUTHORIZED)
        "preparing" -> ready.copy(phase = TaskPhase.PREPARING, service = ServiceState.STARTING)
        "launching" -> live.copy(phase = TaskPhase.WAITING_FOR_GAME)
        "returning" -> live.copy(phase = TaskPhase.WAITING_FOR_GAME, game = GameState.RETURNING, gameDisplayId = 0)
        "login" -> live.copy(phase = TaskPhase.WAITING_FOR_GAME, game = GameState.MANUAL_LOGIN, gameDisplayId = 0)
        "running" -> live.copy(phase = TaskPhase.RUNNING, game = GameState.READY)
        "panel" -> live.copy(phase = TaskPhase.RUNNING, game = GameState.READY, panelOff = true)
        "stopping" -> live.copy(phase = TaskPhase.STOPPING, game = GameState.READY)
        "cleaning" -> ready.copy(phase = TaskPhase.CLEANING, service = ServiceState.CLEANING)
        "done" -> ready.copy(phase = TaskPhase.SUCCEEDED)
        "stopped" -> ready.copy(phase = TaskPhase.STOPPED)
        else -> ready.copy(phase = TaskPhase.FAILED, errorCode = name)
    }
    val logs = when {
        name in setOf("ready", "install", "start", "grant", "root") -> emptyList()
        state.phase == TaskPhase.FAILED -> SAMPLE + FAILURE + "本轮结束：$name"
        state.phase == TaskPhase.SUCCEEDED -> SAMPLE + "本轮结束：success"
        else -> SAMPLE
    }
    return Demo(
        state, logs,
        Tab.entries.firstOrNull { it.name == intent.getStringExtra("tab") } ?: Tab.HOME,
        SubPage.entries.firstOrNull { it.name == intent.getStringExtra("page") },
        ThemeMode.entries.firstOrNull { it.name == intent.getStringExtra("theme") },
    )
}

private val SAMPLE = listOf(
    "Python 启动与资源准备耗时 2080 ms",
    "21:44:15 | WARNING | 强制使用 ONNXRuntime(CPU) 初始化 OCR",
    "21:44:16 | INFO | OCR 运行时就绪，用时 1.94 秒",
    "设备端服务启动耗时 1081 ms",
    "21:44:17 | INFO | 已创建 1280×720 虚拟屏，display 65",
    "21:44:52 | INFO | ADB 看门狗 task_display_changed：{'event': 'task_display_changed', 'event_seq': 3, 'frame_seq': 251, 'from': 65, 'to': 0, 'stack_id': 172, 'task_id': 181, 'target_display_id': 65}",
    "21:44:53 | INFO | ADB 看门狗 move_back_succeeded：{'event': 'move_back_succeeded', 'event_seq': 8, 'stack_id': 172, 'task_id': 181, 'display_id': 65, 'attempt': 1, 'elapsed_ms': 538}",
    "21:45:37 | INFO | ADB 已点按标题进入",
    "21:46:10 | INFO | 游戏画面就绪，用时 113.2 秒",
    "21:46:10 | INFO | ================================================= 开始触屏每日实训 ==================================================",
    "21:46:11 | INFO | 当前界面：主界面",
    "21:46:19 | INFO | 切换到：星际和平指南-每日实训",
    "21:46:22 | INFO | 当前活跃度 300/500",
    "21:47:01 | INFO | 派遣委托或收取1次委托奖励：已完成",
    "21:47:01 | INFO | 档位奖励：100 档已领取，200 档已领取，300 档已领取，400 档未达成，500 档未达成",
    "21:47:01 | INFO | 每日实训活跃度 300/500",
)

private val FAILURE = listOf(
    "21:47:03 | WARNING | 切换界面超时，正在重试",
    "21:47:09 | ERROR | 每日实训页：400 档礼盒点击后仍显示可领取",
)
