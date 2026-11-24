"""Cached, language-aware desktop search. Index text is independent of the user's secrets."""
from dataclasses import dataclass, replace
import re
from urllib.parse import quote

from module.channel_catalog import CHANNELS
from module.content_visibility import Visibility
from module.connection_values import configured_backend
from module.content_pages import GROUP_BY_ID, PAGES, PAGE_BY_ID
from module.docs.catalog import SIDEBAR
from module.localization import get_current_language, tr
from module.localization.languages import available_languages
from module.navigation import TOP_PAGES
from module.settings_registry import SETTINGS, Scope
from module.task_catalog import TASKS
from module.tool_catalog import TOOLS
from .documents import heading_pairs
from .setting_text import CHOICES, DESCRIPTIONS, PAGE_DESCRIPTIONS
from .terms import SYNONYMS, normalize, suggestions, synonyms


@dataclass(frozen=True)
class Result:
    kind: str
    name: str
    location: str
    value: str
    description: str
    link: str
    icon: str
    score: int = 0


@dataclass(frozen=True)
class _Entry:
    result: Result
    names: tuple
    titles: tuple
    keywords: frozenset
    detail: str
    setting: object = None
    body: str = ""


def _entry(kind, title, path, description, link, icon, keywords=(), *, item=None, original=None, source_description=""):
    name = title
    location = " › ".join(tr(p) for p in path)
    desc = description
    result = Result(kind, name, location, "", desc, link, icon)
    terms = tuple(dict.fromkeys(normalize(v) for v in (name, original or title)))
    titles = tuple(re.sub(r"\([^()]*\)", "", name).strip() for name in terms)
    words = frozenset(normalize(v) for w in keywords if w for v in ((w,) if w.isascii() else (w, tr(w))))
    detail = normalize(" ".join((*path, location, source_description, desc)))
    return _Entry(result, terms, titles, words, detail, item)


def _entries(files):
    from module.docs.search import sections

    fields = {f.key: (c, f) for c in CHANNELS for f in c.fields}
    providers = {c.enable_key: c for c in CHANNELS}
    for item in SETTINGS:
        page, group = PAGE_BY_ID[item.page], GROUP_BY_ID[item.page, item.section]
        path = [{"setting": "设置", "task": "任务", "page": "运行"}[page.kind], page.name, group.title]
        path = list(dict.fromkeys(path))
        desc = DESCRIPTIONS.get(item.id, "")
        if item.id in fields:
            channel, field = fields[item.id]
            path.append(channel.name)
            desc = field.description or channel.description
        elif item.id in providers:
            desc = providers[item.id].description
        elif item.id == "qqbot_bind":
            path.append("QQ 官方机器人")
        keywords = (*item.keywords, *item.keys, *CHOICES.get(item.id, {}).values())
        name = (tr("启用 {name} 通知").format(name=tr(providers[item.id].name))
                if item.id in providers else tr(item.title))
        if desc:
            explanation = tr(desc)
        elif options := CHOICES.get(item.id):
            explanation = tr("可选项包括 {items}").format(items=" / ".join(tr(v) for v in options.values()))
        else:
            explanation = tr(group.title)
        yield _entry("setting", name, path, explanation, item.link, page.icon,
                     keywords, item=item, original=item.title, source_description=desc)
        if item.id == "control_backend":
            # Each choice opens the chooser; navigating to it never changes the backend.
            for option in CHOICES[item.id].values():
                yield _entry("setting", tr(option), path, explanation, item.link, page.icon,
                             item=item, original=option)
    for page in PAGES:
        if page.kind == "setting":
            groups = (tr(group.title) for group in page.groups if group.id != "header")
            explanation = tr(PAGE_DESCRIPTIONS[page.id]) if page.id in PAGE_DESCRIPTIONS else " / ".join(groups)
            yield _entry("category", tr(page.name), ("设置",), explanation, "category:" + page.id, page.icon, original=page.name)
    for task in TASKS:
        yield _entry("task", tr(task.name), ("任务", task.group), tr(task.description), "task:" + task.id, task.icon, original=task.name, source_description=task.description)
    for key, (name, _, icon) in TOP_PAGES.items():
        yield _entry("page", tr(name), (), tr(PAGE_DESCRIPTIONS[key]), "page:" + key, icon, original=name)
    for title, link, icon in ((tr("多账号轮流"), "page:accounts", "FIF.PEOPLE"),
                              (tr("账号密码自动填写"), "page:accounts", "FIF.PEOPLE"),
                              (tr("运行记录"), "run:history", "FIF.COMMAND_PROMPT")):
        group = tr("账号") if link == "page:accounts" else tr("运行")
        yield _entry("page", title, (group,), group, link, icon)
    for tool in TOOLS:
        yield _entry("tool", tr(tool.name), ("工具箱",), tr(tool.description), "tool:" + tool.id, tool.icon, original=tool.name, source_description=tool.description)
    for manual, (source, stamp) in zip(SIDEBAR, files):
        name, label = manual.id, manual.name
        indexed = {s.anchor: s for s in sections(source, stamp)}
        root = _entry("doc", tr(label), ("帮助",), tr(PAGE_DESCRIPTIONS[name]), "doc:" + name,
                      manual.icon, original=label)
        yield replace(root, body=normalize(indexed[""].body))
        parents = []
        for heading, original in heading_pairs(name):
            while parents and parents[-1].level >= heading.level:
                parents.pop()
            section = indexed.get(heading.anchor)
            if name != "Changelog" or section:
                title = section.title if section else heading.title
                entry = _entry("doc", title, ("帮助", label), heading.excerpt or tr(PAGE_DESCRIPTIONS[name]),
                               f"doc:{name}#{quote(heading.anchor)}", manual.icon, original=original)
                trail = " › ".join(p.title for p in parents)
                if trail:
                    entry = replace(entry, result=replace(entry.result, location=entry.result.location + " › " + trail),
                                    detail=entry.detail + " " + normalize(trail))
                yield replace(entry, body=normalize(section.body) if section else "")
            parents.append(heading)


