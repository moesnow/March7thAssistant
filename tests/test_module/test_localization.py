# coding:utf-8
"""module.localization（gettext 后端）测试：合成目录，不读取真实译文内容。"""
import gettext

import polib
import pytest

import module.localization as loc
from module.localization import (
    PLURAL_SUFFIX,
    get_current_language,
    tr,
    trc,
    tn,
)


@pytest.fixture(scope="module", autouse=True)
def restore_language():
    original = get_current_language()
    yield
    loc.load_language(original)


def _build(tmp_path, lang, entries=None, plurals=None, contexts=None, nplurals=2):
    """构造并加载一个合成 gettext 目录（键值均为 ASCII 占位串）。"""
    po = polib.POFile()
    po.metadata = {
        "Language": lang,
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=UTF-8",
        "Plural-Forms": f"nplurals={nplurals}; plural={'(n != 1)' if nplurals == 2 else '0'};",
    }
    for k, v in (entries or {}).items():
        po.append(polib.POEntry(msgid=k, msgstr=v))
    for k, forms in (plurals or {}).items():
        e = polib.POEntry(msgid=k, msgid_plural=k + PLURAL_SUFFIX, msgstr="")
        e.msgstr_plural = dict(enumerate(forms))
        po.append(e)
    for (ctx, k), v in (contexts or {}).items():
        po.append(polib.POEntry(msgid=k, msgstr=v, msgctxt=ctx))
    d = tmp_path / lang / "LC_MESSAGES"
    d.mkdir(parents=True, exist_ok=True)
    po.save(str(d / "march7th.po"))
    po.save_as_mofile(str(d / "march7th.mo"))
    return gettext.translation("march7th", str(tmp_path), languages=[lang])


@pytest.fixture()
def env(monkeypatch):
    """把模块状态指向合成目录/空目录。"""

    def set_lang(code, translation=None, fallback=None):
        monkeypatch.setattr(loc, "_current_lang", code)
        monkeypatch.setattr(loc, "_translation", translation or gettext.NullTranslations())
        monkeypatch.setattr(loc, "_fallback_translation", fallback or gettext.NullTranslations())
        monkeypatch.setattr(loc, "_missing_logged", set())

    return set_lang


class TestTr:
    def test_empty_string(self, env):
        env("en_US")
        assert tr("") == ""

    def test_none(self, env):
        env("en_US")
        assert tr(None) is None

    def test_translation_found(self, tmp_path, env):
        trans = _build(tmp_path, "en_US", entries={"s1": "t1"})
        env("en_US", translation=trans)
        assert tr("s1") == "t1"

    def test_identity_translation_is_hit(self, tmp_path, env):
        # msgstr == msgid 视为已翻译命中（同文翻译）
        trans = _build(tmp_path, "zh_CN", entries={"s1": "s1"}, nplurals=1)
        env("zh_CN", translation=trans)
        assert tr("s1") == "s1"

    def test_missing_returns_source_no_marker(self, tmp_path, env):
        trans = _build(tmp_path, "en_US", entries={"s1": "t1"})
        env("en_US", translation=trans)
        result = tr("missing-key")
        assert result == "missing-key"
        assert "[" not in result

    def test_zh_tw_s2t_fallback(self, env, monkeypatch):
        env("zh_TW")
        monkeypatch.setattr(loc, "_s2t", lambda t: f"tw:{t}")
        assert tr("abc") == "tw:abc"

    def test_zh_tw_same_script_text_keeps_chinese(self, tmp_path, env):
        """简繁同形的文案（转换后没变化）必须保留中文，不能回退到英文。"""
        fallback = _build(tmp_path, "en_US", entries={"最高置信度": "Best confidence"})
        env("zh_TW", fallback=fallback)
        assert tr("最高置信度") == "最高置信度"

    def test_zh_tw_converted_text_used(self, tmp_path, env):
        """含简体专用字的文案应返回简转繁结果（台湾用语 s2twp），而不是英文回退。"""
        fallback = _build(tmp_path, "en_US", entries={"设置": "Settings"})
        env("zh_TW", fallback=fallback)
        assert tr("设置") == "設定"

    def test_s2t_unavailable_falls_through_to_en(self, tmp_path, env, monkeypatch):
        """OpenCC 不可用时（_s2t 返回 None）应继续走 en_US 回退。"""
        import opencc

        def boom(*_a, **_k):
            raise RuntimeError("opencc 不可用")

        monkeypatch.setattr(opencc, "OpenCC", boom)
        monkeypatch.setattr(loc, "_s2t_converter", None)  # 模拟首次构造
        fallback = _build(tmp_path, "en_US", entries={"设置": "Settings"})
        env("zh_TW", fallback=fallback)
        assert tr("设置") == "Settings"

    def test_s2t_reuses_converter_instance(self, env, monkeypatch):
        """OpenCC 实例构造/析构开销在百毫秒级，缺译回退必须复用同一实例，不能每次新建。"""
        import opencc

        created = []
        real_opencc = opencc.OpenCC

        def counting_factory(*args, **kwargs):
            created.append(1)
            return real_opencc(*args, **kwargs)

        monkeypatch.setattr(opencc, "OpenCC", counting_factory)
        monkeypatch.setattr(loc, "_s2t_converter", None)  # 模拟首次构造
        env("zh_TW")
        assert tr("设置") == "設定"
        assert tr("另一个需要转换的文案") != ""
        assert len(created) == 1

    def test_en_us_fallback_catalog(self, tmp_path, env):
        trans = _build(tmp_path, "ja_JP", entries={"s1": "ja"})
        fallback = _build(tmp_path, "en_US", entries={"s2": "en2"})
        env("ja_JP", translation=trans, fallback=fallback)
        assert tr("s2") == "en2"

    def test_no_file_writes_on_missing(self, env, monkeypatch):
        env("zh_CN")

        def boom(*a, **k):
            raise AssertionError("缺失翻译不应写文件")

        monkeypatch.setattr("builtins.open", boom)
        assert tr("missing-key-2") == "missing-key-2"


