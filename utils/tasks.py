# coding:utf-8
from module.localization import tr, load_language

load_language()

"""任务定义模块"""

# 可用的任务列表（任务ID -> 任务名称）
AVAILABLE_TASKS = {
    "main": tr("完整运行"),
    "daily": tr("每日实训"),
    "power": tr("清体力"),
    "game_update": tr("更新游戏"),
    "game_pre_download": tr("预下载游戏"),
    "currencywars": tr("货币战争"),
    "fight": tr("锄大地"),
    "universe": tr("模拟宇宙"),
    "forgottenhall": tr("混沌回忆"),
    "purefiction": tr("虚构叙事"),
    "apocalyptic": tr("末日幻影"),
    "currencywarsloop": tr("货币战争循环"),
    "currencywarstemp": tr("货币战争中途接管"),
    "universe_gui": tr("模拟宇宙原生界面"),
    "fight_gui": tr("锄大地原生界面"),
    "universe_update": tr("模拟宇宙更新"),
    "fight_update": tr("锄大地更新"),
    "mobileui_update": tr("触屏模式更新"),
    "game": tr("启动游戏"),
    "notify": tr("测试消息推送"),
    "redemption": tr("兑换码"),
}

# 任务名称本地化映射（兼容旧名称）
TASK_NAMES = AVAILABLE_TASKS
