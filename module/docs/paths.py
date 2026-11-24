"""Desktop breadcrumbs in published prose. Labels are always source-language registry data."""
from dataclasses import dataclass
from functools import lru_cache
import re

from module.content_pages import GROUP_BY_ID, PAGE_BY_ID, PAGES
from module.localization import _s2t, translations_of
from module.settings_registry import SETTINGS

from .model import SettingPath, Text
from .traditional import TRADITIONAL

SEPARATOR = r"\s*(?:→|›|>|＞|»)\s*"
_COMPOUND = re.compile(SEPARATOR + r"[\w ]+$")
_DELIMITERS = {"`": "`", "「": "」", "“": "”", "（": "）", "(": ")", "[": "]", '"': '"', "'": "'",
               "‘": "’", "『": "』"}
_ROOTS = {"zh_CN": ("设置", "任务", "运行"), "zh_TW": ("設定", "任務", "執行", "運行"),
          "en_US": ("Settings", "Tasks", "Run"), "ja_JP": ("設定", "タスク", "実行"),
          "ko_KR": ("설정", "작업", "태스크", "실행")}
_END = re.compile(r"[`」』”，。；：）)|\]\n,;!?！？、\"'’]|[.](?=\s|$)")
EXTERNAL = {
    "Android": {("关于手机",), ("我的设备", "全部参数与信息"), ("系统", "开发者选项"), ("更多设置", "开发者选项"),
                ("后台运行与省电",), ("关于",)},
    "DesktopTwin": {("账户", "登录选项")},
    "FAQ": {("战斗功能", "是否沿用自动战斗设置")},
}
HISTORICAL = {("设置", "按键"), ("设置", "宇宙"), ("设置", "程序")}


@lru_cache(maxsize=2048)
def _label(text, language):
    if language == "zh_CN":
        return text
    if language == "zh_TW":
        return TRADITIONAL.get(text) or _s2t(text) or text
    return translations_of(text, language=language).get(language, text)


@dataclass(frozen=True)
class Destination:
    labels: tuple[str, ...]
    link: str


@lru_cache(maxsize=1)
def _registry():
    paths = {}
    for page in PAGES:
        if page.kind == "page":
            continue
        root = "任务" if page.kind == "task" else "设置"
        page_path = (root, page.name)
        link = ("task:" if page.kind == "task" else "category:") + page.id
        paths[page_path] = Destination(page_path, link)
        for group in page.groups:
            parts = (*page_path, group.title)
            paths[parts] = Destination(tuple(dict.fromkeys(parts)), link)
    items = {}
    for item in SETTINGS:
        page = PAGE_BY_ID[item.page]
        if page.kind == "page":
            continue
        root = "任务" if page.kind == "task" else "设置"
        group = GROUP_BY_ID[page.id, item.section].title
        full = (root, page.name, group, item.title)
        dest = Destination(tuple(dict.fromkeys(full)), item.link)
        for key in (full, (root, page.name, item.title)):
            if key in items and items[key] != dest:
                items[key] = None  # E.g. identically named fields on different notification channels.
            else:
                items[key] = dest
    paths.update(items)
    schedule = (PAGE_BY_ID["run"].name, GROUP_BY_ID["run", "schedule"].title)
    paths[schedule] = paths[("运行", "定时任务")] = Destination(schedule, "run:schedule")
    return paths


def desktop_paths():
    return set(_registry())


@lru_cache(maxsize=12)
def _localized(language, *, full=False):
    result = {}
    for path, destination in _registry().items():
        if language == "zh_TW" and not full and not all(p in TRADITIONAL for p in path):
            continue
        labels = tuple(_label(p, language).casefold() for p in path)
        if labels in result and result[labels] != destination:
            result[labels] = None
        else:
            result[labels] = destination
    return result


