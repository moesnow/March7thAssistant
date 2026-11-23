"""Check desktop navigation mentioned in the maintained Markdown documents."""
import gettext
import re
from pathlib import Path

import pytest
from opencc import OpenCC

from module.docs.paths import EXTERNAL, HISTORICAL, breadcrumbs, desktop_paths
from module.settings_registry import find_setting


ROOT = Path(__file__).resolve().parents[2]
LINK = re.compile(r'\bsetting:([^\s)`<>"\]\'，。]*)')


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


@pytest.mark.parametrize("language", ["zh_TW", "en_US", "ja_JP", "ko_KR"])
def test_every_setting_path_label_has_a_translation(language, compiled_locales):
    catalog = gettext.translation("march7th", compiled_locales, languages=[language])
    labels = {label for path in desktop_paths() for label in path}
    assert not labels.difference(catalog._catalog)
