package org.march7th.assistant

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

    @Test
    fun routineByDefaultSkipsOnlyTheEcho() {
        assertEquals(
            listOf(disabled(StepId.ECHO), pending(StepId.POWER), pending(StepId.REWARDS), pending(StepId.DAILY)),
            plannedSteps(TaskId.ROUTINE, TaskConfig(), monday),
        )
    }

    @Test
    fun echoNeedsPowerAndItsStartDay() {
        val echo = TaskConfig(echoEnable = true, echoStartDay = 3)

        assertEquals(disabled(StepId.ECHO, startDay = 3), plannedSteps(TaskId.ROUTINE, echo, 2).first())
        assertEquals(pending(StepId.ECHO), plannedSteps(TaskId.ROUTINE, echo, 3).first())
        assertEquals(pending(StepId.ECHO), plannedSteps(TaskId.ROUTINE, echo, sunday).first())
        // 关闭清体力时，历战余响和清体力都跳过，不提开始日期。
        val noPower = plannedSteps(TaskId.ROUTINE, echo.copy(powerEnable = false), 2)
        assertEquals(disabled(StepId.ECHO), noPower[0])
        assertEquals(disabled(StepId.POWER), noPower[1])
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
    fun powerAloneIgnoresThePowerSwitch() {
        assertEquals(listOf(pending(StepId.POWER)), plannedSteps(TaskId.POWER, TaskConfig(powerEnable = false), monday))
    }

    @Test
    fun idleMeansNoPendingStep() {
        val nothing = TaskConfig(powerEnable = false, rewardEnable = false, dailyEnable = false)

        assertTrue(plannedSteps(TaskId.ROUTINE, nothing, monday).idle)
        assertTrue(plannedSteps(TaskId.DAILY, nothing, monday).idle)
        assertFalse(plannedSteps(TaskId.POWER, nothing, monday).idle)
        assertFalse(plannedSteps(TaskId.ROUTINE, nothing.copy(dailyEnable = true), monday).idle)
    }

    @Test
    fun eventsMoveStepsThroughTheirStates() {
        var steps = plannedSteps(TaskId.ROUTINE, TaskConfig(), monday)
        steps = steps.onStepEvent("查询支援实训", "started", null).onStepEvent("查询支援实训", "succeeded", null)
        // 未启用的历战余响照样会被 Python 报开始和成功。
        steps = steps.onStepEvent("历战余响", "started", null).onStepEvent("历战余响", "succeeded", null)
        steps = steps.onStepEvent("清体力", "started", null)
        assertEquals(StepStatus.RUNNING, statuses(steps)[StepId.POWER])
        assertEquals(StepId.POWER, steps.progress()!!.step.step)
        assertEquals(1, steps.progress()!!.number)
        assertEquals(3, steps.progress()!!.total)
        steps = steps.onStepEvent("清体力", "succeeded", "已完成 6 次挑战，剩余开拓力 3/300")
            .onStepEvent("日常领奖", "started", null)
            .onStepEvent("日常领奖", "failed", "邮件失败：未确认邮箱附件状态")
            .onStepEvent("每日实训", "started", null)
        assertEquals(3, steps.progress()!!.number)
        steps = steps.onStepEvent("每日实训", "succeeded", "每日实训活跃度 500/500")

        assertEquals(
            listOf(
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
            echo.onStepEvent("历战余响", "failed", "原因").first(),
        )
        assertEquals(StepStatus.FAILED, echo.onStepEvent("清体力", "failed", null)[1].status)
    }

    @Test
    fun finishingMarksOnlyTheRunningStep() {
        val running = plannedSteps(TaskId.ROUTINE, TaskConfig(), monday)
            .onStepEvent("清体力", "started", null).onStepEvent("清体力", "succeeded", null)
            .onStepEvent("日常领奖", "started", null)

        assertEquals(
            listOf(StepStatus.DISABLED, StepStatus.DONE, StepStatus.STOPPED, StepStatus.PENDING),
            running.finished("stopped").map { it.status },
        )
        val failed = running.finished("device_asleep")
        assertEquals(StepResult(StepId.REWARDS, "日常领奖", StepStatus.FAILED), failed[2])
        assertEquals(StepStatus.PENDING, failed[3].status)
    }

    @Test
    fun progressReplacesThePlanWithTheValidItems() {
        val progress = parseProgress(
            """{"power_plan": [["拟造花萼（金）", "回忆之蕾", 1], ["拟造花萼（金）", "回忆之蕾", 0],
                ["未知副本", "x", 2], ["侵蚀隧洞", "无", 1], ["凝滞虚影", "空海之形", 2.5], ["侵蚀隧洞", "睿治之径"],
                "坏数据", ["历战余响", "寒潭指月", 3]],
               "last_run_timestamp": 1762900000.25, "echo_of_war_timestamp": 0}"""
        )!!

        assertEquals(
            listOf(PlanItem(InstanceType.GOLDEN_CALYX, "回忆之蕾", 1), PlanItem(InstanceType.ECHO, "寒潭指月", 3)),
            progress.plan,
        )
        assertEquals(1762900000250L, progress.lastDailyDone)
        assertNull(progress.lastEchoDone)
    }

    @Test
    fun progressWithoutAPlanKeepsTheCurrentOne() {
        assertEquals(emptyList<PlanItem>(), parseProgress("""{"power_plan": []}""")!!.plan)
        assertNull(parseProgress("""{"power_plan": null, "last_run_timestamp": 5}""")!!.plan)
        assertNull(parseProgress("不是 JSON"))
        assertNull(parseProgress("[]"))
    }
}
