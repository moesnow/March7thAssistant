"""账号状态、运行记录与汇总通知使用同一组原因。"""

from module.localization import tr

REASONS = {
    "account_unsupported": "当前运行方式不支持按账号运行",
    "account_not_found": "找不到指定账号",
    "account_no_login": "没有检测到账号登录",
    "account_server_mismatch": "账号和客户端服务器不符",
    "account_switch_failed": "切换登录失败",
    "account_mismatch": "登录的 UID 与指定账号不符",
    "account_login_expired": "登录过期",
    "account_timeout": "账号运行超时",
    "child_failed": "账号任务失败",
    "child_error": "启动或运行账号时出错",
    "child_record_missing": "子运行记录缺失",
    "child_crashed": "子进程意外退出",
    "rotation_parent_lost": "轮流运行进程已退出",
    "rotation_finish_failed": "轮流运行收尾失败",
    "stopped": "已停止",
    "skipped": "已跳过",
    "busy": "已有任务在运行",
    "first_run_required": "需要先完成首次使用确认",
    "missing_snapshot": "没有登录快照",
    "invalid_snapshot": "登录快照损坏或不属于这个账号",
    "game_running": "游戏仍在运行",
    "graphics_pending": "临时画质尚未恢复",
    "registry_failed": "登录信息写入失败",
}


def reason_text(code, error=None):
    if code in REASONS:
        return tr(REASONS[code])
    return error or (tr("运行未完成") if code else "")
