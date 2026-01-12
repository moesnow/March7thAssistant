# coding:utf-8
import os


def is_gui_started():
    """检查是否从图形界面启动"""
    return os.environ.get("MARCH7TH_GUI_STARTED", "").lower() == "true"


def is_docker_started():
    """检查是否从Docker启动"""
    return os.environ.get("MARCH7TH_DOCKER_STARTED", "").lower() == "true"


def should_skip_pause():
    """检查是否应该跳过暂停（GUI或Docker启动时跳过）"""
    return is_gui_started() or is_docker_started()


def pause_on_error():
    """
    失败/错误时暂停（按回车继续）
    仅在非 GUI/Docker 启动且配置允许时暂停
    """
    from module.config import cfg
    if not cfg.exit_after_failure and not should_skip_pause():
        input("按回车键关闭窗口. . .")


def pause_on_success():
    """
    成功后暂停（按回车继续）
    仅在非 GUI/Docker 启动且配置允许时暂停
    """
    from module.config import cfg
    if cfg.pause_after_success and not should_skip_pause():
        input("按回车键关闭窗口. . .")


def pause_always():
    """
    始终暂停（按回车继续）
    仅在非 GUI/Docker 启动时暂停
    """
    if not should_skip_pause():
        input("按回车键关闭窗口. . .")


def pause_and_retry():
    """
    暂停等待重试（按回车重试）
    仅在非 GUI/Docker 启动时暂停，GUI/Docker 启动时直接退出
    """
    import sys
    if should_skip_pause():
        sys.exit(1)
    input("按回车键重试. . .")


def pause_and_continue():
    """
    暂停等待继续（按回车继续）
    仅在非 GUI/Docker 启动时暂停，GUI/Docker 启动时直接继续
    """
    if not should_skip_pause():
        input("按回车键继续. . .")