@lru_cache(maxsize=8)
def _start(language):
    roots = set(_ROOTS["zh_CN"] + _ROOTS["zh_TW"])
    roots.update(_ROOTS.get(language, ()))
    roots.update(_label(s, language) for s in _ROOTS["zh_CN"])
    return re.compile("(" + "|".join(map(re.escape, sorted(roots, key=len, reverse=True))) +
                      ")(?:" + SEPARATOR + r"|\s*-\s*)", re.I)


def _ranges(line, language, code_ends=None):
    end_previous = 0
    for match in _start(language).finditer(line):
        start = match.start()
        if start < end_previous or _COMPOUND.search(line[:start]):
            continue
        opening = line[start - 1] if start else ""
        end = match.end()
        if opening in _DELIMITERS:
            depth = 1
            while end < len(line):
                char = line[end]
                if char == _DELIMITERS[opening]:
                    depth -= 1
                    if not depth:
                        break
                elif char == opening:
                    depth += 1
                end += 1
            left, right = start - 1, min(end + 1, len(line))
        else:
            stop = _END.search(line, end)
            end = stop.start() if stop else len(line)
            # The Markdown code span supplies the closing delimiter after HTML conversion.
            if code_ends:
                for code_start, code_end in code_ends:
                    if code_end > match.end() and code_start < end and not re.match(SEPARATOR, line[code_end:]):
                        end = min(end, code_end)
                        break
            left, right = start, end
        tail = line[match.end():end].rstrip()
        parts = (match[1], *(part.strip() for part in re.split(SEPARATOR, tail)))
        yield left, right, parts
        end_previous = right


def breadcrumbs(line):
    """Source Markdown path check shared with the maintained-manual audit."""
    line = re.sub(r"`(" + SEPARATOR + r")`", r"\1", line.replace("**", ""))
    return (parts for _, _, parts in _ranges(line, "zh_CN"))


def path_spans(spans, source, plain_paths):
    from .blocks import span_slice
    if not spans:
        return spans
    text = "".join(s.text for s in spans)
    if not any(separator in text for separator in "→›>＞»-"):
        return spans
    code_ends = []
    pos = 0
    for span in spans:
        if span.code:
            code_ends.append((pos, pos + len(span.text)))
        pos += len(span.text)
    result, cursor = [], 0
    for left, right, parts in _ranges(text, source.language, code_ends):
        key = tuple(p.casefold() for p in parts)
        external = EXTERNAL.get(source.id, ())
        excluded = any(key == tuple(_label(p, source.language).casefold() for p in ("设置", *path))
                       for path in external)
        dest = None
        if not excluded and source.id != "Changelog":
            mapping = _localized(source.language)
            if source.language == "zh_TW" and key not in mapping:
                mapping = _localized(source.language, full=True)
            dest = mapping.get(key)
            if dest is None and text[left:left+1] not in _DELIMITERS:
                # A bare path can be followed by prose without a comma, e.g. “Settings → About to view …”.
                tail = parts[-1]
                for boundary in reversed(list(re.finditer(r"\s+|(?=[中里下](?:打开|查看|选择|找到))", tail))):
                    end = boundary.start()
                    candidate = mapping.get((*key[:-1], tail[:end].casefold()))
                    if candidate is not None:
                        dest = candidate
                        right = left + text[left:right].rfind(tail) + end
                        break
        if dest is None:
            plain_paths.append(text[left:right])
            continue
        result.extend(span_slice(spans, cursor, left))
        result.append(SettingPath(text[left:right], dest.labels, dest.link))
        cursor = right
    return tuple(result) + span_slice(spans, cursor) if result else spans


def replace_paths(spans, source, plain_paths):
    # A breadcrumb can span bold and adjacent inline-code runs, but never an explicit link or image.
    run, result = [], []
    for span in spans:
        if isinstance(span, Text) and span.link is None:
            run.append(span)
        else:
            result.extend(path_spans(tuple(run), source, plain_paths))
            run.clear()
            result.append(span)
    result.extend(path_spans(tuple(run), source, plain_paths))
    return tuple(result)
