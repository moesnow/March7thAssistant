package top.m7a

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class TaskStepsTest {
    private val monday = 1
    private val sunday = 7

    private fun statuses(steps: List<StepResult>) = steps.associate { it.step to it.status }

    private fun pending(id: StepId) = StepResult(id, id.pythonName, StepStatus.PENDING)
    private fun disabled(id: StepId, startDay: Int? = null) = StepResult(id, id.pythonName, StepStatus.DISABLED, startDay = startDay)
    private fun List<StepResult>.of(id: StepId) = single { it.step == id }

    @Test
    fun routineByDefaultSkipsTheBuildTargetAndTheEcho() {
        assertEquals(
            listOf(
                pending(StepId.REDEMPTION), disabled(StepId.BUILD_TARGET), disabled(StepId.ECHO),
                pending(StepId.POWER), pending(StepId.REWARDS), pending(StepId.DAILY),
            ),
            plannedSteps(TaskId.ROUTINE, TaskConfig(), monday),
        )
    }

    @Test
    fun redemptionNeedsTheRewardSwitchButNoOtherReward() {
        fun steps(config: TaskConfig) = statuses(plannedSteps(TaskId.ROUTINE, config, monday))
        val none = TaskConfig(dispatch = false, mail = false, assist = false, srpass = false, message = false)

        assertEquals(StepStatus.DISABLED, steps(TaskConfig(redemption = false))[StepId.REDEMPTION])
        assertEquals(StepStatus.DISABLED, steps(TaskConfig(rewardEnable = false))[StepId.REDEMPTION])
        // 兑换码自成一步，不算在领奖这一步里。
        assertEquals(StepStatus.PENDING, steps(none)[StepId.REDEMPTION])
        assertEquals(StepStatus.DISABLED, steps(none)[StepId.REWARDS])
        assertEquals(StepStatus.DISABLED, steps(none.copy(srpass = true, redemption = false))[StepId.REDEMPTION])
    }

    @Test
    fun buildTargetIsReadOnlyWhenTheRoutineSpendsPower() {
        fun target(config: TaskConfig) = statuses(plannedSteps(TaskId.ROUTINE, config, monday))[StepId.BUILD_TARGET]

        assertEquals(StepStatus.PENDING, target(TaskConfig(buildTarget = true)))
        assertEquals(StepStatus.DISABLED, target(TaskConfig(buildTarget = true, powerEnable = false)))
        // 单独运行清体力时，培养目标在清体力这一步里读取。
        assertEquals(listOf(pending(StepId.POWER)), plannedSteps(TaskId.POWER, TaskConfig(buildTarget = true), monday))
    }

    @Test
    fun echoNeedsPowerAndItsStartDay() {
        val echo = TaskConfig(echoEnable = true, echoStartDay = 3)

        assertEquals(disabled(StepId.ECHO, startDay = 3), plannedSteps(TaskId.ROUTINE, echo, 2).of(StepId.ECHO))
        assertEquals(pending(StepId.ECHO), plannedSteps(TaskId.ROUTINE, echo, 3).of(StepId.ECHO))
        assertEquals(pending(StepId.ECHO), plannedSteps(TaskId.ROUTINE, echo, sunday).of(StepId.ECHO))
        // 关闭清体力时，历战余响和清体力都跳过，不提开始日期。
        val noPower = plannedSteps(TaskId.ROUTINE, echo.copy(powerEnable = false), 2)
        assertEquals(disabled(StepId.ECHO), noPower.of(StepId.ECHO))
        assertEquals(disabled(StepId.POWER), noPower.of(StepId.POWER))
    }

    @Test
    fun rewardsNeedTheSwitchAndAtLeastOneReward() {
        fun rewards(config: TaskConfig) = statuses(plannedSteps(TaskId.ROUTINE, config, monday))[StepId.REWARDS]
        val none = TaskConfig(dispatch = false, mail = false, assist = false, srpass = false, message = false)

        assertEquals(StepStatus.DISABLED, rewards(none))
        assertEquals(StepStatus.DISABLED, rewards(TaskConfig(rewardEnable = false)))
        // 每日实训的奖励不算在领奖这一步里。
        assertEquals(StepStatus.DISABLED, rewards(none.copy(quest = true)))
        assertEquals(StepStatus.PENDING, rewards(none.copy(message = true)))
    }

    @Test
    fun dailyTrainingRunsWhenItCompletesOrCollects() {
        fun daily(config: TaskConfig) = plannedSteps(TaskId.DAILY, config, monday).single().status

        assertEquals(StepStatus.PENDING, daily(TaskConfig()))
        assertEquals(StepStatus.PENDING, daily(TaskConfig(dailyEnable = false)))
        assertEquals(StepStatus.PENDING, daily(TaskConfig(rewardEnable = false)))
        assertEquals(StepStatus.DISABLED, daily(TaskConfig(dailyEnable = false, rewardEnable = false)))
        assertEquals(StepStatus.DISABLED, daily(TaskConfig(dailyEnable = false, quest = false)))
        assertEquals(StepStatus.DISABLED, statuses(plannedSteps(TaskId.ROUTINE, TaskConfig(dailyEnable = false, quest = false), monday))[StepId.DAILY])
    }

    @Test
    fun redeemNeedsAtLeastOneCodeButNotTheRewardSwitches() {
        assertEquals(listOf(disabled(StepId.REDEMPTION)), plannedSteps(TaskId.REDEEM, TaskConfig(), monday))
        val codes = TaskConfig(redemptionCodes = listOf("ABC123"), rewardEnable = false, redemption = false)
        assertEquals(listOf(pending(StepId.REDEMPTION)), plannedSteps(TaskId.REDEEM, codes, monday))
    }

    @Test
    fun powerAloneIgnoresThePowerSwitch() {
        assertEquals(listOf(pending(StepId.POWER)), plannedSteps(TaskId.POWER, TaskConfig(powerEnable = false), monday))
    }

    @Test
    fun idleMeansNoPendingStep() {
        val nothing = TaskConfig(powerEnable = false, rewardEnable = false, dailyEnable = false)

        assertTrue(plannedSteps(TaskId.ROUTINE, nothing, monday).idle)
        assertTrue(plannedSteps(TaskId.DAILY, nothing, monday).idle)
        assertTrue(plannedSteps(TaskId.REDEEM, nothing, monday).idle)
        assertFalse(plannedSteps(TaskId.POWER, nothing, monday).idle)
        assertFalse(plannedSteps(TaskId.ROUTINE, nothing.copy(dailyEnable = true), monday).idle)
    }

    @Test
    fun eventsMoveStepsThroughTheirStates() {
        var steps = plannedSteps(TaskId.ROUTINE, TaskConfig(), monday)
        steps = steps.onStepEvent("兑换码", "started", null)
        assertEquals(StepId.REDEMPTION, steps.progress()!!.step.step)
        steps = steps.onStepEvent("兑换码", "succeeded", null)
        steps = steps.onStepEvent("查询支援实训", "started", null).onStepEvent("查询支援实训", "succeeded", null)
        // 未启用的历战余响照样会被 Python 报开始和成功。
        steps = steps.onStepEvent("历战余响", "started", null).onStepEvent("历战余响", "succeeded", null)
        steps = steps.onStepEvent("清体力", "started", null)
        assertEquals(StepStatus.RUNNING, statuses(steps)[StepId.POWER])
        assertEquals(StepId.POWER, steps.progress()!!.step.step)
        assertEquals(2, steps.progress()!!.number)
        assertEquals(4, steps.progress()!!.total)
        steps = steps.onStepEvent("清体力", "succeeded", "已完成 6 次挑战，剩余开拓力 3/300")
            .onStepEvent("日常领奖", "started", null)
            .onStepEvent("日常领奖", "failed", "邮件失败：未确认邮箱附件状态")
            .onStepEvent("每日实训", "started", null)
        assertEquals(4, steps.progress()!!.number)
        steps = steps.onStepEvent("每日实训", "succeeded", "每日实训活跃度 500/500")

        assertEquals(
            listOf(
                StepResult(StepId.REDEMPTION, "兑换码", StepStatus.DONE),
                disabled(StepId.BUILD_TARGET),
                disabled(StepId.ECHO),
                StepResult(StepId.POWER, "清体力", StepStatus.DONE, "已完成 6 次挑战，剩余开拓力 3/300"),
                StepResult(StepId.REWARDS, "日常领奖", StepStatus.FAILED, "邮件失败：未确认邮箱附件状态"),
                StepResult(StepId.DAILY, "每日实训", StepStatus.DONE, "每日实训活跃度 500/500"),
            ),
            steps,
        )
        assertNull(steps.progress())
        assertEquals(steps, steps.finished("task_failed"))
    }

    @Test
    fun unknownStepsAppearOnlyWhenTheyFail() {
        val steps = plannedSteps(TaskId.ROUTINE, TaskConfig(), monday)

        assertEquals(steps, steps.onStepEvent("查询支援实训", "started", null).onStepEvent("查询支援实训", "succeeded", null))
        assertEquals(
            steps + StepResult(null, "查询支援实训", StepStatus.FAILED, "未能查询支援实训"),
            steps.onStepEvent("查询支援实训", "failed", "未能查询支援实训"),
        )
    }

    @Test
    fun aFailureOverridesAnyStateButSuccessNeedsAStart() {
        val echo = plannedSteps(TaskId.ROUTINE, TaskConfig(echoEnable = true, echoStartDay = 7), monday)

        assertEquals(echo, echo.onStepEvent("清体力", "succeeded", "摘要"))
        assertEquals(
            StepResult(StepId.ECHO, "历战余响", StepStatus.FAILED, "原因"),
            echo.onStepEvent("历战余响", "failed", "原因").of(StepId.ECHO),
        )
        assertEquals(StepStatus.FAILED, echo.onStepEvent("清体力", "failed", null).of(StepId.POWER).status)
    }

    @Test
    fun finishingMarksOnlyTheRunningStep() {
        val running = plannedSteps(TaskId.ROUTINE, TaskConfig(), monday)
            .onStepEvent("兑换码", "started", null).onStepEvent("兑换码", "succeeded", null)
            .onStepEvent("清体力", "started", null).onStepEvent("清体力", "succeeded", null)
            .onStepEvent("日常领奖", "started", null)

        assertEquals(
            listOf(
                StepStatus.DONE, StepStatus.DISABLED, StepStatus.DISABLED,
                StepStatus.DONE, StepStatus.STOPPED, StepStatus.PENDING,
            ),
            running.finished("stopped").map { it.status },
        )
        val failed = running.finished("device_asleep")
        assertEquals(StepResult(StepId.REWARDS, "日常领奖", StepStatus.FAILED), failed.of(StepId.REWARDS))
        assertEquals(StepStatus.PENDING, failed.of(StepId.DAILY).status)
    }

    @Test
    fun progressReplacesThePlanWithTheValidItems() {
        val progress = parseProgress(
            """{"power_plan": [["拟造花萼（金）", "回忆之蕾", 1], ["拟造花萼（金）", "回忆之蕾", 0],
                ["未知副本", "x", 2], ["侵蚀隧洞", "无", 1], ["凝滞虚影", "空海之形", 2.5], ["侵蚀隧洞", "睿治之径"],
                "坏数据", ["历战余响", "寒潭指月", 3]],
               "last_run_timestamp": 1762900000.25, "echo_of_war_timestamp": 0,
               "already_used_codes": ["OLD1", "", 3, "OLD1", "NEW1"]}"""
        )!!

        assertEquals(
            listOf(PlanItem(InstanceType.GOLDEN_CALYX, "回忆之蕾", 1), PlanItem(InstanceType.ECHO, "寒潭指月", 3)),
            progress.plan,
        )
        assertEquals(1762900000250L, progress.lastDailyDone)
        assertNull(progress.lastEchoDone)
        assertEquals(listOf("OLD1", "NEW1"), progress.usedCodes)
    }

    @Test
    fun progressMovesUsedCodesOutOfTheRedeemList() {
        val config = TaskConfig(
            powerPlan = listOf(PlanItem(InstanceType.CAVERN, "睿治之径", 2)), redemptionCodes = listOf("ABC123", "DEF456"),
        )
        val updated = config.withProgress(TaskProgress(null, null, null, listOf("OLD1", "ABC123")))

        assertEquals(listOf("DEF456"), updated.redemptionCodes)
        assertEquals(listOf("OLD1", "ABC123"), updated.usedCodes)
        assertEquals(config.powerPlan, updated.powerPlan)
        // 没交回兑换码时只换体力计划。
        assertEquals(config.copy(powerPlan = emptyList()), config.withProgress(TaskProgress(emptyList(), null, null)))
    }

    @Test
    fun progressWithoutAPlanKeepsTheCurrentOne() {
        assertEquals(emptyList<PlanItem>(), parseProgress("""{"power_plan": []}""")!!.plan)
        assertNull(parseProgress("""{"power_plan": []}""")!!.usedCodes)
        assertNull(parseProgress("""{"power_plan": null, "last_run_timestamp": 5}""")!!.plan)
        assertNull(parseProgress("不是 JSON"))
        assertNull(parseProgress("[]"))
    }
}
