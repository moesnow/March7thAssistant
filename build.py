from module.ocr.install_ocr import InstallOcr
from tasks.weekly.universe import Universe
from tasks.daily.fight import Fight
import sys

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "github-actions":
        from managers.config_manager import config
        config.set_value("github_mirror", "")

    if not InstallOcr.run() or not Universe.update() or not Fight.update():
        sys.exit(1)
