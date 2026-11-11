package org.march7th.assistant

/** 与 Windows 触屏入口一一对应：日常、每日实训、清体力。 */
enum class TaskId { ROUTINE, DAILY, POWER }

/**
 * typeName 对应共享配置的副本类型，声明顺序与 Windows 的副本清单相同。
 * cost 是每次挑战的开拓力，maxBatch 是一次连续挑战的上限，都取自 tasks/power/policy.py。
 */
enum class InstanceType(val typeName: String, val cost: Int, val maxBatch: Int) {
    GOLDEN_CALYX("拟造花萼（金）", 10, 24),
    CRIMSON_CALYX("拟造花萼（赤）", 10, 24),
    STAGNANT_SHADOW("凝滞虚影", 30, 8),
    CAVERN("侵蚀隧洞", 40, 6),
    ORNAMENT("饰品提取", 40, 6),
    ECHO("历战余响", 30, 3);

    /** 能用来估算的消耗。历战余响超出每周奖励后不耗开拓力，饰品提取可以用沉浸器代付，两者不估算。 */
    val fixedCost: Int?
        get() = cost.takeUnless { this == ORNAMENT || this == ECHO }

    companion object {
        /** 默认副本可选的类型。历战余响只能放进体力计划或由「启用历战余响」处理。 */
        val defaults: List<InstanceType> = entries - ECHO

        fun of(typeName: String?): InstanceType? = entries.firstOrNull { it.typeName == typeName }
    }
}

/** 界面上显示的步骤。pythonName 是 tasks.touch.rewards.routine 里的步骤名。 */
enum class StepId(val pythonName: String) {
    ECHO("历战余响"),
    POWER("清体力"),
    REWARDS("日常领奖"),
    DAILY("每日实训");

    companion object {
        fun of(name: String): StepId? = entries.firstOrNull { it.pythonName == name }
    }
}

enum class StepStatus { PENDING, RUNNING, DONE, FAILED, STOPPED, DISABLED }

/**
 * 本轮的一个步骤。step 为空的是 Python 报来的其他步骤，name 是它的原名。
 * detail 是这一步的摘要或失败原因。startDay 不为空时，历战余响要到这一天（周一为 1）才开始打。
 */
data class StepResult(
    val step: StepId?,
    val name: String,
    val status: StepStatus,
    val detail: String? = null,
    val startDay: Int? = null,
)

/** 体力计划的一项，name 是副本在 instance_names.json 里的键。 */
data class PlanItem(val type: InstanceType, val name: String, val count: Int)

/** key 是 character_names.json 里的角色键，owner 是好友昵称的一部分，空串表示不限好友。 */
data class Support(val key: String, val owner: String = "")

/** 给某个副本单独指定队伍。Python 只按副本名称匹配。 */
data class TeamRule(val instance: String, val team: Int)

/** 可选的副本或角色。id 写入配置，title 和 detail 用于显示。 */
class CatalogItem(val id: String, val title: String, val detail: String? = null)

/** 随 APK 打包的游戏数据里可选的副本和支援角色。 */
class Catalog(val instances: Map<InstanceType, List<CatalogItem>>, val characters: List<CatalogItem>)

