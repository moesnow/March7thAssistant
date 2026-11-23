"""Turn the Markdown HTML tree into self-contained, immutable reader blocks."""
from dataclasses import replace
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from .anchors import NOTICE
from .code import color_code
from .markup import Node, heading_level, node_text
from .links import classify_link
from .paths import replace_paths
from .model import (Break, Callout, CodeBlock, Content, Details, Divider, Heading, Image,
                    ListBlock, Paragraph, Status, Table, Text, inline_text)

_MARKERS = {
    "info": ("note", "info", "说明", "說明", "注", "注記", "補足", "참고", "안내"),
    "tip": ("tip", "hint", "提示", "小贴士", "小貼士", "ヒント", "팁"),
    "warning": ("warning", "attention", "注意", "警告", "주의", "경고"),
    "danger": ("danger", "caution", "important", "危险", "危險", "重要", "危険", "위험", "중요"),
}
_KIND = {key.casefold(): kind for kind, keys in _MARKERS.items() for key in keys}
_MARKER = re.compile(r"^\s*(?:\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]|("
                     + "|".join(map(re.escape, _KIND)) + r")\s*[:：])\s*", re.I)
_STATUS = {"✅": "yes", "✔": "yes", "✓": "yes", "❌": "no", "✗": "no", "✖": "no",
           "⚠": "partial", "🟡": "partial", "△": "partial", "◐": "partial"}
_STYLE = {"strong": "bold", "b": "bold", "em": "italic", "i": "italic", "code": "code",
          "kbd": "code", "del": "strike", "s": "strike", "strike": "strike"}
_BLOCKS = set("p ul ol table blockquote pre hr details div section article main aside figure figcaption".split())


def span_slice(spans, start, end=None):
    """Keep style/link boundaries when removing a prefix or replacing a range."""
    result = []
    pos = 0
    for span in spans:
        size = len(inline_text((span,)))
        stop = pos + size
        if start <= pos and (end is None or stop <= end):
            result.append(span)
        elif isinstance(span, Text) and stop > start and (end is None or pos < end):
            result.append(replace(span, text=span.text[max(start-pos, 0):None if end is None else end-pos]))
        pos = stop
        if end is not None and pos >= end:
            break
    return tuple(result)


def _callout(blocks, notice):
    if not blocks or not isinstance(blocks[0], Paragraph):
        return Callout("info", (), blocks)
    spans = blocks[0].spans
    kind, marker, title = "info", "", ()
    if notice and NOTICE.search(inline_text(spans)):
        kind = "declaration"
    elif match := _MARKER.match(inline_text(spans)):
        kind = _KIND[(match[1] or match[2]).casefold()]
        marker = match[0]
        spans = span_slice(spans, match.end())
    count = 0
    while count < len(spans) and isinstance(spans[count], Text) and spans[count].bold:
        count += 1
    if count and re.search(r"[？?！!。.:：；;]\s*$", inline_text(spans[:count])):
        title, spans = spans[:count], spans[count:]
    first = (Paragraph(spans),) if spans and inline_text(spans).strip() else ()
    return Callout(kind, title, first + blocks[1:], marker)


