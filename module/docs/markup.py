"""Markdown's built-in extensions and a small HTML tree which keeps mixed content in order."""
from dataclasses import dataclass, field
from html.parser import HTMLParser
import re
from threading import local
import xml.etree.ElementTree as ET

from markdown import Markdown
from markdown.extensions import Extension
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.sane_lists import SaneListExtension
from markdown.extensions.tables import TableExtension
from markdown.inlinepatterns import InlineProcessor


class _Strike(InlineProcessor):
    def handleMatch(self, match, data):
        el = ET.Element("del")
        el.text = match[1]
        return el, match.start(0), match.end(0)


class _ReaderMarkup(Extension):
    def extendMarkdown(self, md):
        md.inlinePatterns.register(_Strike(r"~~(?!\s)(.+?)(?<!\s)~~", md), "strike", 75)


@dataclass(eq=False, slots=True)
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)


class Tree(HTMLParser):
    void = frozenset("area base br col embed hr img input link meta param source track wbr".split())

    def __init__(self):
        super().__init__()
        self.root = Node("root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in self.void:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


_thread = local()


_LIST_ITEM = re.compile(r"^( *)(?:[-*+]|\d+\.)[ \t]+(?=\S)")
_FENCE = re.compile(r"^(`{3,}|~{3,})(.*)$")


def list_indentation(source):
    """Docsify accepts 2/3-space children. Python-Markdown expects one tab stop per level."""
    lines = source.split("\n")
    columns = []
    fence = ""
    for i, line in enumerate(lines):
        if mark := _FENCE.match(line):
            if not fence:
                fence = mark[1]
            elif mark[1].startswith(fence) and not mark[2].strip():
                fence = ""
            continue
        if fence or not line.strip():
            continue
        match = _LIST_ITEM.match(line)
        if match:
            indent = len(match[1])
            while columns and indent < columns[-1]:
                columns.pop()
            if not columns and indent >= 4:
                continue  # An indented code block, outside a list.
            if not columns or indent > columns[-1]:
                columns.append(indent)
            lines[i] = " " * (4 * (len(columns) - 1)) + line[indent:]
        elif columns:
            indent = len(line) - len(line.lstrip(" "))
            if indent <= columns[0]:
                columns.clear()
    return "\n".join(lines)


def render_tree(source):
    if not hasattr(_thread, "md"):
        _thread.md = Markdown(extensions=[TableExtension(), FencedCodeExtension(), SaneListExtension(), _ReaderMarkup()])
    html = _thread.md.reset().convert(list_indentation(source))
    parser = Tree()
    parser.feed(html)
    parser.close()
    return parser.root


def node_text(node):
    if isinstance(node, str):
        return node
    return "".join(node_text(child) for child in node.children)


def elements(node):
    for child in node.children:
        if isinstance(child, Node):
            yield child
            yield from elements(child)


def heading_level(node):
    return int(node.tag[1]) if re.fullmatch(r"h[1-6]", node.tag) else 0
