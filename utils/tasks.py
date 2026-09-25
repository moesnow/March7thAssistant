# coding:utf-8
"""任务定义模块。

**这里的名称是中文原文（msgid），不是译文。** 模块级常量在 import 期求值，
若直接存 `tr()` 的结果，就会被冻结在启动时的语言：切换语言后（界面会热重载）
这些文案仍显示旧语言，且会被写进 config.yaml 变成用户数据。显示时请自行调用 `tr()`：

    from module.localization import tr
    label = tr(AVAILABLE_TASKS[task_id])

详见 I18N.md「模块级常量不要存译文」。
"""

# 可用的任务列表（任务ID -> 名称 msgid）
AVAILABLE_TASKS = {
    "main": "完整运行",
    "routine": "日常",
    "daily": "每日实训",
    "power": "清体力",
    "game_update": "更新游戏",
    "game_pre_download": "预下载游戏",
    "app_update": "更新三月七小助手",
    "currencywars": "货币战争",
    "divergent": "差分宇宙",
    "fight": "锄大地",
    "universe": "模拟宇宙",
    "forgottenhall": "混沌回忆",
    "purefiction": "虚构叙事",
    "apocalyptic": "末日幻影",
    "currencywarsloop": "货币战争循环",
    "currencywarstemp": "货币战争中途接管",
    "divergentloop": "差分宇宙循环",
    "divergenttemp": "差分宇宙中途接管",
    "universe_gui": "模拟宇宙原生界面",
    "fight_gui": "锄大地原生界面",
    "universe_update": "模拟宇宙更新",
    "fight_update": "锄大地更新",
    "mobileui_update": "触屏模式更新",
    "game": "启动游戏",
    "notify": "测试消息推送",
    "redemption": "兑换码",
    "screen_test": "界面可切换性测试",
}

# 任务名称映射（兼容旧名称调用方）
TASK_NAMES = AVAILABLE_TASKS

# 支持「暂停/继续」的内置任务白名单。
# 仅针对内置任务 ID；workflow（用户自定义流程）经 workflow 启动路径单独启用
# （运行于 main.py 进程内、走同一套动作卡点），外部/自定义程序与更新、
# 启动器、原生界面类子任务不支持暂停。判定逻辑见 LogInterface._resolvePauseSupport。
PAUSABLE_TASKS = frozenset({
    "main",
    "routine",
    "daily",
    "power",
    "currencywars",
    "currencywarsloop",
    "currencywarstemp",
    "divergent",
    "divergentloop",
    "divergenttemp",
    "fight",
    "universe",
    "forgottenhall",
    "purefiction",
    "apocalyptic",
    "redemption",
    "screen_test",
})


def task_display_names() -> dict:
    """任务ID -> 当前语言显示名。

    供 `--list` 等界面输出使用（属界面文案，随 ui_language）；
    日志与配置仍按约定使用 AVAILABLE_TASKS 里的中文原文。
    """
    from module.localization import tr
    return {task_id: tr(name) for task_id, name in AVAILABLE_TASKS.items()}
