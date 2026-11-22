"""Check desktop navigation mentioned in the maintained Markdown documents."""
import re
from collections import Counter
from pathlib import Path

import pytest
from opencc import OpenCC

from module.settings_registry import SETTINGS, find_setting


ROOT = Path(__file__).resolve().parents[2]
SEPARATOR = r'\s*(?:→|›|>|＞|»)\s*'
START = re.compile(r'(?:设置|設定)(?:' + SEPARATOR + r'|\s*-\s*)')
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
# The changelog records the label shipped in that release. Resolve it to its present tab.
HISTORICAL_TABS = {('按键',): ('杂项',), ('宇宙',): ('差分宇宙',)}


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
        yield tuple(part.strip() for part in re.split(SEPARATOR, tail))


def desktop_paths():
    paths = set()
    short = Counter((s.tab, s.title) for s in SETTINGS)
    for setting in SETTINGS:
        tab = (setting.tab,)
        group = (setting.group,) if setting.group != setting.tab else ()
        path = (*setting.parents, setting.title)
        paths.update((tab, tab + group, tab + path, tab + group + path))
        if short[(setting.tab, setting.title)] == 1:
            paths.add(tab + (setting.title,))
    return paths


def test_maintained_documents_resolve_desktop_settings():
    convert = OpenCC('s2twp').convert

    def parts_tw(parts):
        return tuple(map(convert, parts))

    paths = desktop_paths()
    translated = {parts_tw(p) for p in paths}
    errors = []
    for directory in ('assets/docs', 'assets/agent'):
        for file in (ROOT / directory).rglob('*.md'):
            if re.search(r'_(?:en_US|ja_JP|ko_KR)$', file.stem):
                continue
            name = file.stem.removesuffix('_zh_TW')
            tw = name != file.stem
            external = EXTERNAL.get(name, set())
            aliases = HISTORICAL_TABS if name == 'Changelog' else {}
            if tw:
                external = {parts_tw(p) for p in external}
                aliases = {parts_tw(p): parts_tw(q) for p, q in aliases.items()}
            for line_no, line in enumerate(file.read_text(encoding='utf-8').splitlines(), 1):
                where = f'{file.relative_to(ROOT)}:{line_no}'
                for key in LINK.findall(line):
                    if find_setting(key) is None:
                        errors.append(f'{where}  setting:{key}')
                for path in breadcrumbs(line):
                    if path not in external and aliases.get(path, path) not in (translated if tw else paths):
                        errors.append(f'{where}  {" → ".join(path)}')
    assert not errors, '\n' + '\n'.join(errors)


@pytest.mark.parametrize('text, expected', [
    ('在「设置 › 游戏连接 > 本地操作模式」打开', [('游戏连接', '本地操作模式')]),
    ('`設定 → 雜項`、`设置` → `关于` → `AI 助手`', [('雜項',), ('关于', 'AI 助手')]),
    ('「设置 → 货币战争 → 启用「货币战争」积分奖励」', [('货币战争', '启用「货币战争」积分奖励')]),
    ('例如通过设置 › 推送 › 启用 Go-cqhttp 通知。', [('推送', '启用 Go-cqhttp 通知')]),
    ('（设置→杂项→已删除的卡）', [('杂项', '已删除的卡')]),
])
def test_breadcrumbs_read_the_whole_path(text, expected):
    assert list(breadcrumbs(text)) == expected
