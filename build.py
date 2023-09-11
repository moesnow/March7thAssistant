from module.ocr.install_ocr import InstallOcr
from tasks.weekly.universe import Universe
import sys

if not InstallOcr.run() or not Universe.update():
    sys.exit(1)
