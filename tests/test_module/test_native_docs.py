"""Content equality and link compatibility for the native help reader, without a window."""
from dataclasses import FrozenInstanceError
from html.parser import HTMLParser
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import parse_qs, urlsplit

import markdown
import pytest

from module.docs import reader
from module.docs.catalog import DOCUMENTS, RELATED, SIDEBAR, current_version, source_for, website_url
from module.docs.formats import release_for_anchor, split_faq, version_content
from module.docs.links import classify_link
from module.docs.markup import list_indentation
from module.docs.model import (Break, Callout, CodeBlock, Details, Divider, Heading, Image, Link,
                               ListBlock, Paragraph, SettingPath, Status, Table, Text, block_spans,
                               block_text, inline_text, walk_blocks)
from module.docs.paths import desktop_paths
from module.docs.reader import load_document, load_file, localized_anchor, outline, resolve_anchor
from module.docs.state import changelog_is_new, mark_changelog_seen
from module.docs.support import QQ_GROUP_URL, support_actions
from module.localization.languages import LANGS
from module.navigation import parse_link
from module.search.documents import heading_pairs
from module.settings_registry import SETTINGS, find_setting

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "tests/fixtures/docs/reader.md"


class VisibleHTML(HTMLParser):
    """Independent oracle: HTML text nodes and image alt text in DOM reading order."""
    def __init__(self):
        super().__init__()
        self.parts = []
        self.headings = []
        self.level = 0
        self.start = 0

    def handle_starttag(self, tag, attrs):
        if re.fullmatch(r"h[1-6]", tag):
            self.level, self.start = int(tag[1]), len(self.parts)
        elif tag == "img":
            self.parts.append(dict(attrs).get("alt", ""))

    def handle_data(self, text):
        self.parts.append(text)

    def handle_endtag(self, tag):
        if self.level and tag == f"h{self.level}":
            self.headings.append((self.level, " ".join("".join(self.parts[self.start:]).split())))
            self.level = 0


def literal(block):
    if isinstance(block, Callout):
        return block.marker + inline_text(block.title) + "".join(map(literal, block.blocks))
    if isinstance(block, ListBlock):
        return "".join(literal(b) for item in block.items for b in item)
    if isinstance(block, Details):
        return inline_text(block.summary) + "".join(map(literal, block.blocks))
    return block_text(block)


@pytest.mark.parametrize("manual", SIDEBAR, ids=lambda m: m.id)
@pytest.mark.parametrize("lang", LANGS)
def test_every_visible_character_and_phase3_anchor(manual, lang):
    doc = load_document(manual.id, lang)
    source = doc.path.read_text(encoding="utf-8-sig")
    assert doc.language == lang and doc.path.is_absolute() and doc.title and not doc.degraded
    assert not doc.broken_links
    # Structural whitespace is flexible; letters, punctuation, symbols and repeated text must match in order.
    oracle = VisibleHTML()
    oracle.feed(markdown.markdown(list_indentation(source), extensions=["tables", "fenced_code", "sane_lists"]))
    actual = "".join(map(literal, doc.blocks))
    if doc.id == "Changelog":
        assert len(doc.versions) == len(re.findall(r"^## ", source, re.M))
        for version in doc.versions:
            content = version_content(doc, version.anchor)
            assert not content.degraded and not content.broken_links
            actual += version.version + "".join(map(literal, content.blocks))
    compact = lambda text: re.sub(r"\s+", "", text)
    assert compact(actual) == compact("".join(oracle.parts))

    # Freeze the phase-3 rendering contract independently, including the old unfenced Workflow comments.
    legacy = VisibleHTML()
    extensions = (["tables", "fenced_code"] if doc.id == "Background" else
                  ["tables"] if doc.id in ("Tutorial", "Workflow", "TasksTable") else [])
    lines = source.splitlines()[2 if doc.id == "FAQ" else 1:]
    legacy.feed(markdown.markdown("\n".join(lines), extensions=extensions))
    counts, expected = {}, []
    for level, title in legacy.headings:
        base = re.sub(r"[^\w\s-]", "", title.casefold().strip()).replace(" ", "-")
        counts[base] = n = counts.get(base, 0) + 1
        if base:
            expected.append((level, title, base if n == 1 else f"{base}~{n}"))
    assert [(h.level, h.title, h.anchor) for h, _ in heading_pairs(doc.id, lang)] == expected
    if doc.id == "FAQ":
        faq = split_faq(doc)
        assert len(faq.questions) == len(doc.toc) == sum(level == 3 for level, _ in legacy.headings)
        assert faq.intro and not any(q.title.startswith(("Q:", "Q：")) for q in faq.questions)
        assert not any(block_text(q.blocks[0]).startswith(("A:", "A：")) for q in faq.questions)
    if lang != "zh_CN" and doc.id != "TasksTable":
        assert doc.blocks[1].kind == "declaration"