class Builder:
    def __init__(self, source, article, *, declaration=True):
        self.source = source
        self.article = article
        first_body = next((n for n in article.root.children if isinstance(n, Node) and n.tag != "h1"), None)
        self.notice = declaration and first_body is not None and first_body.tag == "blockquote"
        self.links = {}
        self.broken_links = []
        self.plain_paths = []

    def content(self):
        blocks = tuple(self.blocks(self.article.root.children))
        return Content(blocks, tuple(self.broken_links), tuple(self.plain_paths))

    def link(self, url):
        if url not in self.links:
            self.links[url] = classify_link(url, self.source)
        result = self.links[url]
        if result is None:
            self.broken_links.append(url)
        return result

    def image(self, node, link):
        url = node.attrs.get("src", "")
        path = None
        if url and not url.startswith(("//", "\\")) and not urlsplit(url).scheme:
            file = unquote(urlsplit(url).path)
            local = (Path.cwd() / file.lstrip("/") if file.startswith("/") else self.source.path.parent / file)
            if local.is_file():
                path = local.resolve()
        return Image(node.attrs.get("alt", ""), url, path, link)

    def inline(self, nodes, style):
        for node in nodes:
            if isinstance(node, str):
                if node:
                    yield replace(style, text=node)
            elif node.tag == "br":
                yield Break()
            elif node.tag == "img":
                yield self.image(node, style.link)
            else:
                nested = style
                if node.tag in _STYLE:
                    nested = replace(style, **{_STYLE[node.tag]: True})
                elif node.tag == "a" and "href" in node.attrs:
                    nested = replace(style, link=self.link(node.attrs["href"]))
                yield from self.inline(node.children, nested)

    def spans(self, nodes):
        return replace_paths(tuple(self.inline(nodes, Text(""))), self.source, self.plain_paths)

    def blocks(self, nodes):
        pending = []
        for node in nodes:
            if isinstance(node, str) or (node.tag not in _BLOCKS and not heading_level(node)):
                pending.append(node)
                continue
            yield from self.paragraph(pending)
            pending.clear()
            yield from self.block(node)
        yield from self.paragraph(pending)

    def paragraph(self, nodes):
        spans = self.spans(nodes)
        if not spans:
            return
        visible = [s for s in spans if not isinstance(s, Text) or s.text.strip()]
        if len(visible) == 1 and isinstance(visible[0], Image):
            yield visible[0]
        elif visible:
            yield Paragraph(spans)

    def block(self, node):
        if heading_level(node):
            anchor = self.article.bindings[node]
            yield Heading(anchor.level, self.spans(node.children), anchor.title, anchor.anchor)
        elif node.tag == "p":
            yield from self.paragraph(node.children)
        elif node.tag in ("ul", "ol"):
            start = node.attrs.get("start", "1")
            items = tuple(tuple(self.blocks(li.children)) for li in node.children
                          if isinstance(li, Node) and li.tag == "li")
            yield ListBlock(node.tag == "ol", int(start) if re.fullmatch(r"-?\d+", start) else 1, items)
        elif node.tag == "table":
            yield self.table(node)
        elif node.tag == "blockquote":
            notice, self.notice = self.notice, False
            yield _callout(tuple(self.blocks(node.children)), notice)
        elif node.tag == "pre":
            code = next((c for c in node.children if isinstance(c, Node) and c.tag == "code"), node)
            lang = next((v[9:] for v in code.attrs.get("class", "").split() if v.startswith("language-")), "")
            raw = node_text(code)
            yield CodeBlock(lang, raw, color_code(lang, raw), self.article.bindings.get(node, ()))
        elif node.tag == "hr":
            yield Divider()
        elif node.tag == "details":
            summary = next((c for c in node.children if isinstance(c, Node) and c.tag == "summary"), None)
            yield Details(self.spans(summary.children) if summary else (),
                          tuple(self.blocks(c for c in node.children if c is not summary)), "open" in node.attrs)
        else:
            yield from self.blocks(node.children)

    def table(self, node):
        def table_rows(section):
            for child in section.children:
                if isinstance(child, Node):
                    if child.tag == "tr":
                        yield [c for c in child.children if isinstance(c, Node) and c.tag in ("td", "th")]
                    elif child.tag in ("thead", "tbody", "tfoot"):
                        yield from table_rows(child)

        def cell(node):
            spans = self.spans(node.children)
            if len(spans) == 1 and isinstance(spans[0], Text) and not spans[0].link:
                text = spans[0].text
                if status := _STATUS.get(text.strip().replace("\ufe0f", "")):
                    return (Status(text, status),)
            return spans

        rows = list(table_rows(node))
        first = rows[0] if rows else []
        align = []
        for c in first:
            match = re.search(r"text-align:\s*(left|center|right)", c.attrs.get("style", ""))
            align.append(match[1] if match else c.attrs.get("align", "default"))
        header = tuple(cell(c) for c in first) if any(c.tag == "th" for c in first) else ()
        return Table(header, tuple(tuple(cell(c) for c in row) for row in rows[bool(header):]), tuple(align))
