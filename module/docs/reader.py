"""File-stamped reader API. The catalogue can be imported without loading the parser."""
from dataclasses import replace
from functools import lru_cache
import logging
from pathlib import Path
import re
from urllib.parse import unquote

from .anchors import article_for, prepare_article, slug, source_text
from .blocks import Builder
from .catalog import DOCUMENTS, Source, source_for
from .formats import question_title, release_headings, releases
from .model import Content, Document, Paragraph, Text

log = logging.getLogger(__name__)


def fallback(source, text, error):
    log.warning("帮助文档 %s 无法排版，已保留可读取的原文：%s", source.path, error)
    return Content((Paragraph((Text(text),)),), degraded=True)


def document_for(source):
    return _document(source, source.stamp)


@lru_cache(maxsize=48)
def _document(source, stamp):
    text = ""
    versions = ()
    try:
        text = source_text(source, stamp)
        if source.id == "Changelog":
            index = releases(source, stamp)
            versions = tuple(r.entry for r in index.entries.values())
            article = prepare_article(source, index.intro)
            toc = tuple(r.heading for r in index.entries.values())
        else:
            article = article_for(source, stamp)
            toc = tuple(h for h in article.headings if h.level in (2, 3))
            if source.id == "FAQ":
                toc = tuple(replace(h, title=question_title(h.title)) for h in toc if h.level == 3)
        content = Builder(source, article).content()
        headings = article.headings
        title = next((h.title for h in headings if h.level == 1), source.id)
    except Exception as exc:
        content = fallback(source, text, exc)
        title, toc = source.id, ()
    return Document(id=source.id, language=source.language, title=title, path=source.path,
                    blocks=content.blocks, broken_links=content.broken_links, plain_paths=content.plain_paths,
                    degraded=content.degraded, toc=toc, versions=versions)


def load_document(doc_id: str, language: str | None = None) -> Document:
    return document_for(source_for(doc_id, language))


def load_file(path, *, doc_id="Sample", language="zh_CN") -> Document:
    return document_for(Source(doc_id, language, Path(path).absolute()))


def outline(source):
    try:
        if source.id == "Changelog":
            return release_headings(source, source.stamp)
        return article_for(source, source.stamp).headings
    except Exception:
        document_for(source)  # Same fallback and one cached diagnostic.
        return ()


_MISSING = {
    "Tutorial": {"数据保存在哪里", "流程编排", "安卓设备（ADB）", "运行页", "首次配置向导"},
    "Workflow": {"命令行运行", "列出所有可用的流程名称", "运行整个流程", "仅运行指定步骤（步骤路径的含义见下文）", "仅运行指定步骤"},
    "FAQ": {"Q：手机上能用小助手吗？", "Q：账号提示「登录过期」，怎么恢复？", "Q：为什么提示登录的 UID 不符？",
            "Q：轮流时有一个账号切换失败，后面的还会跑吗？", "Q：为什么 A 号已经做完，B 号的任务还显示未完成？",
            "Q：换电脑后为什么提示重新保存密码？", "Q：旧版本的账号文件去哪了？"},
}


def _aligned(name, local, original):
    if name == "Changelog":
        def groups(headings):
            result = {"": []}
            version = ""
            for h in headings:
                if h.level == 2:
                    version = h.title
                    result[version] = []
                result[version].append(h)
            return result
        other = groups(original)
        return tuple((a, b) for version, group in groups(local).items()
                     if version in other and [h.level for h in group] == [h.level for h in other[version]]
                     for a, b in zip(group, other[version]))
    if len(local) < len(original):
        original = tuple(h for h in original if h.title not in _MISSING.get(name, ()))
    elif len(local) > len(original):
        local = tuple(h for h in local if h.title not in _MISSING.get(name, ()))
    if len(local) == len(original) and all(a.level == b.level for a, b in zip(local, original)):
        return tuple(zip(local, original))
    return ()


def _match(headings, value, web=False):
    if web:
        exact = next((h for h in headings if h.web_id and h.web_id == value), None)
        if exact:
            return exact
    for field in ("anchor", "web_id", "title"):
        for h in headings:
            if getattr(h, field) == value:
                return h
    for h in headings:
        short = re.sub(r"\s*[（(][^）)]*[）)]$", "", h.title)
        if slug(short) == value:
            return h
    return None


def resolve_anchor(source, anchor, *, web=False, written_language=None):
    if not anchor:
        return ""
    value = unquote(anchor).removeprefix("#")
    local = outline(source)
    if source.id in DOCUMENTS and written_language and written_language != source.language:
        written = outline(source_for(source.id, written_language))
        other = _match(written, value, web)
        if other:
            original = outline(source_for(source.id, "zh_CN"))
            canonical = next((b for a, b in _aligned(source.id, written, original) if a == other), None)
            for a, b in _aligned(source.id, local, original):
                if b == canonical:
                    return a.anchor
    if hit := _match(local, value, web):
        return hit.anchor
    if source.language == "zh_CN" or source.id not in DOCUMENTS:
        return ""
    original = outline(source_for(source.id, "zh_CN"))
    other = _match(original, value, web)
    if not other:
        return ""
    if source.id == "Tutorial" and other.title == "数据保存在哪里" and not any(h.title == other.title for h in local):
        # Older translations have no storage section. The registry help button opens the configuration guide.
        if source.language in ("en_US", "ja_JP", "ko_KR") and len(local) < len(original):
            other = next((h for h in original if h.title == "配置说明"), other)
    for h, orig in _aligned(source.id, local, original):
        if orig == other:
            return h.anchor
    return ""


def localized_anchor(name, anchor, language=None):
    return resolve_anchor(source_for(name, language), anchor)


def website_anchor(source, anchor):
    local = resolve_anchor(source, anchor)
    headings = outline(source)
    for i, h in enumerate(headings):
        if h.anchor == local:
            return h.web_id or next((p.web_id for p in reversed(headings[:i]) if p.web_id), "")
    return ""
