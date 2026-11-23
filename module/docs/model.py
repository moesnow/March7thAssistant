"""Immutable, display-independent parts of a manual. All offsets index Python strings."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Link:
    kind: str
    target: str


@dataclass(frozen=True, slots=True)
class Text:
    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False
    strike: bool = False
    link: Link | None = None


@dataclass(frozen=True, slots=True)
class SettingPath:
    text: str
    labels: tuple[str, ...]
    target: str


@dataclass(frozen=True, slots=True)
class Status:
    text: str
    value: str


@dataclass(frozen=True, slots=True)
class Break:
    text: str = "\n"


@dataclass(frozen=True, slots=True)
class Image:
    alt: str
    url: str
    path: Path | None
    link: Link | None = None


Inline = Text | SettingPath | Status | Break | Image
Spans = tuple[Inline, ...]


@dataclass(frozen=True, slots=True)
class Anchor:
    level: int
    title: str
    anchor: str
    web_id: str


@dataclass(frozen=True, slots=True)
class Heading:
    level: int
    spans: Spans
    text: str
    anchor: str


@dataclass(frozen=True, slots=True)
class Paragraph:
    spans: Spans


@dataclass(frozen=True, slots=True)
class ListBlock:
    ordered: bool
    start: int
    items: tuple[tuple[Block, ...], ...]


@dataclass(frozen=True, slots=True)
class Table:
    header: tuple[Spans, ...]
    rows: tuple[tuple[Spans, ...], ...]
    align: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Callout:
    kind: str
    title: Spans
    blocks: tuple[Block, ...]
    marker: str = ""


@dataclass(frozen=True, slots=True)
class CodeToken:
    kind: str
    text: str


@dataclass(frozen=True, slots=True)
class CodeBlock:
    language: str
    text: str
    tokens: tuple[CodeToken, ...]
    anchors: tuple[Anchor, ...] = ()


@dataclass(frozen=True, slots=True)
class Divider:
    pass


@dataclass(frozen=True, slots=True)
class Details:
    summary: Spans
    blocks: tuple[Block, ...]
    opened: bool


Block = Heading | Paragraph | ListBlock | Table | Callout | CodeBlock | Divider | Image | Details


@dataclass(frozen=True, slots=True)
class Content:
    blocks: tuple[Block, ...]
    broken_links: tuple[str, ...] = ()
    plain_paths: tuple[str, ...] = ()
    degraded: bool = False


@dataclass(frozen=True, slots=True)
class VersionEntry:
    version: str
    anchor: str
    prerelease: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class Document(Content):
    id: str
    language: str
    title: str
    path: Path
    toc: tuple[Anchor, ...] = ()
    versions: tuple[VersionEntry, ...] = ()


def inline_text(spans: Spans) -> str:
    return "".join(span.alt if isinstance(span, Image) else span.text for span in spans)


def block_text(block: Block) -> str:
    if isinstance(block, (Heading, Paragraph)):
        return inline_text(block.spans)
    if isinstance(block, CodeBlock):
        return block.text
    if isinstance(block, Image):
        return block.alt
    if isinstance(block, Table):
        return "\n".join(" ".join(inline_text(cell) for cell in row) for row in (block.header, *block.rows))
    if isinstance(block, ListBlock):
        return "\n".join(block_text(child) for item in block.items for child in item)
    if isinstance(block, (Callout, Details)):
        title = inline_text(block.title if isinstance(block, Callout) else block.summary)
        return "\n".join(filter(None, (title, *(block_text(child) for child in block.blocks))))
    return ""


def walk_blocks(blocks):
    """Depth-first reading order, including containers and their nested blocks."""
    for block in blocks:
        yield block
        if isinstance(block, ListBlock):
            for item in block.items:
                yield from walk_blocks(item)
        elif isinstance(block, (Callout, Details)):
            yield from walk_blocks(block.blocks)


def block_spans(block):
    """Inline runs belonging to this block itself (including table cells and captions)."""
    if isinstance(block, (Heading, Paragraph)):
        yield from block.spans
    elif isinstance(block, Table):
        for row in (block.header, *block.rows):
            for cell in row:
                yield from cell
    elif isinstance(block, Callout):
        yield from block.title
    elif isinstance(block, Details):
        yield from block.summary
    elif isinstance(block, Image):
        yield block