def test_catalog_language_fallback_and_help_actions(isolated_layout):
    assert [m.id for m in SIDEBAR] == ["Tutorial", "FAQ", "Background", "Workflow", "TasksTable", "Changelog"]
    assert SIDEBAR[4].name == "每日实训对照表"
    sidebar = Path("assets/docs/_sidebar.md").read_text(encoding="utf-8")
    for m in RELATED:
        assert f"[{m.name}](/assets/docs/{m.id}.md)" in sidebar
    for m in DOCUMENTS.values():
        assert parse_link("doc:" + m.id) == ("doc", m.id, "")
    assert source_for("Docker", "ko_KR").language == "zh_CN"
    assert load_document("Docker", "ko_KR").path.name == "Docker.md"
    assert website_url("Docker", language="ko_KR").endswith("/Docker")
    assert current_version() == Path("assets/config/version.txt").read_text(encoding="utf-8").strip()
    actions = support_actions()
    assert actions.faq == "doc:FAQ" and actions.qq_url == QQ_GROUP_URL and actions.log_folder == isolated_layout.root / "logs"


def test_sample_blocks_inline_marks_and_fallback():
    doc = load_file(SAMPLE)
    blocks = tuple(walk_blocks(doc.blocks))
    assert {type(b) for b in blocks} == {Heading, Paragraph, ListBlock, Table, Callout, CodeBlock, Divider, Image, Details}
    spans = [s for b in blocks for s in block_spans(b)]
    assert any(isinstance(s, Break) for s in spans)
    assert any(isinstance(s, Text) and s.bold and s.italic for s in spans)
    assert any(isinstance(s, Text) and s.strike for s in spans)
    assert any(isinstance(s, Text) and s.code and s.text == "Ctrl" for s in spans)
    assert any(isinstance(s, Text) and s.bold and s.link for s in spans)
    assert {b.kind for b in blocks if isinstance(b, Callout)} == {"info", "declaration", "tip", "warning", "danger"}
    tip = next(b for b in blocks if isinstance(b, Callout) and b.kind == "tip")
    assert inline_text(tip.title) == "想一边用电脑一边运行？" and "[!TIP]" not in block_text(tip)
    table = next(b for b in blocks if isinstance(b, Table))
    assert table.align == ("left", "center", "right", "default")
    assert {s.value for s in spans if isinstance(s, Status)} == {"yes", "no", "partial"}
    nested = next(b for b in blocks if isinstance(b, ListBlock))
    assert nested.ordered and nested.start == 3 and isinstance(nested.items[1][1], ListBlock)
    imgs = [s for s in spans if isinstance(s, Image)]
    assert any(i.path and i.path.is_absolute() and i.path.is_file() for i in imgs)
    assert any(i.url.startswith("https:") and i.path is None for i in imgs)
    assert any(i.url == "unavailable.png" and i.path is None for i in imgs)
    assert "未知行内标签里的字" in "".join(map(literal, doc.blocks))
    assert doc.broken_links == ("missing.md",)
    assert doc.plain_paths == ("「设置 → 旧版入口」",)
    for code in (b for b in blocks if isinstance(b, CodeBlock)):
        assert "".join(t.text for t in code.tokens) == code.text
        kinds = {t.kind for t in code.tokens}
        if code.language in ("text", "example"):
            assert kinds == {"plain"}
        else:
            assert {"keyword", "string"} <= kinds
    assert any(t.kind == "number" for b in blocks if isinstance(b, CodeBlock) for t in b.tokens)
    assert any(t.kind == "comment" for b in blocks if isinstance(b, CodeBlock) for t in b.tokens)
    assert doc.toc[-1].anchor.endswith("~2")
    with pytest.raises(FrozenInstanceError):
        table.align = ()


def test_table_status_annotations_keep_text_styles_and_links(tmp_path):
    path = tmp_path / "status.md"
    path.write_text("""| 支持情况 |
| --- |
| ✅（ADB） |
| ✔️ (Termux) |
| ❌（不支持） |
| ⚠️（部分支持） |
| **✅**（**[安卓版](https://example.org/android)**） |
| [✅（链接）](https://example.org/status) |
| 普通说明 ✅ |
""", encoding="utf-8")
    doc = load_file(path)
    assert not doc.degraded
    table = next(b for b in doc.blocks if isinstance(b, Table))
    cells = [row[0] for row in table.rows]
    assert [isinstance(cell[0], Status) for cell in cells] == [True] * 5 + [False] * 2
    assert [cell[0].value for cell in cells[:5]] == ["yes", "yes", "no", "partial", "yes"]
    assert [inline_text(cell) for cell in cells[:5]] == [
        "✅（ADB）", "✔️ (Termux)", "❌（不支持）", "⚠️（部分支持）", "✅（安卓版）"]
    assert any(isinstance(s, Text) and s.bold and s.link == Link("external", "https://example.org/android")
               for s in cells[4])
    assert cells[5][0].link == Link("external", "https://example.org/status")


