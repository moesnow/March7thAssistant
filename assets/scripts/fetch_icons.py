# coding: utf-8
"""
按需拉取 GUI 图标（黑白双版 SVG）的一次性/可重复执行脚本。

图标来源（均为可再分发的开源图标库，经 Iconify JSON API 批量获取）：
- fluent  : Fluent UI System Icons（Microsoft，MIT）
- simple-icons : 品牌 logo（CC0-1.0）
- tabler / tdesign / icon-park-outline : 补充品牌 logo（MIT / Apache-2.0）

用法（在仓库根目录执行，仅依赖 Python 标准库）：
    python assets/scripts/fetch_icons.py

产物（提交进仓库，随 assets/ 一起打包分发）：
    assets/app/images/icons/ui/{name}_{black|white}.svg     通用 UI 图标
    assets/app/images/icons/brand/{name}_{black|white}.svg  品牌 logo

注意：品牌 logo 的商标权归属各公司，仅可用于标识对应产品/服务。
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://api.iconify.design"

# 通用 UI 图标：本地名称 -> Fluent UI System Icons 图标名（24px regular）
UI_ICONS = {
    "flash": "flash-24-regular",
    "battery-charge": "battery-charge-24-regular",
    "drop": "drop-24-regular",
    "beaker": "beaker-24-regular",
    "arrow-repeat-all": "arrow-repeat-all-24-regular",
    "arrow-clockwise": "arrow-clockwise-24-regular",
    "people": "people-24-regular",
    "people-checkmark": "people-checkmark-24-regular",
    "people-list": "people-list-24-regular",
    "people-link": "people-link-24-regular",
    "people-swap": "people-swap-24-regular",
    "people-team": "people-team-24-regular",
    "people-chat": "people-chat-24-regular",
    "target": "target-24-regular",
    "target-arrow": "target-arrow-24-regular",
    "diamond": "diamond-24-regular",
    "cube": "cube-24-regular",
    "planet": "planet-24-regular",
    "gift": "gift-24-regular",
    "send": "send-24-regular",
    "send-copy": "send-copy-24-regular",
    "clipboard-task": "clipboard-task-24-regular",
    "crown": "crown-24-regular",
    "trophy": "trophy-24-regular",
    "ticket-horizontal": "ticket-horizontal-24-regular",
    "sparkle": "sparkle-24-regular",
    "box": "box-24-regular",
    "stack": "stack-24-regular",
    "coin-multiple": "coin-multiple-24-regular",
    "coin-stack": "coin-stack-24-regular",
    "money": "money-24-regular",
    "wand": "wand-24-regular",
    "options": "options-24-regular",
    "gauge": "gauge-24-regular",
    "rocket": "rocket-24-regular",
    "clock": "clock-24-regular",
    "timer": "timer-24-regular",
    "hourglass": "hourglass-24-regular",
    "filter": "filter-24-regular",
    "merge": "merge-24-regular",
    "cloud": "cloud-24-regular",
    "cloud-arrow-down": "cloud-arrow-down-24-regular",
    "cloud-sync": "cloud-sync-24-regular",
    "eye-off": "eye-off-24-regular",
    "keyboard": "keyboard-24-regular",
    "key": "key-24-regular",
    "chart-multiple": "chart-multiple-24-regular",
    "speaker-2": "speaker-2-24-regular",
    "megaphone": "megaphone-24-regular",
    "megaphone-circle": "megaphone-circle-24-regular",
    "megaphone-loud": "megaphone-loud-24-regular",
    "mic": "mic-24-regular",
    "sound-wave-circle": "sound-wave-circle-24-regular",
    "plug-connected": "plug-connected-24-regular",
    "list": "list-24-regular",
    "pin": "pin-24-regular",
    "leaf-two": "leaf-two-24-regular",
    "compass-true-north": "compass-true-north-24-regular",
    "map": "map-24-regular",
    "food": "food-24-regular",
    "bookmark": "bookmark-24-regular",
    "server": "server-24-regular",
    "question": "question-24-regular",
    "toolbox": "toolbox-24-regular",
    "history": "history-24-regular",
    "link": "link-24-regular",
    "tap-single": "tap-single-24-regular",
    "person": "person-24-regular",
    "star": "star-24-regular",
    "arrow-import": "arrow-import-24-regular",
    "arrow-export": "arrow-export-24-regular",
    "select-all-on": "select-all-on-24-regular",
}

# 品牌 logo：本地图标名 -> (Iconify 集合, 图标名)
BRAND_ICONS = {
    "windows": ("simple-icons", "windows"),
    "telegram": ("simple-icons", "telegram"),
    "matrix": ("simple-icons", "matrix"),
    "discord": ("simple-icons", "discord"),
    "qq": ("simple-icons", "qq"),
    "bilibili": ("simple-icons", "bilibili"),
    "dingtalk": ("tabler", "brand-dingtalk"),
    "wecom": ("tdesign", "logo-wecom-filled"),
    "lark": ("icon-park-outline", "new-lark"),
}

COLORS = {"black": "#000000", "white": "#FFFFFF"}
ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "app", "images", "icons")
# viewBox 必须使用图标自身的网格尺寸（不同图标库可能是 16/24/32/48），
# 写死 24 会把大网格图标裁切到左上角
SVG_TEMPLATE = ('<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
                'viewBox="0 0 {w} {h}">{body}</svg>')


def fetch(url: str, retries: int = 5) -> bytes:
    """下载接口返回，带限流重试与退避。"""
    delay = 1.0
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "March7thAssistant-build"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise RuntimeError(f"重试耗尽: {url}")


def fetch_bodies(prefix: str, names: list) -> dict:
    """通过 JSON API 一次取回整批图标的 SVG body 与网格尺寸（含别名解析）。

    返回 {图标名: {"body": ..., "width": ..., "height": ...}}，
    宽高优先取图标自身声明，其次取集合默认值。
    """
    url = f"{API}/{prefix}.json?icons={','.join(names)}"
    data = json.loads(fetch(url).decode("utf-8"))
    icons = data.get("icons", {})
    aliases = data.get("aliases", {})
    default_w = data.get("width", 24)
    default_h = data.get("height", 24)
    result = {}
    for name in names:
        entry = icons.get(name)
        if entry is None and name in aliases:
            entry = icons.get(aliases[name].get("parent", ""))
        if entry is None or "body" not in entry:
            raise RuntimeError(f"图标缺失: {prefix}/{name}")
        result[name] = {
            "body": entry["body"],
            "width": entry.get("width", default_w),
            "height": entry.get("height", default_h),
        }
    return result


def write_pair(category: str, local_name: str, source: str, entry: dict, manifest: dict):
    target_dir = os.path.join(ROOT, category)
    os.makedirs(target_dir, exist_ok=True)
    w, h = entry["width"], entry["height"]
    for suffix, color in COLORS.items():
        svg = SVG_TEMPLATE.format(w=w, h=h, body=entry["body"].replace("currentColor", color))
        out = os.path.join(target_dir, f"{local_name}_{suffix}.svg")
        with open(out, "w", encoding="utf-8") as f:
            f.write(svg)
    manifest[f"{category}/{local_name}"] = {"source": source, "grid": [w, h]}
    print(f"ok  {category}/{local_name} ({w}x{h})")


def main():
    manifest = {}
    # 通用 UI 图标：全部来自 fluent 集合，分批请求（每批 40 个）
    names = list(UI_ICONS.values())
    for i in range(0, len(names), 40):
        batch = names[i:i + 40]
        bodies = fetch_bodies("fluent", batch)
        for local_name, remote in UI_ICONS.items():
            if remote in bodies:
                write_pair("ui", local_name, f"fluent/{remote}", bodies[remote], manifest)
        time.sleep(1.0)

    # 品牌 logo：按集合分组请求
    by_prefix = {}
    for local_name, (prefix, remote) in BRAND_ICONS.items():
        by_prefix.setdefault(prefix, []).append((local_name, remote))
    for prefix, items in by_prefix.items():
        bodies = fetch_bodies(prefix, [remote for _, remote in items])
        for local_name, remote in items:
            write_pair("brand", local_name, f"{prefix}/{remote}", bodies[remote], manifest)
        time.sleep(1.0)

    # 来源清单（含网格尺寸），测试与版权追溯都依赖它
    with open(os.path.join(ROOT, "sources.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)
    print("done")


if __name__ == "__main__":
    sys.exit(main())
