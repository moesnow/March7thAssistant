package top.m7a

/**
 * 本轮开始时的步骤，状态是 PENDING 或 DISABLED。
 * 规则与 tasks.touch 一致：Python 会跳过或什么都不做的步骤，这里就是 DISABLED。today 是星期几，周一为 1。
 */
fun plannedSteps(task: TaskId, config: TaskConfig, today: Int): List<StepResult> {
    fun step(id: StepId, enabled: Boolean, startDay: Int? = null) = StepResult(
        id, id.pythonName,
        if (enabled && startDay == null) StepStatus.PENDING else StepStatus.DISABLED,
        startDay = startDay,
    )
    // 不补做也不领取时，每日实训只记一条日志就结束。
    val daily = config.dailyEnable || (config.rewardEnable && config.quest)
    return when (task) {
        TaskId.ROUTINE -> {
            val echo = config.powerEnable && config.echoEnable
            val rewards = config.rewardEnable &&
                (config.dispatch || config.mail || config.assist || config.srpass || config.message)
            listOf(
                step(StepId.REDEMPTION, config.rewardEnable && config.redemption),
                // 「日常」里只有历战余响和清体力用到培养目标，两者都随清体力关闭。
                step(StepId.BUILD_TARGET, config.powerEnable && config.buildTarget),
                step(StepId.ECHO, echo, config.echoStartDay.takeIf { echo && today < it }),
                step(StepId.POWER, config.powerEnable),
                step(StepId.REWARDS, rewards),
                step(StepId.DAILY, daily),
            )
        }
        TaskId.DAILY -> listOf(step(StepId.DAILY, daily))
        // 单独运行清体力不受「启用清体力」影响。
        TaskId.POWER -> listOf(step(StepId.POWER, true))
        // 和电脑版工具箱一样只看填写的兑换码，不受领取奖励的开关影响。
        TaskId.REDEEM -> listOf(step(StepId.REDEMPTION, config.redemptionCodes.isNotEmpty()))
    }
}

/** 所选任务这一轮什么都不会做。 */
val List<StepResult>.idle: Boolean
    get() = none { it.status == StepStatus.PENDING }

/**
 * 处理 Python 报来的步骤事件，state 是 started、succeeded 或 failed。
 * 未启用的步骤 Python 也会报开始和成功，这里忽略；表外的步骤只在失败时追加一行。
 */
fun List<StepResult>.onStepEvent(name: String, state: String, detail: String?): List<StepResult> {
    val id = StepId.of(name)
    val index = indexOfFirst { if (id != null) it.step == id else it.step == null && it.name == name }
    if (index < 0) {
        return if (state == "failed") this + StepResult(id, name, StepStatus.FAILED, detail) else this
    }
    val current = this[index]
    val next = when (state) {
        "started" -> current.copy(status = StepStatus.RUNNING).takeIf { current.status == StepStatus.PENDING }
        "succeeded" -> current.copy(status = StepStatus.DONE, detail = detail).takeIf { current.status == StepStatus.RUNNING }
        "failed" -> current.copy(status = StepStatus.FAILED, detail = detail, startDay = null)
        else -> null
    } ?: return this
    return toMutableList().also { it[index] = next }
}

/**
 * 一轮结束时收尾：停止时进行中的步骤算已停止，其他失败算没有完成且没有原因。
 * 没开始的步骤保持 PENDING，界面显示「没有执行」。
 */
fun List<StepResult>.finished(result: String): List<StepResult> = map {
    if (it.status != StepStatus.RUNNING) {
        it
    } else when (result) {
        "success" -> it.copy(status = StepStatus.DONE)
        "stopped" -> it.copy(status = StepStatus.STOPPED)
        else -> it.copy(status = StepStatus.FAILED, detail = null)
    }
}

/** 正在进行的步骤，以及它在启用的步骤里排第几（从 1 开始）、启用的步骤共几个。 */
class StepProgress(val step: StepResult, val number: Int, val total: Int)

fun List<StepResult>.progress(): StepProgress? {
    val enabled = filter { it.step != null && it.status != StepStatus.DISABLED }
    val index = enabled.indexOfFirst { it.status == StepStatus.RUNNING }
    return if (index < 0) null else StepProgress(enabled[index], index + 1, enabled.size)
}

/**
 * 一轮里 Python 交回的进度。plan 为 null 表示没有可用的计划数据；时间是毫秒，没有记录为 null。
 * usedCodes 是 Python 记下的已使用兑换码，为 null 表示没有交回。
 */
class TaskProgress(
    val plan: List<PlanItem>?,
    val lastDailyDone: Long?,
    val lastEchoDone: Long?,
    val usedCodes: List<String>? = null,
)

/** 解析 reportProgress 的 JSON，整份读不出时返回 null。体力计划逐项校验，不合格的项丢弃。 */
fun parseProgress(json: String): TaskProgress? {
    val root = runCatching { Json.decode(json) }.getOrNull() as? Map<*, *> ?: return null
    val plan = (root["power_plan"] as? List<*>)?.mapNotNull { item ->
        val row = item as? List<*>
        val type = InstanceType.of(row?.getOrNull(0) as? String)
        val name = row?.getOrNull(1) as? String
        val count = (row?.getOrNull(2) as? Long)?.takeIf { it in 1L..TaskConfig.MAX_PLAN_COUNT }
        if (row?.size == 3 && type != null && !name.isNullOrBlank() && name != "无" && count != null) {
            PlanItem(type, name, count.toInt())
        } else {
            null
        }
    }?.take(TaskConfig.MAX_PLAN_ITEMS)
    return TaskProgress(
        plan, epochMillis(root["last_run_timestamp"]), epochMillis(root["echo_of_war_timestamp"]),
        parseUsedCodes(root["already_used_codes"]),
    )
}

/** 把进度并入设置：体力计划换成剩下的；已使用的兑换码以 Python 为准，并移出待兑换列表。 */
fun TaskConfig.withProgress(progress: TaskProgress): TaskConfig {
    val planned = progress.plan?.let { copy(powerPlan = it) } ?: this
    val used = progress.usedCodes ?: return planned
    return planned.copy(usedCodes = used, redemptionCodes = planned.redemptionCodes - used.toSet())
}

/** Python 用秒记时间戳，0 表示没有记录。 */
private fun epochMillis(seconds: Any?): Long? =
    (seconds as? Number)?.toDouble()?.takeIf { it > 0 && it.isFinite() }?.let { (it * 1000).toLong() }