@pytest.mark.parametrize("raw,kind,target", [
    ("/assets/docs/Android.md", "doc", "doc:Android"), ("./FAQ.md", "doc", "doc:FAQ"),
    ("FAQ_en_US.md", "doc", "doc:FAQ"), ("doc:FAQ", "doc", "doc:FAQ"),
    ("Tutorial.md#定时运行", "doc", "doc:Tutorial#定时运行"), ("#运行前准备", "doc", "doc:Tutorial#运行前准备"),
    ("#/assets/docs/Tutorial?id=副本类型-副本名称", "doc", "doc:Tutorial#副本类型--副本名称"),
    ("https://m7a.top/docs/#/assets/docs/Tutorial_en_US?id=before-you-run", "doc", "doc:Tutorial#运行前准备"),
    ("https://m7a.top/#/assets/docs/FAQ", "doc", "doc:FAQ"), ("#/assets/docs/Termux?id=gone", "doc", "doc:Termux"),
    ("setting:local_control_mode", "app", "setting:local_control_mode"), ("run:schedule", "app", "run:schedule"),
    ("task:power#instance_type", "app", "task:power#instance_type"), ("category:game", "app", "category:game"),
    ("page:help", "app", "page:help"), ("tool:screenshot", "app", "tool:screenshot"),
    ("https://example.org/help", "external", "https://example.org/help"), ("http://example.org", "external", "http://example.org"),
    ("mailto:a@example.org", "external", "mailto:a@example.org"),
    ("missing.md", "", ""), ("FAQ.md#absent", "", ""), ("#missing", "", ""), ("file:///tmp/test", "", ""),
    ("javascript:void(0)", "", ""), ("setting:unknown", "", ""), ("//example.org/x", "", ""),
    ("https://m7a.top/docs/#/assets/docs/Unknown", "", ""),
])
def test_classification(raw, kind, target):
    assert classify_link(raw, source_for("Tutorial", "zh_CN")) == (Link(kind, target) if kind else None)


@pytest.mark.parametrize("lang", LANGS)
def test_registry_doc_links_and_canonical_button_labels(lang):
    for link in {s.doc for s in SETTINGS if s.doc}:
        _, name, anchor = parse_link(link)
        translated = localized_anchor(name, anchor, lang)
        assert translated and translated in {h.anchor for h in outline(source_for(name, lang))}
    assert localized_anchor("Tutorial", "definitely-absent", lang) == ""
    doc = load_document("Tutorial", lang)
    paths = [s for b in walk_blocks(doc.blocks) for s in block_spans(b) if isinstance(s, SettingPath)]
    if lang in ("zh_CN", "zh_TW"):
        assert len(paths) == 30
        assert {"category:run_mode", "setting:game_path", "setting:refresh_hour",
                "run:schedule", "setting:setup_wizard"} <= {s.target for s in paths}
    for s in paths:
        kind, name, anchor = parse_link(s.target)
        if kind in ("setting", "task") and (kind == "setting" or anchor):
            item = find_setting(anchor or name)
            assert item.title == s.labels[-1] and item.link == s.target
        if s.target != "run:schedule":
            assert s.labels in desktop_paths()
    if lang == "zh_CN":
        assert any(s.labels == ("设置", "运行方式", "本地客户端", "本地操作模式") for s in paths)