def current_value(item, config):
    if not item.keys:
        return ""
    key = item.keys[0]
    value = config.get_value(key)
    if any(item.key_scope(k) == Scope.SECRET for k in item.keys):
        return tr("已设置") if any(config.get_value(k) for k in item.keys if item.key_scope(k) == Scope.SECRET) else tr("未设置")
    if key == "control_backend":
        value = configured_backend(config)
        if value not in ("local", "cloud", "adb"):
            return tr("暂时无法读取")
    if isinstance(value, (dict, list, tuple)):
        return tr("共 {count} 项").format(count=len(value))
    if key == "ui_language":
        return {v: k for k, v in available_languages().items()}.get(value, tr("自动"))
    if key == "browser_scale_factor" and isinstance(value, (int, float)) and value != 1:
        return f"{value:.0%}"
    if key == "weekly_divergent_level" and type(value) is int and 1 <= value <= 6:
        level = ("Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅹ")[value - 1]
        return tr("难度") + " " + level + (tr("（星阶模式）") if value == 6 else "")
    label = CHOICES.get(key, {}).get(value)
    if label is not None:
        return tr(label)
    if isinstance(value, bool):
        return tr("开") if value else tr("关")
    if value is None or value == "":
        return tr("未设置")
    text = str(value)
    return text if len(text) <= 44 else text[:18] + "…" + text[-24:]


class SearchIndex:
    def __init__(self, config):
        self.config = config
        self._language = None
        self._files = ()
        self._entries = ()
        self._synonyms = {}
        self._unsubscribe = config.subscribe(self._changed) if hasattr(config, "subscribe") else None

    def _changed(self, keys, external):
        if external or "ui_language" in keys:
            self.invalidate()

    def close(self):
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None

    def invalidate(self):
        self._language = None

    def prepare(self):
        from module.docs.search import signatures
        language = get_current_language()
        files = signatures(language)
        if self._language != language or self._files != files:
            self._entries = tuple(_entries(files))
            self._synonyms = synonyms(language)
            self._language, self._files = language, files

    def query(self, text, *, limit=24, kinds=None, settings_only=False):
        words = normalize(text).split()
        if not words or limit <= 0:
            return []
        self.prepare()
        tokens = [(word, self._synonyms.get(word, ())) for word in dict.fromkeys(words)]
        found = []
        for entry in self._entries:
            if kinds is not None and entry.result.kind not in kinds:
                continue
            if settings_only and (entry.setting is None or
                                  PAGE_BY_ID[entry.setting.page].kind != "setting" and entry.result.link != "run:schedule"):
                continue
            score = 0
            for word, aliases in tokens:
                if word in entry.names or word in entry.titles:
                    score += 130
                elif word in entry.keywords:
                    score += 120
                elif any(alias in entry.titles for alias in aliases):
                    score += 117 if any(n.startswith(word) for n in entry.titles) else 115
                elif any(n.startswith(word) for n in entry.titles):
                    score += 95
                elif any(word in n for n in entry.titles):
                    score += 85
                elif any(alias in entry.keywords for alias in aliases):
                    score += 80
                elif any(word in n for n in entry.names) or any(word in k for k in entry.keywords):
                    score += 65
                elif any(alias in n for n in entry.names for alias in aliases):
                    score += 58
                elif word in entry.detail:
                    score += 35
                elif any(alias in entry.detail for alias in aliases):
                    score += 18
                elif word in entry.body:
                    score += 12
                elif entry.body and any(alias in entry.body for alias in aliases):
                    score += 6
                else:
                    break
            else:
                found.append((score, entry))
        found.sort(key=lambda pair: (-pair[0], pair[1].result.kind == "doc"))
        seen, results = set(), []
        visibility = Visibility.read(self.config)
        for score, entry in found:
            if entry.result.link in seen:
                continue
            if entry.setting and not visibility.setting(entry.setting):
                continue
            kind, key = entry.result.kind, entry.result.link.partition(":")[2]
            if kind in ("page", "task") and not visibility.page(key) or kind == "tool" and not visibility.tool(key):
                continue
            seen.add(entry.result.link)
            value = current_value(entry.setting, self.config) if entry.setting else ""
            results.append(replace(entry.result, score=score, value=value))
            if len(results) >= limit:
                break
        return results

    suggestions = staticmethod(suggestions)
