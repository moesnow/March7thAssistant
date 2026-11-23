"""Check desktop navigation mentioned in the maintained Markdown documents."""
import re
from pathlib import Path

import pytest
from opencc import OpenCC

from module.content_pages import PAGES, PAGE_BY_ID, GROUP_BY_ID
from module.settings_registry import SETTINGS, find_setting


ROOT = Path(__file__).resolve().parents[2]
SEPARATOR = r'\s*(?:→|›|>|＞|»)\s*'
START = re.compile(r'(设置|設定|任务|任務|运行|執行|運行)(?:' + SEPARATOR + r'|\s*-\s*)')
COMPOUND_MENU = re.compile(SEPARATOR + r'[\w ]+$')
LINK = re.compile(r'\bsetting:([^\s)`<>"\]\'，。]*)')
DELIMITERS = {'`': '`', '「': '」', '“': '”', '（': '）', '(': ')', '[': ']'}

# These paths describe other interfaces, even when they occur in a desktop manual.
EXTERNAL = {
    'Android': {
        ('关于手机',), ('我的设备', '全部参数与信息'), ('系统', '开发者选项'), ('更多设置', '开发者选项'),
        ('后台运行与省电',), ('关于',),  # Phone system menus and the Android app.
    },
    'DesktopTwin': {('账户', '登录选项')},  # Windows Hello sign-in options.
    'FAQ': {('战斗功能', '是否沿用自动战斗设置')},  # In-game battle settings.
}
# Preserve only the paths actually printed in historical release notes.
HISTORICAL = {("设置", "按键"), ("设置", "宇宙"), ("设置", "程序")}


def enclosed_text(tail, opening):
    closing = DELIMITERS[opening]
    depth = 1
    for index, char in enumerate(tail):
        if char == closing:
            depth -= 1
            if not depth:
                return tail[:index]
        elif char == opening:
            depth += 1
    return tail


def breadcrumbs(line):
    line = line.replace('**', '')
    # Adjacent code spans are also used for individual breadcrumb components.
    line = re.sub(r'`(' + SEPARATOR + r')`', r'\1', line)
    for match in START.finditer(line):
        # “管理设置” and “更多设置” can themselves be a component of another breadcrumb.
        if COMPOUND_MENU.search(line[:match.start()]):
            continue
        tail = line[match.end():]
        opening = line[match.start() - 1] if match.start() else ''
        if opening in DELIMITERS:
            tail = enclosed_text(tail, opening)
        else:
            tail = re.split(r'[`」”，。；：）)|\]\n]', tail, maxsplit=1)[0]
        yield (match[1], *(part.strip() for part in re.split(SEPARATOR, tail)))


def desktop_paths():
    paths = {("运行", "定时任务")}
    for page in PAGES:
        if page.kind == "page":
            continue
        root = "任务" if page.kind == "task" else "设置"
        paths.add((root, page.name))
        paths.update((root, page.name, group.title) for group in page.groups)
    for setting in SETTINGS:
        page = PAGE_BY_ID[setting.page]
        if page.kind == "page":
            continue
        root = "任务" if page.kind == "task" else "设置"
        group = GROUP_BY_ID[page.id, setting.section].title
        paths.update(((root, page.name, setting.title), (root, page.name, group, setting.title)))
    return paths


def test_maintained_documents_resolve_desktop_settings():
    convert = OpenCC('s2twp').convert

    def parts_tw(parts):
        return tuple(map(convert, parts))

    paths = desktop_paths()
    translated = {parts_tw(p) for p in paths}
    errors = []
    for directory in ('assets/docs', 'assets/agent', 'assets/logo', 'docs'):
        for file in (ROOT / directory).rglob('*.md'):
            if re.search(r'_(?:en_US|ja_JP|ko_KR)$', file.stem):
                continue
            name = file.stem.removesuffix('_zh_TW')
            tw = name != file.stem
            external = {('设置', *p) for p in EXTERNAL.get(name, set())}
            if name == 'Changelog':
                external.update(HISTORICAL)
            if tw:
                external = {parts_tw(p) for p in external}
            for line_no, line in enumerate(file.read_text(encoding='utf-8').splitlines(), 1):
                where = f'{file.relative_to(ROOT)}:{line_no}'
                for key in LINK.findall(line):
                    if find_setting(key) is None:
                        errors.append(f'{where}  setting:{key}')
                for path in breadcrumbs(line):
                    if path not in external and path not in (translated if tw else paths):
                        errors.append(f'{where}  {" → ".join(path)}')
    assert not errors, '\n' + '\n'.join(errors)


@pytest.mark.parametrize("text, expected", [
    ("在「设置 › 运行方式 > 本地操作模式」打开", [("设置", "运行方式", "本地操作模式")]),
    ("`設定 → 高級`、`设置` → `关于` → `AI 助手`", [("設定", "高級"), ("设置", "关于", "AI 助手")]),
    ("「任务 → 货币战争 → 启用「货币战争」积分奖励」", [("任务", "货币战争", "启用「货币战争」积分奖励")]),
    ("例如通过设置 › 消息推送 › 启用 Go-cqhttp 通知。", [("设置", "消息推送", "启用 Go-cqhttp 通知")]),
    ("（运行→定时任务）", [("运行", "定时任务")]),
])
def test_breadcrumbs_read_the_whole_path(text, expected):
    assert list(breadcrumbs(text)) == expected


def test_paths_follow_task_moves_and_reject_obsolete_settings_tabs():
    paths = desktop_paths()
    assert ("任务", "清体力", "刷什么", "副本类型") in paths
    assert ("设置", "游戏与启动", "游戏内按键") in paths
    assert ("设置", "程序") not in paths
    assert ("设置", "体力", "副本类型") not in paths
