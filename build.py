from module.logger import log
from module.config import cfg
from module.ocr import ocr
from module.game import cloud_game
from tasks.weekly.universe import Universe
from tasks.daily.fight import Fight
from tasks.base.genshin_starRail_fps_unlocker import Genshin_StarRail_fps_unlocker
import re
import sys
import argparse
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


def generate_changelog(version: str, output_file: Path) -> None:
    """生成并输出日志内容"""
    log.info(f"[*] 生成版本 {version} 的日志内容...")
    log_content = get_changelog(version)

    # 生成最终内容
    final_output = f"""{log_content}

首次安装请下载文件名内含有"full"的压缩包，否则会因为缺少组件无法使用！

[已有 Mirror酱 CDK？前往 Mirror酱 高速下载](https://mirrorchyan.com/zh/download?rid=March7thAssistant&os=&arch=&channel=stable&source=m7a-release)"""

    output_file.write_text(final_output, encoding="utf-8")
    log.info(f"[✓] 日志内容已输出到 {output_file}")


def init_ocr() -> None:
    """初始化OCR"""
    log.info("[*] 初始化OCR...")
    ocr.instance_ocr(log_level="info")
    log.info("[✓] OCR初始化完成")


def update_universe() -> None:
    """更新Universe"""
    log.info("[*] 更新Universe...")
    Universe.update()
    log.info("[✓] Universe更新完成")


def update_fight() -> None:
    """更新Fight"""
    log.info("[*] 更新Fight...")
    Fight.update()
    log.info("[✓] Fight更新完成")


def update_fps_unlocker() -> None:
    """更新FPS解锁器"""
    log.info("[*] 更新Genshin StarRail FPS解锁器...")
    Genshin_StarRail_fps_unlocker.update()
    log.info("[✓] FPS解锁器更新完成")


def download_browser() -> None:
    """下载集成浏览器"""
    log.info("[*] 下载集成浏览器...")
    cfg.set_value("browser_download_use_mirror", False)
    cloud_game.download_intergrated_browser()
    log.info("[✓] 浏览器下载完成")


def execute_all_tasks(version: str = None, output_file: Path = None) -> None:
    """执行所有任务"""
    log.info("=" * 50)
    log.info("执行全部构建任务")
    log.info("=" * 50)

    init_ocr()
    update_universe()
    update_fight()
    update_fps_unlocker()
    download_browser()

    if version and output_file:
        generate_changelog(version, output_file)

    log.info("=" * 50)
    log.info("[✓] 所有任务执行完成")
    log.info("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="March7th Assistant 构建脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python build.py --help                                      # 显示帮助信息
  python build.py --task ocr                                  # 只初始化OCR
  python build.py --task universe                             # 只更新Universe
  python build.py --task fight                                # 只更新Fight
  python build.py --task fps-unlocker                         # 只更新FPS解锁器
  python build.py --task browser                              # 只下载浏览器
  python build.py --task changelog -v v1.0.0 -o changelog.md  # 只生成日志
  python build.py --task all -v v1.0.0 -o changelog.md        # 执行全部任务
  python build.py -v v1.0.0 -o changelog.md                   # 默认执行全部任务
        """
    )

    parser.add_argument(
        "--task",
        "-t",
        type=str,
        choices=["ocr", "universe", "fight", "fps-unlocker", "browser", "changelog", "all"],
        help="要执行的任务(默认: all)"
    )
    parser.add_argument(
        "--version",
        "-v",
        type=str,
        help="版本号(用于生成日志，如: v1.0.0)"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="日志输出文件路径"
    )

    # 处理向后兼容性：如果没有 --task 但有位置参数
    if len(sys.argv) >= 2 and not sys.argv[1].startswith("-"):
        # 旧格式: python build.py <version> <output_file>
        version = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
        if output_file:
            execute_all_tasks(version, Path(output_file))
            return
        else:
            log.error("错误: 旧格式用法需要同时提供版本号和输出文件: python build.py <version> <output_file>")
            sys.exit(1)

    args = parser.parse_args()

    # 如果没有指定任务，默认执行全部
    task = args.task or "all"

    try:
        if task == "ocr":
            init_ocr()
        elif task == "universe":
            update_universe()
        elif task == "fight":
            update_fight()
        elif task == "fps-unlocker":
            update_fps_unlocker()
        elif task == "browser":
            download_browser()
        elif task == "changelog":
            if not args.version or not args.output:
                log.error("错误: changelog 任务需要 --version 和 --output 参数")
                parser.print_help()
                sys.exit(1)
            generate_changelog(args.version, Path(args.output))
        elif task == "all":
            version = args.version
            output_file = Path(args.output) if args.output else None

            if args.version and not args.output:
                log.warning("警告: 指定了版本但未指定输出文件，将跳过日志生成")
                output_file = None

            execute_all_tasks(version, output_file)

    except Exception as e:
        log.error(f"[✗] 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
