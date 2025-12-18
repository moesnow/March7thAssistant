# coding:utf-8
"""任务定义模块"""

# 可用的任务列表（任务ID -> 任务名称）
AVAILABLE_TASKS = {
    "main": "完整运行",
    "daily": "每日实训",
    "power": "清体力",
    "currencywars": "货币战争",
    "currencywarsloop": "货币战争循环",
    "currencywarstemp": "货币战争中途接管",
    "fight": "锄大地",
    "universe": "模拟宇宙",
    "forgottenhall": "混沌回忆",
    "purefiction": "虚构叙事",
    "apocalyptic": "末日幻影",
    "redemption": "兑换码",
    "universe_gui": "模拟宇宙原生界面",
    "fight_gui": "锄大地原生界面",
    "universe_update": "模拟宇宙更新",
    "fight_update": "锄大地更新",
    "mobileui_update": "触屏模式更新",
    "game": "启动游戏",
    "notify": "测试消息推送",
}

# 任务名称本地化映射（兼容旧名称）
TASK_NAMES = AVAILABLE_TASKS
