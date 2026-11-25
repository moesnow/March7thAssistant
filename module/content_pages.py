"""Desktop content order. Names are source-language msgids, translated at display time."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Group:
    id: str
    title: str
    collapsed: bool = False


@dataclass(frozen=True)
class Page:
    id: str
    name: str
    kind: str
    icon: str
    task_group: str
    groups: tuple[Group, ...]


PAGES = (
    Page("run_mode", "运行方式", "setting", "FIF.CONNECT", "", (
        Group("header", "运行方式"),
        Group("local", "本地客户端"),
        Group("cloud", "云·星穹铁道"),
        Group("adb", "安卓设备"),
    )),
    Page("game", "游戏与启动", "setting", "FIF.GAME", "", (
        Group("launch", "启动游戏"),
        Group("optimization", "游戏优化"),
        Group("keys", "游戏内按键"),
    )),
    Page("after_run", "任务结束后", "setting", "FIF.POWER_BUTTON", "", (
        Group("actions", "完成后操作"),
    )),
    Page("notify", "消息推送", "setting", "FIF.RINGER", "", (
        Group("header", "消息推送"),
        Group("channels", "已添加的渠道"),
        Group("content", "推送内容"),
    )),
    Page("hotkeys", "快捷键", "setting", "UiIcon.KEYBOARD", "", (
        Group("keys", "全局热键"),
    )),
    Page("appearance", "外观与窗口", "setting", "FIF.PALETTE", "", (
        Group("appearance", "外观"),
        Group("window", "窗口"),
    )),
    Page("update", "更新", "setting", "FIF.UPDATE", "", (
        Group("source", "更新源"),
    )),
    Page("data", "数据与备份", "setting", "FIF.FOLDER", "", (
        Group("folder", "数据文件夹"),
        Group("backup", "备份与恢复"),
        Group("diagnostics", "导出排查包"),
    )),
    Page("advanced", "高级", "setting", "FIF.SETTING", "", (
        Group("general", "高级"),
        Group("permissions", "启动与权限"),
        Group("privacy", "隐私"),
    )),
    Page("about", "关于", "setting", "FIF.INFO", "", (
        Group("header", "关于"),
        Group("project", "社区与工具"),
    )),
    Page("power", "清体力", "task", "UiIcon.BATTERY_CHARGE", "每天", (
        Group("header", "加入完整运行"),
        Group("instances", "刷什么"),
        Group("refill", "开拓力不够时"),
        Group("battle", "战斗与高级", True),
    )),
    Page("daily", "每日实训", "task", "UiIcon.CLIPBOARD_TASK", "每天", (
        Group("header", "加入完整运行"),
        Group("training", "实训项目"),
    )),
    Page("activity", "活动", "task", "UiIcon.SPARKLE", "每天", (
        Group("header", "加入完整运行"),
        Group("events", "活动项目"),
    )),
    Page("reward", "领取奖励", "task", "UiIcon.GIFT", "每天", (
        Group("header", "加入完整运行"),
        Group("items", "领取项目"),
    )),
    Page("fight", "锄大地", "task", "UiIcon.MAP", "每天", (
        Group("header", "加入完整运行"),
        Group("maps", "地图与队伍"),
        Group("rewards", "特殊物品领取"),
        Group("advanced", "战斗与高级", True),
    )),
    Page("echo", "历战余响", "task", "UiIcon.CROWN", "每周", (
        Group("header", "加入完整运行"),
        Group("schedule", "执行时间"),
    )),
    Page("currencywars", "货币战争", "task", "UiIcon.COIN_STACK", "每周", (
        Group("header", "加入完整运行"),
        Group("strategy", "博弈策略"),
        Group("advanced", "战斗与高级", True),
    )),
    Page("universe", "差分宇宙", "task", "UiIcon.PLANET", "每周", (
        Group("header", "加入完整运行"),
        Group("points", "积分奖励"),
        Group("external", "模拟宇宙（外部工具，停止维护）", True),
    )),
    Page("challenge", "逐光捡金", "task", "UiIcon.TROPHY", "每周", (
        Group("forgottenhall", "混沌回忆"),
        Group("purefiction", "虚构叙事"),
        Group("apocalyptic", "末日幻影"),
    )),
    Page("assets", "资产管理", "task", "UiIcon.BOX", "按月和其他", (
        Group("header", "加入完整运行"),
        Group("monthly", "每月兑换"),
        Group("materials", "资产处理"),
        Group("relics", "遗器清理", True),
    )),
    Page("run", "运行", "page", "FIF.PLAY", "", (
        Group("schedule", "定时计划"),
    )),
)

PAGE_BY_ID = {page.id: page for page in PAGES}
GROUP_BY_ID = {(page.id, group.id): group for page in PAGES for group in page.groups}
