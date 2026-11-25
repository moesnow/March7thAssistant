from statistics import median
from time import perf_counter

from module.content_samples import SampleConfig
from module.docs.model import SettingPath, block_spans, walk_blocks
from module.docs.reader import load_file
from module.docs.search import search_help
from module.search import SearchIndex


def test_body_search_returns_section_ranges_and_title_priority():
    result = search_help("ＲＴＳＳ ＯＣＲ", "zh_CN")
    assert not result.suggestions
    faq = next(h for h in result.hits if h.section.doc_id == "FAQ")
    assert faq.section.anchor and "常见问题 › " in faq.section.location
    assert any(faq.snippet[a:b].lower() == "rtss" for a, b in faq.matches)
    assert search_help("命令行启动").hits[0].section.anchor == "命令行启动"
    assert search_help("ｉｎｓｔａｌｌａｔｉｏｎ", "en_US").hits[0].section.title == "Download and Installation"
    assert search_help("不起作用的不存在词9281").suggestions == SearchIndex.suggestions()
    assert not search_help(" ").hits
    assert any(h.section.doc_id == "TasksTable" and not h.section.anchor for h in search_help("派遣委托").hits)
    assert any(h.section.doc_id == "Changelog" and h.section.anchor for h in search_help("Topics").hits)
    assert any("后台" in h.section.title for h in search_help("不占鼠标").hits)


def test_section_index_refreshes_while_same_global_search_is_open(tmp_path, monkeypatch):
    docs = tmp_path / "assets/docs"
    docs.mkdir(parents=True)
    for name in ("Tutorial", "Background", "FAQ", "Workflow", "TasksTable", "Changelog"):
        (docs / (name + ".md")).write_text(f"# {name}\n\n## Topic\n\nExample", encoding="utf-8")
    config = SampleConfig()
    monkeypatch.chdir(tmp_path)
    index = SearchIndex(config)
    assert not index.query("straße")
    (docs / "Tutorial.md").write_text("# Tutorial\n\n## Topic\n\nＡ Straße and cafe\u0301. ｶﾞｲﾄﾞ", encoding="utf-8")
    hits = search_help("ｓｔｒａｓｓｅ café").hits
    assert [hits[0].snippet[a:b] for a, b in hits[0].matches] == ["Straße", "cafe\u0301"]
    kana = search_help("ガイド").hits[0]
    assert [kana.snippet[a:b] for a, b in kana.matches] == ["ｶﾞｲﾄﾞ"]
    assert index.query("strasse", kinds={"doc"})[0].link == "doc:Tutorial#topic"


def test_global_body_weight_and_prepared_query_latency():
    index = SearchIndex(SampleConfig())
    index.prepare()
    assert any(h.link.startswith("doc:FAQ#") for h in index.query("RTSS OCR", kinds={"doc"}))
    assert index.query("命令行启动", kinds={"doc"})[0].name == "命令行启动"
    samples = []
    for _ in range(8):
        for query in ("后台", "ＲＴＳＳ", "清体力", "不占鼠标", "RTSS OCR", "不存在9281"):
            start = perf_counter()
            index.query(query)
            samples.append(perf_counter() - start)
    assert median(samples) < .010


def test_translated_paths_use_catalog_names_and_keep_explicit_links(tmp_path, monkeypatch, compiled_locales):
    from module import localization
    from module.docs import paths
    monkeypatch.setattr(localization, "_locale_dir", str(compiled_locales))
    monkeypatch.setattr(localization, "_lang_catalogs_cache", {})
    paths._label.cache_clear()
    paths._localized.cache_clear()
    try:
        canonical = ("设置", "关于", "社区与工具", "AI 助手")
        for lang in ("en_US", "ja_JP", "ko_KR"):
            labels = [localization.translations_of(k)[lang] for k in canonical]
            text = " → ".join((labels[0], labels[1], labels[-1]))
            full = " → ".join(labels)
            file = tmp_path / f"{lang}.md"
            file.write_text(f'# Title\n\n"{text}" [link](https://example.org/) `{full}`', encoding="utf-8")
            doc = load_file(file, language=lang)
            spans = [s for b in walk_blocks(doc.blocks) for s in block_spans(b)]
            buttons = [s for s in spans if isinstance(s, SettingPath)]
            assert len(buttons) == 2 and all(s.target == "setting:agentPromptCard" for s in buttons)
            assert buttons[0].text == f'"{text}"'
            assert all(button.labels == canonical for button in buttons)
            assert any(getattr(s, "link", None) for s in spans)
    finally:
        paths._label.cache_clear()
        paths._localized.cache_clear()


def test_setup_wizard_is_reachable_from_help_and_settings_search():
    from urllib.parse import unquote
    section = "doc:Tutorial#首次配置向导"
    assert any(unquote(hit.section.link) == section for hit in search_help("首次配置向导").hits)
    index = SearchIndex(SampleConfig())
    hits = index.query("向导", settings_only=True)
    assert [hit.link for hit in hits] == ["setting:setup_wizard"]
    assert any(unquote(hit.link) == section for hit in index.query("向导"))
