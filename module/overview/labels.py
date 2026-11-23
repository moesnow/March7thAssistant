"""运行记录及定时完成后操作的界面用词。"""
from module.localization import tr

TRIGGERS = {
    "manual": "手动", "scheduled": "定时", "gui": "图形界面", "cli": "命令行", "entry": "命令行",
    "docker": "容器", "non_interactive": "非交互运行", "desktop_twin": "桌面分身",
}
RESULTS = {"success": "成功", "failed": "失败", "partial": "部分失败", "blocked": "未执行", "running": "运行中",
           "aborted": "异常结束", "interrupted": "已中断", "stopped": "已停止", "skipped": "已跳过"}
POST_ACTIONS = {"None": "无操作", "Shutdown": "关机", "Sleep": "睡眠", "Hibernate": "休眠", "Restart": "重启",
                "Logoff": "注销", "TurnOffDisplay": "关闭显示器"}


def trigger_label(key):
    return tr(TRIGGERS[key]) if key in TRIGGERS else tr("未知")


def result_label(key):
    return tr(RESULTS[key]) if key in RESULTS else tr("未知")


def post_action_label(key):
    return tr(POST_ACTIONS[key]) if key in POST_ACTIONS else str(key)
