"""One searchable section per article H2/H3, FAQ question or release. No Qt or user configuration."""
from dataclasses import dataclass
from functools import lru_cache
from html import unescape
import re
import unicodedata
from urllib.parse import quote

from module.localization import get_current_language
from module.search.terms import normalize, query_terms, suggestions
from .anchors import source_text
from .catalog import SIDEBAR, source_for
from .formats import releases, split_faq
from .model import Heading, block_text
from .reader import document_for


@dataclass(frozen=True, slots=True)
class Section:
    doc_id: str
    anchor: str
    title: str
    location: str
    body: str

    @property
    def link(self):
        return "doc:" + self.doc_id + ("#" + quote(self.anchor) if self.anchor else "")


@dataclass(frozen=True, slots=True)
class Hit:
    section: Section
    snippet: str
    matches: tuple[tuple[int, int], ...]
    score: int


@dataclass(frozen=True, slots=True)
class HelpResults:
    hits: tuple[Hit, ...]
    suggestions: tuple[str, ...]


def signatures(language=None):
    sources = (source_for(m.id, language) for m in SIDEBAR)
    return tuple((s, s.stamp) for s in sources)


_RELEASE_MARKUP = re.compile(r"<!--[\s\S]*?-->|!?\[([^\]\n]*)\]\((?:[^()\n]|\([^()\n]*\))*\)|"
                             r"^(?:#{1,6}\s+|[-*+]\s+|>\s?)|(\*\*|~~|`+)", re.M)


def _release_text(markdown):
    # Release indexing only needs displayed words; leave the expensive block/colour models lazy.
    return unescape(_RELEASE_MARKUP.sub(lambda m: m[1] or "", markdown))


def _body(blocks):
    return " ".join(" ".join(block_text(b) for b in blocks).split())


@lru_cache(maxsize=48)
def sections(source, stamp):
    doc = document_for(source)
    def section(anchor, trail, body):
        return Section(doc.id, anchor, trail[-1], " › ".join(trail), " ".join(body.split()))
    if doc.id == "FAQ":
        faq = split_faq(doc)
        return (section("", (doc.title,), _body(faq.intro)), *(
            section(q.anchor, (doc.title, q.title), _body(q.blocks)) for q in faq.questions))
    if doc.id == "Changelog" and not doc.degraded:
        index = releases(source, stamp)
        text = source_text(source, stamp)
        return (section("", (doc.title,), _body(doc.blocks[1:])), *(
            section(r.entry.anchor, (doc.title, r.entry.version), _release_text(text[r.start:r.end]))
            for r in index.entries.values()))
    rows, parents, body = [], [], []
    anchor, trail = "", (doc.title,)
    for block in doc.blocks:
        if isinstance(block, Heading) and block.level == 1 and not rows and not body:
            continue
        if isinstance(block, Heading) and block.level in (2, 3):
            rows.append(section(anchor, trail, _body(body)))
            while parents and parents[-1].level >= block.level:
                parents.pop()
            parents.append(block)
            anchor, trail, body = block.anchor, (doc.title, *(p.text for p in parents)), []
        else:
            body.append(block)
    rows.append(section(anchor, trail, _body(body)))
    return tuple(rows)


@lru_cache(maxsize=8)
def _index(files):
    return tuple((s, normalize(s.title), normalize(s.body)) for source, stamp in files for s in sections(source, stamp))


def _original_offsets(text):
    """Map NFKC/casefold expansions and combining marks back to a slice of the displayed text."""
    offsets = []
    space = False
    start = 0
    while start < len(text):
        end = start + 1
        while end < len(text):
            first = unicodedata.normalize("NFKD", text[end])[0]
            # Half-width kana + voiced mark and decomposed Hangul can form one displayed character.
            if not unicodedata.combining(first):
                if not 0x1160 <= ord(first) <= 0x11ff:
                    break
                last = unicodedata.normalize("NFKC", text[start:end])[-1]
                if unicodedata.normalize("NFC", last + first) == last + first:
                    break
            end += 1
        part = unicodedata.normalize("NFKC", text[start:end]).casefold()
        for char in part:
            if char.isspace():
                if not offsets:
                    continue
                if space:
                    offsets[-1] = (offsets[-1][0], end)
                    continue
                space = True
            else:
                space = False
            offsets.append((start, end))
        start = end
    return offsets


def _snippet(text, normalized, terms, width=120):
    # Bodies already contain single spaces. Map after matching so the UI can slice the original Unicode.
    offsets = _original_offsets(text)
    ranges = []
    for word, aliases in terms:
        for term in (word, *aliases):
            pos = normalized.find(term)
            while pos >= 0:
                end = pos + len(term)
                if end <= len(offsets):
                    ranges.append((offsets[pos][0], offsets[end-1][1]))
                pos = normalized.find(term, end)
    ranges.sort()
    start = max(0, ranges[0][0] - 32) if ranges else 0
    end = min(len(text), max(start + width, ranges[0][1] if ranges else 0))
    offset = int(start > 0) - start
    visible = []
    for a, b in ranges:
        if start <= a < b <= end:
            if visible and a + offset <= visible[-1][1]:
                visible[-1] = (visible[-1][0], max(visible[-1][1], b + offset))
            else:
                visible.append((a + offset, b + offset))
    return ("…" if start else "") + text[start:end] + ("…" if end < len(text) else ""), tuple(visible)


def search_help(text, language=None, *, limit=24):
    language = language or get_current_language()
    terms = query_terms(text, language)
    if not terms or limit <= 0:
        return HelpResults((), ())
    found = []
    for section, title, body in _index(signatures(language)):
        score, title_hits = 0, 0
        for word, aliases in terms:
            if word in title:
                score += 8 if word == title else 6
                title_hits += 1
            elif any(a in title for a in aliases):
                score += 4
                title_hits += 1
            elif word in body:
                score += 2
            elif any(a in body for a in aliases):
                score += 1
            else:
                break
        else:
            found.append((title_hits * (10 * len(terms)) + score, section, title, body))
    found.sort(key=lambda row: -row[0])
    hits = []
    for score, section, title, body in found[:limit]:
        use_body = any(v in body for word, aliases in terms for v in (word, *aliases))
        snippet, matches = _snippet(section.body if use_body else section.title, body if use_body else title, terms)
        hits.append(Hit(section, snippet, matches, score))
    return HelpResults(tuple(hits), () if hits else suggestions(language))
