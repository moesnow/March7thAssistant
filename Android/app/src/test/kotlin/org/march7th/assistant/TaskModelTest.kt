package org.march7th.assistant

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TaskModelTest {
    private val catalog = Catalog(
        mapOf(
            InstanceType.GOLDEN_CALYX to items("回忆之蕾", "以太之蕾", "藏珍之蕾"),
            InstanceType.CRIMSON_CALYX to items("收容舱段", "支援舱段"),
            InstanceType.STAGNANT_SHADOW to items("空海之形", "巽风之形"),
            InstanceType.CAVERN to items("睿治之径", "霜风之径"),
            InstanceType.ORNAMENT to items("永恒笑剧", "蠹役饥肠"),
            InstanceType.ECHO to items("毁灭的开端", "寒潭指月"),
        ),
        listOf(CatalogItem("March7th", "三月七"), CatalogItem("Qingque", "青雀")),
    )

    private fun items(vararg ids: String) = ids.map { CatalogItem(it, it, "说明") }

    private val defaultSettings = mapOf(
        "power_enable" to true,
        "power_plan" to emptyList<Any>(),
        "power_plan_keep" to false,
        "power_plan_continue" to true,
        "instance_type" to "拟造花萼（金）",
        "instance_names" to mapOf(
            "拟造花萼（金）" to "回忆之蕾", "拟造花萼（赤）" to "收容舱段", "凝滞虚影" to "空海之形",
            "侵蚀隧洞" to "睿治之径", "饰品提取" to "永恒笑剧", "历战余响" to "毁灭的开端",
        ),
        "use_reserved_trailblaze_power" to false,
        "use_fuel" to false,
        "instance_team_enable" to false,
        "instance_team_number" to "6",
        "instance_teams" to emptyList<Any>(),
        "borrow_enable" to false,
        "borrow_character_enable" to false,
        "borrow_friends" to emptyList<Any>(),
        "borrow_scroll_times" to 10,
        "echo_of_war_enable" to false,
        "echo_of_war_start_day_of_week" to 1,
        "tp_before_instance" to false,
        "relic_bag_cleanup_enable" to false,
        "instance_names_challenge_count" to mapOf(
            "拟造花萼（金）" to 24, "拟造花萼（赤）" to 24, "凝滞虚影" to 8, "侵蚀隧洞" to 6, "饰品提取" to 6, "历战余响" to 3,
        ),
        "auto_battle_detect_enable" to true,
        "reward_enable" to true,
        "reward_dispatch_enable" to true,
        "reward_mail_enable" to true,
        "reward_assist_enable" to true,
        "reward_quest_enable" to true,
        "reward_srpass_enable" to true,
        "reward_message_enable" to false,
        "daily_enable" to true,
        "daily_material_enable" to true,
    )

    private val custom = TaskConfig(
        panelOff = true,
        muteGame = false,
        powerEnable = false,
        powerPlan = listOf(
            PlanItem(InstanceType.CRIMSON_CALYX, "支援舱段", 6),
            PlanItem(InstanceType.ECHO, "寒潭指月", 999),
        ),
        planKeep = true,
        planContinue = false,
        instanceType = InstanceType.CAVERN,
        instanceNames = TaskConfig.DEFAULT_INSTANCE_NAMES + mapOf(
            InstanceType.CAVERN to "霜风之径", InstanceType.STAGNANT_SHADOW to "巽风之形", InstanceType.ORNAMENT to "已下架",
        ),
        reserve = true,
        fuel = true,
        teamEnable = true,
        teamNumber = 12,
        teamRules = listOf(TeamRule("霜风之径", 3)),
        borrowEnable = true,
        borrowAlways = true,
        supports = listOf(Support("Qingque", "用牌"), Support("March7th")),
        borrowScrollTimes = 1,
        echoEnable = true,
        echoStartDay = 7,
        teleportFirst = true,
        relicCleanup = true,
        challengeCounts = TaskConfig.DEFAULT_CHALLENGE_COUNTS + mapOf(InstanceType.GOLDEN_CALYX to 1, InstanceType.ECHO to 2),
        autoBattle = false,
        rewardEnable = false,
        dispatch = false,
        mail = false,
        assist = false,
        quest = false,
        srpass = false,
        message = true,
        dailyEnable = false,
        synthesis = false,
    )

    @Test
    fun defaultSettingsMatchTheTemplateDefaults() {
        val settings = TaskConfig().toSettings(catalog)

        assertEquals(defaultSettings, settings)
        assertEquals(30, settings.size)
        assertEquals("6", settings["instance_team_number"])
    }

    @Test
    fun customSettingsUseThePythonShapes() {
        val expected = mapOf(
            "power_enable" to false,
            "power_plan" to listOf(listOf("拟造花萼（赤）", "支援舱段", 6), listOf("历战余响", "寒潭指月", 999)),
            "power_plan_keep" to true,
            "power_plan_continue" to false,
            "instance_type" to "侵蚀隧洞",
            // 不在清单里的名称回落到清单第一项，任何一项都不会是「无」。
            "instance_names" to mapOf(
                "拟造花萼（金）" to "回忆之蕾", "拟造花萼（赤）" to "收容舱段", "凝滞虚影" to "巽风之形",
                "侵蚀隧洞" to "霜风之径", "饰品提取" to "永恒笑剧", "历战余响" to "毁灭的开端",
            ),
            "use_reserved_trailblaze_power" to true,
            "use_fuel" to true,
            "instance_team_enable" to true,
            "instance_team_number" to "12",
            "instance_teams" to listOf(mapOf("instance_name" to "霜风之径", "team_number" to 3)),
            "borrow_enable" to true,
            "borrow_character_enable" to true,
            "borrow_friends" to listOf(listOf("Qingque", "用牌"), listOf("March7th", "")),
            "borrow_scroll_times" to 1,
            "echo_of_war_enable" to true,
            "echo_of_war_start_day_of_week" to 7,
            "tp_before_instance" to true,
            "relic_bag_cleanup_enable" to true,
            "instance_names_challenge_count" to mapOf(
                "拟造花萼（金）" to 1, "拟造花萼（赤）" to 24, "凝滞虚影" to 8, "侵蚀隧洞" to 6, "饰品提取" to 6, "历战余响" to 2,
            ),
            "auto_battle_detect_enable" to false,
            "reward_enable" to false,
            "reward_dispatch_enable" to false,
            "reward_mail_enable" to false,
            "reward_assist_enable" to false,
            "reward_quest_enable" to false,
            "reward_srpass_enable" to false,
            "reward_message_enable" to true,
            "daily_enable" to false,
            "daily_material_enable" to false,
        )

        assertEquals(expected, custom.toSettings(catalog))
        assertEquals(defaultSettings.keys, expected.keys)
    }

    @Test
    fun borrowingNeedsAtLeastOneCharacter() {
        val settings = TaskConfig(borrowEnable = true, supports = emptyList()).toSettings(catalog)

        assertEquals(false, settings["borrow_enable"])
        assertEquals(emptyList<Any>(), settings["borrow_friends"])
    }

    @Test
    fun settingsSurviveAPreferenceRoundTrip() {
        assertEquals(TaskConfig(), decodeTaskConfig(TaskConfig().encode()))
        assertEquals(custom, decodeTaskConfig(custom.encode()))
        // 写进 JSON 的正好是 Python 能读的值。
        assertEquals(
            Json.decode(Json.encode(custom.toSettings(catalog))),
            Json.decode(Json.encode(decodeTaskConfig(custom.encode()).toSettings(catalog))),
        )
    }

    @Test
    fun missingOrBrokenPreferencesFallBackToDefaults() {
        assertEquals(TaskConfig(), decodeTaskConfig(null))
        assertEquals(TaskConfig(), decodeTaskConfig("{\"tasks\": \"POWER,DAILY\""))
        assertEquals(TaskConfig(), decodeTaskConfig("[1, 2]"))
        val partial = decodeTaskConfig(
            """{"fuel": true, "teamNumber": 13, "echoStartDay": 0, "instanceType": "ECHO", "borrowScrollTimes": "5",
               "powerPlan": [["ECHO", "寒潭指月", 0], ["CAVERN", "睿治之径", 2], ["UNKNOWN", "x", 1], ["CAVERN", "", 1]],
               "challengeCounts": {"CAVERN": 7, "ECHO": 2}, "supports": [["March7th", ""], ["March7th", "重复"]]}"""
        )

        assertEquals(TaskConfig().copy(
            fuel = true,
            powerPlan = listOf(PlanItem(InstanceType.CAVERN, "睿治之径", 2)),
            challengeCounts = TaskConfig.DEFAULT_CHALLENGE_COUNTS + (InstanceType.ECHO to 2),
            supports = listOf(Support("March7th")),
        ), partial)
    }

    @Test
    fun validationFollowsTheWindowsRanges() {
        assertTrue(TaskConfig().isValid)
        assertTrue(custom.isValid)
        val plan = List(TaskConfig.MAX_PLAN_ITEMS) { PlanItem(InstanceType.GOLDEN_CALYX, "回忆之蕾", 1) }
        assertTrue(TaskConfig(powerPlan = plan).isValid)
        val invalid = listOf(
            TaskConfig(powerPlan = plan + plan.first()),
            TaskConfig(powerPlan = listOf(PlanItem(InstanceType.GOLDEN_CALYX, "回忆之蕾", 0))),
            TaskConfig(powerPlan = listOf(PlanItem(InstanceType.GOLDEN_CALYX, "回忆之蕾", 1000))),
            TaskConfig(instanceType = InstanceType.ECHO),
            TaskConfig(teamNumber = 0),
            TaskConfig(teamNumber = 13),
            TaskConfig(teamRules = listOf(TeamRule("回忆之蕾", 13))),
            TaskConfig(teamRules = listOf(TeamRule("回忆之蕾", 1), TeamRule("回忆之蕾", 2))),
            TaskConfig(supports = List(7) { Support("角色$it") }),
            TaskConfig(supports = listOf(Support("March7th"), Support("March7th", "好友"))),
            TaskConfig(borrowScrollTimes = 0),
            TaskConfig(borrowScrollTimes = 11),
            TaskConfig(echoStartDay = 0),
            TaskConfig(echoStartDay = 8),
            TaskConfig(challengeCounts = TaskConfig.DEFAULT_CHALLENGE_COUNTS + (InstanceType.STAGNANT_SHADOW to 9)),
            TaskConfig(challengeCounts = TaskConfig.DEFAULT_CHALLENGE_COUNTS + (InstanceType.ECHO to 0)),
        )
        for (config in invalid) assertFalse(config.toString(), config.isValid)
    }

    @Test
    fun jsonKeepsTextAndNumbersIntact() {
        val value = mapOf(
            "text" to "引号\"、反斜杠\\、换行\n、制表\t、控制\u0001",
            "numbers" to listOf(0L, -3L, 1762900000L, 1762900000.5, 1.0E-4),
            "flags" to listOf(true, false, null),
            "nested" to mapOf("empty" to emptyMap<String, Any>(), "list" to emptyList<Any>()),
        )

        assertEquals(value, Json.decode(Json.encode(value)))
        assertEquals(mapOf("a" to "é/x"), Json.decode(""" { "a" : "é\/x" } """))
        for (broken in listOf("", "{", "[1,]", "{\"a\" 1}", "tru", "1 2", "\"x")) {
            assertTrue(broken, runCatching { Json.decode(broken) }.isFailure)
        }
    }
}
