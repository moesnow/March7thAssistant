from module.logger import log
from module.config import cfg
from module.ocr import OCRInstaller
from module.game import cloud_game
from tasks.weekly.universe import Universe
from tasks.daily.fight import Fight
from tasks.base.genshin_starRail_fps_unlocker import Genshin_StarRail_fps_unlocker
import re
import sys
from pathlib import Path

CHANGELOG_PATH = Path("assets/docs/Changelog.md")


def get_changelog(version: str) -> str:
    text = CHANGELOG_PATH.read_text(encoding="utf-8")

    pattern = rf"## {re.escape(version)}\s+(.*?)(?=\n## |\Z)"
    match = re.search(pattern, text, flags=re.S)

    if not match:
        raise ValueError(f"未找到版本 {version} 的日志内容")

    section = match.group(1).strip()
    return section


if __name__ == "__main__":
    ocr_installer = OCRInstaller(log)
    ocr_installer.check_and_install()
    Universe.update()
    Fight.update()
    Genshin_StarRail_fps_unlocker.update()
    cfg.set_value("browser_download_use_mirror", False)
    cloud_game.download_intergrated_browser()

    if len(sys.argv) < 3:
        print("Usage: python build.py <version> <output_file>")
        sys.exit(1)

    version = sys.argv[1]
    output_file = Path(sys.argv[2])
    log = get_changelog(version)

    # 生成最终内容
    final_output = f"""{log}

首次安装请下载文件名内含有“full”的压缩包，否则会因为缺少组件无法使用！

[已有 Mirror酱 CDK？前往 Mirror酱 高速下载](https://mirrorchyan.com/zh/download?rid=March7thAssistant&os=&arch=&channel=stable&source=m7a-release)"""

    output_file.write_text(final_output, encoding="utf-8")
