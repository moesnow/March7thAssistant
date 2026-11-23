"""Help headings and excerpts for global search, paired with their Simplified Chinese titles."""
from dataclasses import dataclass
from functools import lru_cache

from module.docs.catalog import source_for
from module.docs.model import Heading as BlockHeading, block_text
from module.docs.reader import _aligned, document_for, outline


@dataclass(frozen=True, slots=True)
class Heading:
    level: int
    title: str
    anchor: str
    excerpt: str = ""


@lru_cache(maxsize=48)
def _rows(source, stamp):
    from module.docs.search import sections
    headings = outline(source)
    if headings and headings[0].level == 1:
        headings = headings[1:]
    bodies = {s.anchor: s.body for s in sections(source, stamp)}
    if source.id != "Changelog":
        current = ""
        for block in document_for(source).blocks:
            if isinstance(block, BlockHeading):
                current = block.anchor
            elif current and not bodies.get(current):
                bodies[current] = " ".join(block_text(block).split())
        for i in range(len(headings) - 2, -1, -1):
            row, following = headings[i:i+2]
            if not bodies.get(row.anchor) and following.level > row.level:
                bodies[row.anchor] = bodies.get(following.anchor) or following.title
    rows = []
    for h in headings:
        if h.anchor:
            excerpt = bodies.get(h.anchor, "")
            rows.append(Heading(h.level, h.title, h.anchor, excerpt if len(excerpt) <= 110 else excerpt[:109] + "…"))
    return tuple(rows)


@lru_cache(maxsize=48)
def _pairs(local, local_stamp, original, original_stamp):
    translated = {h.anchor: src.title for h, src in _aligned(local.id, outline(local), outline(original))}
    return tuple((row, translated.get(row.anchor, row.title)) for row in _rows(local, local_stamp))


def heading_pairs(name, language=None):
    local, original = source_for(name, language), source_for(name, "zh_CN")
    return _pairs(local, local.stamp, original, original.stamp)
