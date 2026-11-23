"""The desktop identity and the bundled docsify 4.13.1 Tn identity have separate counters."""
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from html import escape
import re

from .catalog import Source
from .markup import elements, heading_level, node_text, render_tree
from .model import Anchor


def slug(title):
    return re.sub(r"[^\w\s-]", "", title.strip().casefold()).replace(" ", "-")


_WEB_PUNCT = re.compile(r"""[\u2000-\u206F\u2E00-\u2E7F\\'!"#$%&()*+,./:;<=>?@\[\]^`{|}~]""")
# Keep declaration paragraphs distinct from an immediately following, separate quotation.
NOTICE = re.compile(r"本文件由簡體|本文件由简体|(?:document|file).*?(?:translated|translation)|"
                    r"簡体字中国語.*翻訳|중국어 간체.*번역", re.I)


def web_slug(title):
    text = re.sub(r"[A-Z]+", lambda m: m[0].lower(), title.strip())
    text = _WEB_PUNCT.sub("", re.sub(r"<[^>]+>", "", text))
    return re.sub(r"^([0-9])", r"_\1", re.sub(r"-+", "-", re.sub(r"\s", "-", text)))


class AnchorNames:
    def __init__(self):
        self.desktop = Counter()
        self.web = Counter()

    def add(self, level, title, *, page_title=False, code=False):
        title = " ".join(title.split())
        base = slug(title)
        if not page_title:
            self.desktop[base] += 1
        count = self.desktop[base]
        anchor = f"{base}~{count}" if count > 1 else base
        web_id = ""
        if not code:
            # marked passes rendered inline HTML (including escaped text) to Tn.
            key = web_slug(escape(title).replace("&#x27;", "&#39;"))
            serial = self.web[key]
            self.web[key] += 1
            web_id = f"{key}-{serial}" if serial else key
        return Anchor(level, title, anchor, web_id)


@lru_cache(maxsize=64)
def source_text(source: Source, stamp):
    return source.path.read_text(encoding="utf-8-sig", errors="replace")


@dataclass
class Article:
    root: object
    bindings: dict
    headings: tuple[Anchor, ...]


def prepare_article(source, text, supplied=(), *, declaration=True):
    first = re.match(r"\A(#[^\n]*\n\s*\n>[^\n]*(?:\n>[^\n]*)*)(\n\s*\n)(?=>)", text)
    if first and declaration and NOTICE.search(first[1]):
        root = render_tree(first[1])
        root.children.extend(render_tree(text[first.end():]).children)
    else:
        root = render_tree(text)
    names = AnchorNames()
    provided = iter(supplied)
    bindings, outline = {}, []
    for node in elements(root):
        if level := heading_level(node):
            title = node_text(node)
            heading = next(provided, None) or names.add(level, title, page_title=not outline and level == 1)
            bindings[node] = heading
            outline.append(heading)
        elif node.tag == "pre" and source.id == "Workflow" and source.language in ("zh_CN", "zh_TW"):
            # Phase 3 indexed three shell comments as H1. Old links land on the original code.
            aliases = tuple(names.add(1, m[1], code=True) for m in re.finditer(r"^# (.+)$", node_text(node), re.M))
            bindings[node] = aliases
            outline.extend(aliases)
    return Article(root, bindings, tuple(outline))


@lru_cache(maxsize=48)
def article_for(source, stamp):
    return prepare_article(source, source_text(source, stamp))
