"""Headings as rendered by the desktop Markdown reader, with stable duplicate anchors."""
from dataclasses import dataclass, replace
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
import re

import markdown

from module.localization.languages import localized_doc_path


def slug(title):
    return re.sub(r"[^\w\s-]", "", title.strip().casefold()).replace(" ", "-")


@dataclass(frozen=True)
class Heading:
    level: int
    title: str
    anchor: str
    excerpt: str = ""


class _Headings(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self.level = 0
        self.words = []
        self.counts = {}
        self.excerpt_tag = None
        self.excerpt_words = []

    def handle_starttag(self, tag, attrs):
        if re.fullmatch("h[1-6]", tag):
            self.level = int(tag[1])
            self.words = []
            self.excerpt_tag = None
        elif (tag in ("p", "li", "td", "pre") and self.items and not self.level and not self.items[-1].excerpt
              and self.excerpt_tag is None):
            self.excerpt_tag = tag
            self.excerpt_words = []

    def handle_data(self, data):
        if self.level:
            self.words.append(data)
        elif self.excerpt_tag:
            self.excerpt_words.append(data)

    def handle_endtag(self, tag):
        if self.level and tag == f"h{self.level}":
            title = " ".join("".join(self.words).split())
            base = slug(title)
            count = self.counts.get(base, 0) + 1
            self.counts[base] = count
            anchor = base if count == 1 else f"{base}~{count}"
            if base:
                self.items.append(Heading(self.level, title, anchor))
            self.level = 0
        elif tag == self.excerpt_tag:
            excerpt = " ".join("".join(self.excerpt_words).split())
            if excerpt:
                self.items[-1] = replace(self.items[-1], excerpt=excerpt if len(excerpt) <= 110 else excerpt[:109] + "…")
            self.excerpt_tag = None


@lru_cache(maxsize=48)
def read_headings(name, path):
    try:
        lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return ()
    lines = lines[2:] if name == "FAQ" else lines[1:]
    extensions = ["tables", "fenced_code"] if name == "Background" else ["tables"] if name in ("Tutorial", "Workflow", "TasksTable") else []
    parser = _Headings()
    parser.feed(markdown.markdown("\n".join(lines), extensions=extensions))
    for index in range(len(parser.items) - 2, -1, -1):
        row, following = parser.items[index:index + 2]
        if not row.excerpt and following.level > row.level:
            parser.items[index] = replace(row, excerpt=following.excerpt or following.title)
    return tuple(parser.items)


def heading_pairs(name):
    local = read_headings(name, localized_doc_path(name))
    source = read_headings(name, f"./assets/docs/{name}.md")
    if len(local) != len(source):
        # The English, Japanese and Korean manuals predate the following sections.
        missing = {
            "Tutorial": {"数据保存在哪里", "流程编排", "安卓设备（ADB）"},
            "Workflow": {"命令行运行", "列出所有可用的流程名称", "运行整个流程", "仅运行指定步骤（步骤路径的含义见下文）", "仅运行指定步骤"},
            "FAQ": {"Q：手机上能用小助手吗？"},
        }
        source = tuple(h for h in source if h.title not in missing.get(name, ()))
    aligned = len(local) == len(source) and all(a.level == b.level for a, b in zip(local, source))
    return tuple((h, source[i].title if aligned else h.title) for i, h in enumerate(local))


def localized_anchor(name, anchor):
    # A registry link in the manual can use the Chinese heading in any UI language.
    if not anchor:
        return anchor
    pairs = heading_pairs(name)
    if any(h.anchor == anchor for h, _ in pairs):
        return anchor
    for heading, original in pairs:
        short = re.sub(r"\s*[（(][^）)]*[）)]$", "", original)
        if anchor in (slug(original), slug(short)):
            return heading.anchor
    return anchor
