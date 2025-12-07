from tasks.base.fastest_mirror import FastestMirror
from module.logger import log
from module.config import cfg
from module.notification import notif
from module.notification.notification import NotificationLevel
from packaging.version import parse
import requests


def start():
    try:
        if cfg.update_prerelease_enable and cfg.update_source == "GitHub":
            response = requests.get(FastestMirror.get_github_api_mirror("moesnow", "March7thAssistant", False), timeout=10, headers=cfg.useragent)
        else:
            response = requests.get(FastestMirror.get_github_api_mirror("moesnow", "March7thAssistant"), timeout=10, headers=cfg.useragent)
        if not cfg.check_update:
            return
        log.hr("开始检测更新", 0)
        if response.status_code == 200:
            if cfg.update_prerelease_enable and cfg.update_source == "GitHub":
                data = response.json()[0]
            else:
                data = response.json()

            version = data["tag_name"]

            assert_url = None
            for asset in data["assets"]:
                if ((cfg.update_full_enable or cfg.update_source == "MirrorChyan") and "full" in asset["browser_download_url"]) or \
                   (not cfg.update_full_enable and "full" not in asset["browser_download_url"]):
                    assert_url = asset["browser_download_url"]
                    break

            if assert_url is not None and parse(version.lstrip('v')) > parse(cfg.version.lstrip('v')):
                notif.notify(content=cfg.notify_template['NewVersion'].format(version=version), level=NotificationLevel.ALL)
                log.info(f"发现新版本：{cfg.version}  ——→  {version}")
                log.info(data["html_url"])
            else:
                log.info(f"已经是最新版本：{cfg.version}")
        else:
            log.warning("检测更新失败")
            log.debug(response.text)
        log.hr("完成", 2)
    except Exception:
        pass
