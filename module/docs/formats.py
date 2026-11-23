"""Question/answer sections and a file-offset directory for long release histories."""
from dataclasses import dataclass, replace
from functools import lru_cache
import re

from utils.version import Version

from .anchors import AnchorNames, prepare_article, source_text
from .blocks import Builder, span_slice
from .catalog import Source
from .markup import node_text, render_tree
from .model import Anchor, Block, Heading, Paragraph, VersionEntry, inline_text

_Q = re.compile(r"^\s*(?:Q|Question|问题|問題|質問|질문|문)\s*[:：]\s*", re.I)
_A = re.compile(r"^\s*(?:A|Answer|回答|答案|答え|答|답변|답)\s*[:：]\s*", re.I)


@dataclass(frozen=True, slots=True)
class Question:
    title: str
    anchor: str
    blocks: tuple[Block, ...]


@dataclass(frozen=True, slots=True)
class FAQ:
    intro: tuple[Block, ...]
    questions: tuple[Question, ...]


def question_title(text):
    return _Q.sub("", text, count=1)


def split_faq(document):
    intro, questions, answer = [], [], []
    heading = None
    for block in document.blocks:
        if isinstance(block, Heading) and block.level == 1 and not intro and heading is None:
            continue
        if isinstance(block, Heading) and block.level == 3:
            if heading is not None:
                questions.append(Question(question_title(heading.text), heading.anchor, tuple(answer)))
            heading, answer = block, []
        elif heading is None:
            intro.append(block)
        else:
            if not answer and isinstance(block, Paragraph) and (m := _A.match(inline_text(block.spans))):
                block = Paragraph(span_slice(block.spans, m.end()))
            answer.append(block)
    if heading is not None:
        questions.append(Question(question_title(heading.text), heading.anchor, tuple(answer)))
    return FAQ(tuple(intro), tuple(questions))


@dataclass(frozen=True, slots=True)
class Release:
    entry: VersionEntry
    heading: Anchor
    start: int
    end: int


@dataclass
class ReleaseFile:
    intro: str
    entries: dict[str, Release]


_FENCE = r"^(?P<fence>`{3,}|~{3,})(?P<info>[^\n]*)$"
_VERSION_LINES = re.compile(_FENCE + r"|^##[ \t]+(?P<title>[^\n]+)$", re.M)
_ALL_HEADINGS = re.compile(_FENCE + r"|^(?P<hash>#{1,6})[ \t]+(?P<title>[^\n]+)$", re.M)


def _headings(text, pattern):
    fence = ""
    for match in pattern.finditer(text):
        mark = match["fence"]
        if mark:
            if not fence:
                fence = mark
            elif mark.startswith(fence) and not match["info"].strip():
                fence = ""
        elif not fence:
            yield match


def _title(raw):
    raw = re.sub(r"[ \t]+#+[ \t]*$", "", raw).strip()
    if any(char in raw for char in "*`[<&~_"):
        return node_text(render_tree("# " + raw)).strip()
    return raw


@lru_cache(maxsize=12)
def releases(source, stamp):
    text = source_text(source, stamp)
    matches = list(_headings(text, _VERSION_LINES))
    entries = {}
    names = AnchorNames()
    for i, match in enumerate(matches):
        title = _title(match["title"])
        heading = names.add(2, title)
        try:
            prerelease = Version(title, strict=True).is_prerelease
        except ValueError:
            prerelease = False
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        entry = VersionEntry(title, heading.anchor, prerelease)
        entries[entry.anchor] = Release(entry, heading, match.end(), end)
    return ReleaseFile(text[:matches[0].start()] if matches else text, entries)


@lru_cache(maxsize=12)
def release_headings(source, stamp):
    text = source_text(source, stamp)
    names = AnchorNames()
    result = []
    for match in _headings(text, _ALL_HEADINGS):
        level = len(match["hash"])
        result.append(names.add(level, _title(match["title"]), page_title=not result and level == 1))
    return tuple(result)


@lru_cache(maxsize=12)
def _release_sections(source, stamp):
    owners, children = {}, {}
    owner = ""
    for h in release_headings(source, stamp):
        if h.level == 2:
            owner = h.anchor
            children[owner] = []
        elif owner:
            children[owner].append(h)
        if owner:
            owners[h.anchor] = owner
    return owners, children


def release_for_anchor(document, anchor):
    source = Source(document.id, document.language, document.path)
    if document.degraded or document.id != "Changelog":
        return None
    try:
        stamp = source.stamp
        owner = _release_sections(source, stamp)[0].get(anchor)
        release = releases(source, stamp).entries.get(owner)
        return release.entry if release else None
    except (OSError, ValueError):
        return None


def version_content(document, version):
    source = Source(document.id, document.language, document.path)
    if source.id != "Changelog":
        return None
    key = version.anchor if isinstance(version, VersionEntry) else version
    entry = next((v for v in document.versions if key in (v.anchor, v.version)), None)
    return _version_content(source, source.stamp, entry.anchor) if entry else None


@lru_cache(maxsize=96)
def _version_content(source, stamp, version):
    from .reader import fallback
    text = ""
    try:
        index = releases(source, stamp)
        release = index.entries.get(version)
        if not release:
            return None
        text = source_text(source, stamp)[release.start:release.end]
        supplied = _release_sections(source, stamp)[1][release.entry.anchor]
        article = prepare_article(source, text, supplied, declaration=False)
        return Builder(source, article, declaration=False).content()
    except Exception as exc:
        return fallback(source, text, exc)