/** 三个任务共用的设置。字段与 Python 配置键的对照见 toSettings 和界面契约。 */
data class TaskConfig(
    val panelOff: Boolean = false,
    val muteGame: Boolean = true,
    val powerEnable: Boolean = true,
    val powerPlan: List<PlanItem> = emptyList(),
    val planKeep: Boolean = false,
    val planContinue: Boolean = true,
    val instanceType: InstanceType = InstanceType.GOLDEN_CALYX,
    /** 每种类型各记一个副本，换类型时回到上次的选择。没有记录的类型取清单第一项。 */
    val instanceNames: Map<InstanceType, String> = DEFAULT_INSTANCE_NAMES,
    val reserve: Boolean = false,
    val fuel: Boolean = false,
    val teamEnable: Boolean = false,
    val teamNumber: Int = 6,
    val teamRules: List<TeamRule> = emptyList(),
    val borrowEnable: Boolean = false,
    val borrowAlways: Boolean = false,
    val supports: List<Support> = emptyList(),
    val borrowScrollTimes: Int = MAX_SCROLL_TIMES,
    val echoEnable: Boolean = false,
    val echoStartDay: Int = 1,
    val teleportFirst: Boolean = false,
    val relicCleanup: Boolean = false,
    val challengeCounts: Map<InstanceType, Int> = DEFAULT_CHALLENGE_COUNTS,
    val autoBattle: Boolean = true,
    val rewardEnable: Boolean = true,
    val dispatch: Boolean = true,
    val mail: Boolean = true,
    val assist: Boolean = true,
    val quest: Boolean = true,
    val srpass: Boolean = true,
    val message: Boolean = false,
    val dailyEnable: Boolean = true,
    val synthesis: Boolean = true,
) {
    /** 是否都在 Windows 设置页允许的范围内。 */
    val isValid: Boolean
        get() = powerPlan.size <= MAX_PLAN_ITEMS &&
            powerPlan.all { it.count in 1..MAX_PLAN_COUNT && it.name.isNotBlank() } &&
            instanceType != InstanceType.ECHO &&
            instanceNames.values.all { it.isNotBlank() } &&
            teamNumber in 1..MAX_TEAM &&
            teamRules.all { it.team in 1..MAX_TEAM && it.instance.isNotBlank() } &&
            teamRules.distinctBy { it.instance }.size == teamRules.size &&
            supports.size <= MAX_SUPPORTS &&
            supports.distinctBy { it.key }.size == supports.size &&
            borrowScrollTimes in 1..MAX_SCROLL_TIMES &&
            echoStartDay in 1..7 &&
            challengeCounts.all { (type, count) -> count in 1..type.maxBatch }

    /** 实际使用的副本名称：已存名称不在清单里时取清单第一项。 */
    fun instanceName(type: InstanceType, catalog: Catalog): String {
        val stored = instanceNames[type]
        val items = catalog.instances[type].orEmpty()
        return when {
            items.any { it.id == stored } -> stored!!
            items.isNotEmpty() -> items.first().id
            else -> stored.orEmpty()
        }
    }

    fun challengeCount(type: InstanceType): Int = challengeCounts[type] ?: type.maxBatch

    companion object {
        const val MAX_PLAN_ITEMS = 8
        const val MAX_PLAN_COUNT = 999
        const val MAX_SUPPORTS = 6
        const val MAX_TEAM = 12
        const val MAX_SCROLL_TIMES = 10

        // 取自 config.example.yaml。模板里凝滞虚影是「无」，没有记录时取清单第一项。
        val DEFAULT_INSTANCE_NAMES = mapOf(
            InstanceType.GOLDEN_CALYX to "回忆之蕾",
            InstanceType.CRIMSON_CALYX to "收容舱段",
            InstanceType.CAVERN to "睿治之径",
            InstanceType.ORNAMENT to "永恒笑剧",
            InstanceType.ECHO to "毁灭的开端",
        )
        val DEFAULT_CHALLENGE_COUNTS = InstanceType.entries.associateWith { it.maxBatch }
    }
}

/** 写入 Python 配置的设置，键与 android_task.SETTING_KEYS 一一对应。 */
fun TaskConfig.toSettings(catalog: Catalog): Map<String, Any> = linkedMapOf(
    "power_enable" to powerEnable,
    "power_plan" to powerPlan.map { listOf(it.type.typeName, it.name, it.count) },
    "power_plan_keep" to planKeep,
    "power_plan_continue" to planContinue,
    "instance_type" to instanceType.typeName,
    "instance_names" to InstanceType.entries.associate { it.typeName to instanceName(it, catalog) },
    "use_reserved_trailblaze_power" to reserve,
    "use_fuel" to fuel,
    "instance_team_enable" to teamEnable,
    "instance_team_number" to teamNumber.toString(),
    "instance_teams" to teamRules.map { mapOf("instance_name" to it.instance, "team_number" to it.team) },
    // 没选角色时不进支援列表，也不为支援实训多查一次任务卡。
    "borrow_enable" to (borrowEnable && supports.isNotEmpty()),
    "borrow_character_enable" to borrowAlways,
    "borrow_friends" to supports.map { listOf(it.key, it.owner) },
    "borrow_scroll_times" to borrowScrollTimes,
    "echo_of_war_enable" to echoEnable,
    "echo_of_war_start_day_of_week" to echoStartDay,
    "tp_before_instance" to teleportFirst,
    "relic_bag_cleanup_enable" to relicCleanup,
    "instance_names_challenge_count" to InstanceType.entries.associate { it.typeName to challengeCount(it) },
    "auto_battle_detect_enable" to autoBattle,
    "reward_enable" to rewardEnable,
    "reward_dispatch_enable" to dispatch,
    "reward_mail_enable" to mail,
    "reward_assist_enable" to assist,
    "reward_quest_enable" to quest,
    "reward_srpass_enable" to srpass,
    "reward_message_enable" to message,
    "daily_enable" to dailyEnable,
    "daily_material_enable" to synthesis,
)

/** 保存到偏好的写法。枚举存名称，读取见 [decodeTaskConfig]。 */
fun TaskConfig.encode(): String = Json.encode(
    linkedMapOf(
        "panelOff" to panelOff,
        "muteGame" to muteGame,
        "powerEnable" to powerEnable,
        "powerPlan" to powerPlan.map { listOf(it.type.name, it.name, it.count) },
        "planKeep" to planKeep,
        "planContinue" to planContinue,
        "instanceType" to instanceType.name,
        "instanceNames" to instanceNames.mapKeys { it.key.name },
        "reserve" to reserve,
        "fuel" to fuel,
        "teamEnable" to teamEnable,
        "teamNumber" to teamNumber,
        "teamRules" to teamRules.map { listOf(it.instance, it.team) },
        "borrowEnable" to borrowEnable,
        "borrowAlways" to borrowAlways,
        "supports" to supports.map { listOf(it.key, it.owner) },
        "borrowScrollTimes" to borrowScrollTimes,
        "echoEnable" to echoEnable,
        "echoStartDay" to echoStartDay,
        "teleportFirst" to teleportFirst,
        "relicCleanup" to relicCleanup,
        "challengeCounts" to challengeCounts.mapKeys { it.key.name },
        "autoBattle" to autoBattle,
        "rewardEnable" to rewardEnable,
        "dispatch" to dispatch,
        "mail" to mail,
        "assist" to assist,
        "quest" to quest,
        "srpass" to srpass,
        "message" to message,
        "dailyEnable" to dailyEnable,
        "synthesis" to synthesis,
    )
)