def test_docsify_duplicates_current_language_and_round_trip(tmp_path, monkeypatch):
    path = tmp_path / "assets/docs/Tutorial.md"
    path.parent.mkdir(parents=True)
    path.write_text("# Title\n\n## 4. 中文（ABC） / word!\n\n## 4. 中文（ABC） / word!", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    doc = load_document("Tutorial")
    for i, h in enumerate(doc.toc):
        url = website_url(doc.id, h.anchor)
        web = parse_qs(urlsplit(urlsplit(url).fragment).query)["id"][0]
        assert web == "_4-中文（abc）-word" + ("-1" if i else "")
        assert classify_link(url, source_for(doc.id)).target == f"doc:Tutorial#{h.anchor}"
    assert doc.toc[-1].anchor.endswith("~2")


def test_version_directory_is_lazy_and_preserves_global_subheading_ids(tmp_path, monkeypatch):
    p = tmp_path / "Changelog.md"
    p.write_text("# 记录\n\n## v2.0-beta\n\n### 修复\n\n```text\n## example\n```\n\n## v1\n\n### 修复\n\n内容", encoding="utf-8")
    from module.docs import formats
    calls = []
    original = formats.prepare_article
    def counted(*args, **kwargs):
        calls.append(args[1])
        return original(*args, **kwargs)
    monkeypatch.setattr(formats, "prepare_article", counted)
    doc = load_file(p, doc_id="Changelog")
    assert not calls and [v.prerelease for v in doc.versions] == [True, False]
    assert "example" not in repr(doc.blocks) and [h.title for h in doc.toc] == ["v2.0-beta", "v1"]
    last = doc.versions[-1]
    assert release_for_anchor(doc, "修复~2") == last
    content = version_content(doc, last.anchor)
    assert len(calls) == 1 and "example" not in calls[0]
    assert content.blocks[0].anchor == "修复~2"
    assert version_content(doc, last) is version_content(doc, last.version) is content and len(calls) == 1
    assert version_content(doc, "missing") is None


def test_file_changes_failure_fallback_and_log(tmp_path, monkeypatch, caplog):
    p = tmp_path / "local.md"
    p.write_text("# Header\n\n## First", encoding="utf-8")
    doc = load_file(p)
    assert load_file(p) is doc
    p.write_text("# Header\n\n## Second heading", encoding="utf-8")
    assert load_file(p).toc[0].anchor == "second-heading"
    p.write_text("# 再次变化\n\n完整的 **原文**", encoding="utf-8")
    monkeypatch.setattr(reader.Builder, "content", lambda self: 1 / 0)
    failed = load_file(p)
    assert failed.degraded and block_text(failed.blocks[0]) == p.read_text(encoding="utf-8")
    assert load_file(p) is failed
    assert len([r for r in caplog.records if str(p) in r.message]) == 1
    assert load_file(tmp_path / "missing.md").degraded


@pytest.mark.parametrize("prefix,kind", [("Tip:", "tip"), ("重要：", "danger"), ("警告：", "warning"),
                                         ("危険：", "danger"), ("참고:", "info"), ("[!WARNING]", "warning")])
def test_callout_keywords_preserve_styling(tmp_path, prefix, kind):
    path = tmp_path / "s.md"
    path.write_text(f"# Test\n\n> {prefix} **Title!** Normal", encoding="utf-8")
    callout = load_file(path).blocks[-1]
    assert callout.kind == kind and inline_text(callout.title) == "Title!"
    assert block_text(callout.blocks[0]).strip() == "Normal"


def test_seen_version_install_upgrade_rollback_and_io_failure(tmp_path):
    file = tmp_path / "state/help.sqlite3"
    assert not changelog_is_new("v1", file) and file.is_file()
    assert changelog_is_new("v2", file) and changelog_is_new("v2", file)
    assert mark_changelog_seen("v2", file) and not changelog_is_new("v2", file)
    assert mark_changelog_seen("v1", file) and not changelog_is_new("v2", file)
    assert not changelog_is_new("v2", file / "bad") and not mark_changelog_seen("v2", file / "bad")
    file.write_bytes(b"damaged")
    assert not changelog_is_new("v2", file) and not mark_changelog_seen("v2", file)


def test_traditional_vocabulary_and_no_optional_renderer_dependencies():
    from opencc import OpenCC
    from module.docs.traditional import TRADITIONAL
    convert = OpenCC("s2twp").convert
    assert all(convert(word) == value for word, value in TRADITIONAL.items())
    subprocess.run([sys.executable, "-B", "-c", """
import sys
sys.modules['pygments'] = None
from module.docs.reader import load_document
assert not load_document('Tutorial').degraded
assert not {'PySide6', 'qfluentwidgets', 'module.config'} & sys.modules.keys()
"""], check=True)


def test_restore_view_across_two_translations_with_different_revisions():
    chinese = "使用后备开拓力--使用燃料"
    traditional = localized_anchor("Tutorial", chinese, "zh_TW")
    english = localized_anchor("Tutorial", chinese, "en_US")
    assert traditional and english and traditional != english
    assert resolve_anchor(source_for("Tutorial", "en_US"), traditional, written_language="zh_TW") == english
    assert resolve_anchor(source_for("Tutorial", "zh_TW"), english, written_language="en_US") == traditional


def test_bare_breadcrumb_keeps_surrounding_prose_and_unknown_submenu(tmp_path):
    path = tmp_path / "menus.md"
    path.write_text("# Menu\n\n可以在设置 → 关于中查看版本。\n\n设置 → 关于 → 新菜单。", encoding="utf-8")
    doc = load_file(path)
    assert [s.text for s in doc.blocks[1].spans] == ["可以在", "设置 → 关于", "中查看版本。"]
    assert doc.blocks[1].spans[1].target == "category:about"
    assert doc.plain_paths == ("设置 → 关于 → 新菜单",)
