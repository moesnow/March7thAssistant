from module.config import cfg
from module.logger import log
import sys
import os
from utils.console import pause_on_error, pause_and_retry


class Genshin_StarRail_fps_unlocker:
    @staticmethod
    def update():
        from module.update.update_handler import UpdateHandler
        from tasks.base.fastest_mirror import FastestMirror
        import requests
        import json
        response = requests.get(FastestMirror.get_github_api_mirror("winTEuser", "Genshin_StarRail_fps_unlocker"), timeout=10, headers=cfg.useragent)
        if response.status_code == 200:
            data = json.loads(response.text)
            url = None
            for asset in data["assets"]:
                if asset["name"].startswith("Unlocker") and asset["name"].endswith(".exe"):
                    url = FastestMirror.get_github_mirror(asset["browser_download_url"])
                    break
            if url is None:
                log.error("没有找到可用更新，请稍后再试")
                pause_on_error()
                sys.exit(0)
            update_handler = UpdateHandler(url, cfg.genshin_starRail_fps_unlocker_path, "Genshin_StarRail_fps_unlocker")
            update_handler.download_file_path = os.path.join(cfg.genshin_starRail_fps_unlocker_path, "unlocker.exe")
            update_handler.download_file()
        else:
            log.error(f"获取更新信息失败：{response.status_code}")
