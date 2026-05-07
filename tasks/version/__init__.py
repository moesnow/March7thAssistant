"""主循环中的版本检测（仅通知，不执行更新）。"""
from module.config import cfg
from module.logger import log
from module.notification import notif
from module.notification.notification import NotificationLevel
from module.update.version_check import check_for_update


def start():
    if not cfg.check_update:
        return
    try:
        log.hr("开始检测更新", 0)
        info = check_for_update(
            source=getattr(cfg, "update_source", "GitHub"),
            cdk=getattr(cfg, "mirrorchyan_cdk", ""),
            prerelease=bool(getattr(cfg, "update_prerelease_enable", False)),
        )
        if info is not None:
            notif.notify(
                content=cfg.notify_template["NewVersion"].format(version=info.version),
                level=NotificationLevel.ERROR,
            )
            log.info(f"发现新版本：{cfg.version}  ——→  {info.version}")
        else:
            log.info(f"已经是最新版本：{cfg.version}")
        log.hr("完成", 2)
    except Exception:
        pass
