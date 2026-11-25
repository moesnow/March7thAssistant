"""从项目作者提供的 PNG 导出桌面端 Q 版插画。"""
import argparse
from pathlib import Path

from PIL import Image

DESTINATION = Path(__file__).resolve().parents[1] / "app/images/mascot"
POSES = {
    "全身站立": "chibi_full", "敲电脑": "chibi_typing", "挥手": "chibi_wave",
    "拿地图发懵": "chibi_lost", "探头比OK": "chibi_ok", "举相机": "chibi_camera",
    "抱礼盒": "chibi_gift", "认真": "chibi_serious", "放大镜": "chibi_search",
    "取景器": "chibi_viewfinder", "云端": "chibi_cloud", "眼花": "chibi_dizzy",
    "下次一定": "chibi_later", "盖章": "chibi_stamp", "吓一跳": "chibi_startled",
    "抱纸箱": "chibi_box",
}
EVERNIGHT = ("全身站立", "敲电脑", "挥手", "拿地图发懵", "探头比OK")


def prepare(source: Path, destination: Path = DESTINATION, *, evernight: bool = False):
    poses, prefix = POSES, ""
    if evernight:
        # 允许逐张补图。长夜月的原图单独放在一个目录。
        prefix = "长夜月_"
        poses = {name: POSES[name] for name in EVERNIGHT if (source / f"{prefix}{name}.png").is_file()}
        destination = destination / "evernight"
        if not poses:
            raise ValueError("指定目录中没有长夜月的五种问候姿势")
    destination.mkdir(parents=True, exist_ok=True)
    for name, stem in poses.items():
        with Image.open(source / f"{prefix}{name}.png") as original:
            rgba = original.convert("RGBA")
        box = rgba.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
        if box is None:
            raise ValueError(f"{name}.png 没有可见内容")
        left, top, right, bottom = box
        cropped = rgba.crop((left - 6, top - 6, right + 6, bottom + 6))
        cropped.thumbnail((512, 512), Image.Resampling.LANCZOS, reducing_gap=None)
        cropped.save(destination / f"{stem}.webp", "WEBP", quality=88, method=6)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--evernight", action="store_true", help="处理单独目录中的长夜月原图")
    args = parser.parse_args()
    prepare(args.source, evernight=args.evernight)