class TestTrc:
    def test_context_hit(self, tmp_path, env):
        trans = _build(tmp_path, "en_US", entries={"run": "RunBtn"}, contexts={("state", "run"): "Running"})
        env("en_US", translation=trans)
        assert trc("state", "run") == "Running"
        assert trc("button", "run") == "RunBtn"  # 无上下文条目回退 tr

    def test_context_miss_falls_back_to_source(self, env):
        env("en_US")
        assert trc("ctx", "text") == "text"


class TestTn:
    def test_two_forms(self, tmp_path, env):
        trans = _build(tmp_path, "en_US", plurals={"k1": ("one", "many")})
        env("en_US", translation=trans)
        assert tn("k1", 1) == "one"
        assert tn("k1", 5) == "many"

    def test_single_form_language(self, tmp_path, env):
        trans = _build(tmp_path, "zh_CN", plurals={"k1": ("same",)}, nplurals=1)
        env("zh_CN", translation=trans)
        assert tn("k1", 1) == "same"
        assert tn("k1", 5) == "same"

    def test_count_auto_format(self, tmp_path, env):
        trans = _build(tmp_path, "en_US", plurals={"x {count} y": ("a {count} b", "c {count} d")})
        env("en_US", translation=trans)
        assert tn("x {count} y", 1) == "a 1 b"
        assert tn("x {count} y", 5) == "c 5 d"

    def test_missing_returns_formatted_source(self, env):
        env("en_US")
        assert tn("only {count} left", 2) == "only 2 left"