/** 读不出或超出范围的项用默认值，整份读不出时返回默认设置。 */
fun decodeTaskConfig(text: String?): TaskConfig {
    val root = text?.let { runCatching { Json.decode(it) }.getOrNull() } as? Map<*, *> ?: return TaskConfig()
    val default = TaskConfig()
    fun flag(key: String, fallback: Boolean) = root[key] as? Boolean ?: fallback
    fun number(key: String, range: IntRange, fallback: Int) =
        (root[key] as? Long)?.takeIf { it >= range.first && it <= range.last }?.toInt() ?: fallback
    fun type(name: Any?) = InstanceType.entries.firstOrNull { it.name == name }
    fun rows(key: String) = (root[key] as? List<*>).orEmpty().mapNotNull { it as? List<*> }

    val plan = rows("powerPlan").mapNotNull { row ->
        val type = type(row.getOrNull(0))
        val name = row.getOrNull(1) as? String
        val count = (row.getOrNull(2) as? Long)?.takeIf { it in 1L..TaskConfig.MAX_PLAN_COUNT }
        if (row.size == 3 && type != null && !name.isNullOrBlank() && count != null) PlanItem(type, name, count.toInt()) else null
    }.take(TaskConfig.MAX_PLAN_ITEMS)
    val names = (root["instanceNames"] as? Map<*, *>).orEmpty().mapNotNull { (key, value) ->
        val type = type(key)
        if (type != null && value is String && value.isNotBlank()) type to value else null
    }.toMap()
    val counts = (root["challengeCounts"] as? Map<*, *>).orEmpty().mapNotNull { (key, value) ->
        val type = type(key)
        if (type != null && value is Long && value in 1L..type.maxBatch) type to value.toInt() else null
    }.toMap()
    val rules = rows("teamRules").mapNotNull { row ->
        val instance = row.getOrNull(0) as? String
        val team = (row.getOrNull(1) as? Long)?.takeIf { it in 1L..TaskConfig.MAX_TEAM }
        if (row.size == 2 && !instance.isNullOrBlank() && team != null) TeamRule(instance, team.toInt()) else null
    }.distinctBy { it.instance }
    val supports = rows("supports").mapNotNull { row ->
        val key = row.getOrNull(0) as? String
        val owner = row.getOrNull(1) as? String
        if (row.size == 2 && !key.isNullOrBlank() && owner != null) Support(key, owner) else null
    }.distinctBy { it.key }.take(TaskConfig.MAX_SUPPORTS)

    return TaskConfig(
        panelOff = flag("panelOff", default.panelOff),
        muteGame = flag("muteGame", default.muteGame),
        powerEnable = flag("powerEnable", default.powerEnable),
        powerPlan = plan,
        planKeep = flag("planKeep", default.planKeep),
        planContinue = flag("planContinue", default.planContinue),
        instanceType = type(root["instanceType"])?.takeIf { it != InstanceType.ECHO } ?: default.instanceType,
        instanceNames = default.instanceNames + names,
        reserve = flag("reserve", default.reserve),
        fuel = flag("fuel", default.fuel),
        teamEnable = flag("teamEnable", default.teamEnable),
        teamNumber = number("teamNumber", 1..TaskConfig.MAX_TEAM, default.teamNumber),
        teamRules = rules,
        borrowEnable = flag("borrowEnable", default.borrowEnable),
        borrowAlways = flag("borrowAlways", default.borrowAlways),
        supports = supports,
        borrowScrollTimes = number("borrowScrollTimes", 1..TaskConfig.MAX_SCROLL_TIMES, default.borrowScrollTimes),
        echoEnable = flag("echoEnable", default.echoEnable),
        echoStartDay = number("echoStartDay", 1..7, default.echoStartDay),
        teleportFirst = flag("teleportFirst", default.teleportFirst),
        relicCleanup = flag("relicCleanup", default.relicCleanup),
        challengeCounts = default.challengeCounts + counts,
        autoBattle = flag("autoBattle", default.autoBattle),
        rewardEnable = flag("rewardEnable", default.rewardEnable),
        dispatch = flag("dispatch", default.dispatch),
        mail = flag("mail", default.mail),
        assist = flag("assist", default.assist),
        quest = flag("quest", default.quest),
        srpass = flag("srpass", default.srpass),
        message = flag("message", default.message),
        dailyEnable = flag("dailyEnable", default.dailyEnable),
        synthesis = flag("synthesis", default.synthesis),
    )
}
