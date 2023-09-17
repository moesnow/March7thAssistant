from module.ocr.install_ocr import InstallOcr
from tasks.weekly.universe import Universe
import sys

if len(sys.argv) > 1 and sys.argv[1] == "github-actions":
    from managers.config_manager import config
    config.set_value("github_mirror", "")

if not InstallOcr.run() or not Universe.update():
    sys.exit(1)