class TestLoadLanguage:
    @pytest.fixture(autouse=True)
    def _restore_language_state(self, monkeypatch):
        """load_language() 直接改写模块状态；先登记原值，用例结束后还原，避免测试语言漏给后续用例。"""
        for name in ("_current_lang", "_translation", "_fallback_translation", "_missing_logged",
                     "_catalog_logged", "_pending_catalog_notices"):
            monkeypatch.setattr(loc, name, getattr(loc, name))

    def test_load_from_locale_dir(self, tmp_path, monkeypatch, env):
        _build(tmp_path, "xx_XX", entries={"s1": "tX"})
        monkeypatch.setattr(loc, "_locale_dir", str(tmp_path))
        loc.load_language("xx_XX")
        monkeypatch.setattr(loc, "_missing_logged", set())
        assert get_current_language() == "xx_XX"
        assert tr("s1") == "tX"

    def test_missing_catalog_falls_back_to_null(self, monkeypatch, env):
        monkeypatch.setattr(loc, "_locale_dir", "不存在的目录")
        loc.load_language("yy_YY")
        monkeypatch.setattr(loc, "_missing_logged", set())
        assert get_current_language() == "yy_YY"
        assert tr("any") == "any"

    @staticmethod
    def _rewrite_po(tmp_path, lang, entries, *, po_mtime, mo_mtime=None):
        """改写 .po 并固定 .po/.mo 的修改时间（不依赖文件系统时间精度）。"""
        import os
        d = tmp_path / lang / "LC_MESSAGES"
        po = polib.POFile()
        po.metadata = {"Language": lang, "Content-Type": "text/plain; charset=UTF-8"}
        for k, v in entries.items():
            po.append(polib.POEntry(msgid=k, msgstr=v))
        po.save(str(d / "march7th.po"))
        os.utime(d / "march7th.po", (po_mtime, po_mtime))
        if mo_mtime is not None:
            os.utime(d / "march7th.mo", (mo_mtime, mo_mtime))

    def _load(self, monkeypatch, tmp_path, lang):
        monkeypatch.setattr(loc, "_locale_dir", str(tmp_path))
        monkeypatch.setattr(loc, "_catalog_logged", set())
        monkeypatch.setattr(loc, "_pending_catalog_notices", {})
        loc.load_language(lang)
        monkeypatch.setattr(loc, "_missing_logged", set())

    @staticmethod
    def _fake_logger(monkeypatch):
        import sys
        import types
        from unittest.mock import Mock
        fake = types.ModuleType("module.logger")
        fake.log = Mock()
        monkeypatch.setitem(sys.modules, "module.logger", fake)
        return fake.log

    def test_notice_before_logger_is_written_once_logger_is_ready(self, tmp_path, monkeypatch, env):
        import sys
        _build(tmp_path, "xx_XX", entries={"s1": "tX"})
        (tmp_path / "xx_XX" / "LC_MESSAGES" / "march7th.mo").unlink()
        monkeypatch.delitem(sys.modules, "module.logger", raising=False)  # app.py：先加载语言，后导入日志
        self._load(monkeypatch, tmp_path, "xx_XX")
        assert tr("s1") == "tX"
        log = self._fake_logger(monkeypatch)
        loc.flush_catalog_notices()
        loc.load_language("xx_XX")
        loc.flush_catalog_notices()
        log.info.assert_called_once()
        assert "xx_XX" in log.info.call_args.args[0]

    def test_unreadable_po_is_reported_as_warning(self, tmp_path, monkeypatch, env):
        _build(tmp_path, "xx_XX", entries={"s1": "old"})
        self._rewrite_po(tmp_path, "xx_XX", {"s1": "new"}, po_mtime=2_000_000_000, mo_mtime=1_000_000_000)
        monkeypatch.setattr(polib, "pofile", lambda *a, **k: (_ for _ in ()).throw(OSError("broken")))
        log = self._fake_logger(monkeypatch)
        self._load(monkeypatch, tmp_path, "xx_XX")
        log.warning.assert_called_once()
        assert "broken" in log.warning.call_args.args[0]
        log.info.assert_not_called()

    def test_source_run_reads_po_when_mo_missing(self, tmp_path, monkeypatch, env):
        _build(tmp_path, "xx_XX", entries={"s1": "tX"})
        (tmp_path / "xx_XX" / "LC_MESSAGES" / "march7th.mo").unlink()
        self._load(monkeypatch, tmp_path, "xx_XX")
        assert tr("s1") == "tX"

    def test_source_run_prefers_newer_po_over_stale_mo(self, tmp_path, monkeypatch, env):
        _build(tmp_path, "xx_XX", entries={"s1": "old"})
        self._rewrite_po(tmp_path, "xx_XX", {"s1": "new"}, po_mtime=2_000_000_000, mo_mtime=1_000_000_000)
        self._load(monkeypatch, tmp_path, "xx_XX")
        assert tr("s1") == "new"

    def test_up_to_date_mo_is_used_without_reading_po(self, tmp_path, monkeypatch, env):
        _build(tmp_path, "xx_XX", entries={"s1": "compiled"})
        self._rewrite_po(tmp_path, "xx_XX", {"s1": "unused"}, po_mtime=1_000_000_000, mo_mtime=2_000_000_000)
        monkeypatch.setattr(polib, "pofile", lambda *a, **k: pytest.fail(".mo 未过期时不应解析 .po"))
        self._load(monkeypatch, tmp_path, "xx_XX")
        assert tr("s1") == "compiled"

    def test_unreadable_po_falls_back_to_stale_mo(self, tmp_path, monkeypatch, env):
        _build(tmp_path, "xx_XX", entries={"s1": "old"})
        self._rewrite_po(tmp_path, "xx_XX", {"s1": "new"}, po_mtime=2_000_000_000, mo_mtime=1_000_000_000)
        monkeypatch.setattr(polib, "pofile", lambda *a, **k: (_ for _ in ()).throw(OSError("broken")))
        self._load(monkeypatch, tmp_path, "xx_XX")
        assert tr("s1") == "old"

    def test_frozen_build_never_reads_po(self, tmp_path, monkeypatch, env):
        import sys
        _build(tmp_path, "xx_XX", entries={"s1": "tX"})
        (tmp_path / "xx_XX" / "LC_MESSAGES" / "march7th.mo").unlink()
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        self._load(monkeypatch, tmp_path, "xx_XX")
        assert tr("s1") == "s1"

    def test_auto_resolves_via_detect_lang(self, monkeypatch, env):
        import module.config as mcfg
        monkeypatch.setattr(mcfg.cfg, "get_value", lambda key, default=None: "auto")
        monkeypatch.setattr(loc, "_locale_dir", "不存在的目录")
        monkeypatch.setattr(loc, "detect_lang", lambda: "zz_ZZ")
        loc.load_language("auto")
        monkeypatch.setattr(loc, "_missing_logged", set())
        assert get_current_language() == "zz_ZZ"


class TestInstanceDisplayToRaw:
    def test_returns_tuple(self):
        from module.localization import instance_display_to_raw
        result = instance_display_to_raw("some_type", "some_name")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_unresolvable_returns_inputs(self):
        from module.localization import instance_display_to_raw
        result = instance_display_to_raw("unknown_type", "unknown_name")
        assert result[0] == "unknown_type"
        assert isinstance(result[1], str)

    def test_name_with_parentheses_cleaned(self):
        from module.localization import instance_display_to_raw
        result = instance_display_to_raw("unknown", "name（extra info）")
        assert "（" not in result[1]
