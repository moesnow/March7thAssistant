# coding:utf-8
"""gettext(.po/.mo) 目录后端工具。

约定：
- msgid = 中文原文（key 即 msgid），源语言 zh_CN
- 复数条目：msgid_plural = 文案 + PLURAL_SUFFIX（仅元数据后缀；GNU gettext 运行期按 msgid 查表）
- .mo 随 .po 一起提交（打包流程整目录拷贝 assets，零改动），check 校验两者同步
- 本模块只做机械读写，调用方输出统计时不得打印译文内容
"""
from __future__ import annotations

import os
import tempfile

import polib

from . import (
    BASE_LOCALE,
    LOCALES,
    LOCALE_DIR,
    PLURAL_SUFFIX,
    collect_code_extras,
    collect_data_literals,
    collect_table_literals,
    has_positional_placeholder,
    placeholders,
)

PO_DOMAIN = "march7th"


def po_path(lang: str):
    return LOCALE_DIR / lang / "LC_MESSAGES" / f"{PO_DOMAIN}.po"


def mo_path(lang: str):
    return LOCALE_DIR / lang / "LC_MESSAGES" / f"{PO_DOMAIN}.mo"


def pot_path():
    return LOCALE_DIR / f"{PO_DOMAIN}.pot"


def nplurals_of(lang: str) -> int:
    from module.localization.languages import get_lang_meta

    for part in get_lang_meta(lang)["plural_forms"].split(";"):
        part = part.strip()
        if part.startswith("nplurals="):
            try:
                return int(part.split("=", 1)[1])
            except ValueError:
                return 1
    return 1


def base_metadata(lang: str, is_pot: bool = False) -> dict:
    from module.localization.languages import get_lang_meta

    meta = {
        "Project-Id-Version": "march7th",
        "Report-Msgid-Bugs-To": "",
        "POT-Creation-Date": "2026-09-24 00:00+0800",
        "PO-Revision-Date": "2026-09-24 00:00+0800",
        "Last-Translator": "",
        "Language-Team": "" if is_pot else lang,
        "Language": "" if is_pot else lang,
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=UTF-8",
        "Content-Transfer-Encoding": "8bit",
        "X-Generator": "tools.i18n",
    }
    if not is_pot:
        meta["Plural-Forms"] = get_lang_meta(lang)["plural_forms"]
    return meta


# ---------------------------------------------------------------------------
# 源条目集合
# ---------------------------------------------------------------------------

def source_entries() -> dict[str, dict]:
    """收集全部源条目：{msgid: {"ref": "path:line", "plural": bool, "contexts": tuple}}。

    来源四类：源码 tr/tn/trc 字面量、TABLE_SOURCES 常量表、DATA_SOURCES 数据文件、trc 语境。
    contexts 为经 trc() 传入的 msgctxt 集合（同一 msgid 可带多个语境）。
    """
    plurals, refs, contexts = collect_code_extras()
    table_literals, table_refs = collect_table_literals()
    data_literals, data_refs = collect_data_literals()
    entries: dict[str, dict] = {}
    for msgid, (path, line) in refs.items():
        entries[msgid] = {
            "ref": f"{path}:{line}",
            "plural": msgid in plurals,
            "contexts": tuple(sorted(contexts.get(msgid, ()))),
        }
    # 常量表与数据源都来自 set，排序保证 extract 结果可复现
    for msgid in sorted(table_literals):
        entries.setdefault(msgid, {"ref": table_refs.get(msgid, ""), "plural": False, "contexts": ()})
    for msgid in sorted(data_literals):
        entries.setdefault(msgid, {"ref": data_refs.get(msgid, ""), "plural": False, "contexts": ()})
    return entries


def entry_key(entry) -> str:
    """条目在目录中的唯一键：有 msgctxt 时用 gettext 的 'msgctxt\\x04msgid' 形式。"""
    if getattr(entry, "msgctxt", ""):
        return f"{entry.msgctxt}\x04{entry.msgid}"
    return entry.msgid


def context_key(msgctxt: str, msgid: str) -> str:
    """按 gettext 约定拼 msgctxt 条目的键。"""
    return f"{msgctxt}\x04{msgid}"


def _occurrences(ref: str) -> list:
    if not ref:
        return []
    if ":" in ref and ref.rsplit(":", 1)[1].isdigit():
        path, line = ref.rsplit(":", 1)
        return [(path, line)]
    return [(ref, "")]


def _make_entry(msgid: str, meta: dict, lang: str | None,
                msgstr: str = "", plural_msgstr: str = "",
                msgctxt: str | None = None) -> polib.POEntry:
    is_plural = meta.get("plural", False)
    entry = polib.POEntry(
        msgid=msgid,
        msgctxt=msgctxt,
        msgstr="" if is_plural else msgstr,
        occurrences=_occurrences(meta.get("ref", "")),
    )
    if is_plural:
        entry.msgid_plural = msgid + PLURAL_SUFFIX
        if lang is None:  # .pot 模板：nplurals=2 形式
            entry.msgstr_plural = {0: "", 1: ""}
        else:
            n = nplurals_of(lang)
            if n >= 2:
                entry.msgstr_plural = {0: msgstr, 1: plural_msgstr}
            else:
                # 单形式语言：复数形非空优先（通吃 n），否则用单数形
                entry.msgstr_plural = {0: plural_msgstr or msgstr}
    return entry


def po_keyset(po) -> set[str]:
    """条目键集合：带 msgctxt 的条目用 ctx\\x04msgid，复数条目同时映射 msgid|plural。"""
    keys = set()
    for e in po:
        key = entry_key(e)
        keys.add(key)
        if e.msgid_plural:
            keys.add(key + PLURAL_SUFFIX)
    return keys


def _index(po) -> dict:
    return {entry_key(e): e for e in po}


def _context_keys(entries: dict[str, dict]) -> set[str]:
    """源侧 trc 语境对应的目录键集合。"""
    keys = set()
    for msgid, meta in entries.items():
        for ctx in meta.get("contexts", ()):
            keys.add(context_key(ctx, msgid))
    return keys


def _build_pot(entries: dict[str, dict]) -> None:
    pot = polib.POFile(wrapwidth=78)
    pot.metadata = base_metadata("", is_pot=True)
    for msgid, meta in entries.items():
        pot.append(_make_entry(msgid, meta, None))
        for ctx in meta.get("contexts", ()):
            pot.append(_make_entry(msgid, meta, None, msgctxt=ctx))
    pot.save(str(pot_path()))


# ---------------------------------------------------------------------------
# 生成
# ---------------------------------------------------------------------------

def update_po() -> dict:
    """把源码/数据源提取结果并入 .pot 与各 .po（新条目追加，已有译文不覆盖）。

    - 已有单数条目在源侧改为 tn() 复数时升级为复数条目（译文保留在 msgstr[0]）；
    - trc() 的每条语境补一条 msgctxt 条目，同时保留无上下文条目供 tr() 回退。
    """
    entries = source_entries()
    _build_pot(entries)

    added: dict[str, int] = {}
    for lang in LOCALES:
        path = po_path(lang)
        try:
            po = polib.pofile(str(path))
        except Exception:
            po = polib.POFile(wrapwidth=78)
            po.metadata = base_metadata(lang)
        have = po_keyset(po)
        index = _index(po)
        n = 0
        for msgid, meta in entries.items():
            if msgid in have:
                if meta.get("plural"):
                    e = index.get(msgid)
                    if e is not None and not e.msgid_plural:
                        forms = nplurals_of(lang)
                        old = e.msgstr or ""
                        e.msgid_plural = msgid + PLURAL_SUFFIX
                        e.msgstr_plural = ({0: old, 1: ""} if forms >= 2 else {0: old})
                        e.msgstr = ""
                        n += 1
            else:
                po.append(_make_entry(msgid, meta, lang,
                                      msgstr=msgid if lang == BASE_LOCALE else ""))
                n += 1
            for ctx in meta.get("contexts", ()):
                if context_key(ctx, msgid) in have:
                    continue
                # 语境条目与无上下文条目共享同一 ref；zh_CN 直接填原文
                po.append(_make_entry(msgid, meta, lang,
                                      msgstr=msgid if lang == BASE_LOCALE else "",
                                      msgctxt=ctx))
                n += 1
        po.save(str(path))
        added[lang] = n
    return added


def compile_po(lang: str) -> int:
    """编译 .po -> .mo，返回字节数。"""
    po = polib.pofile(str(po_path(lang)))
    path = mo_path(lang)
    os.makedirs(str(path.parent), exist_ok=True)
    po.save_as_mofile(str(path))
    return os.path.getsize(str(path))


# ---------------------------------------------------------------------------
# 校验
# ---------------------------------------------------------------------------

def _is_untranslated(entry) -> bool:
    if entry.msgid_plural:
        return not all(entry.msgstr_plural.values())
    return not entry.msgstr


def check_po(formatted: set[str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    entries = source_entries()
    try:
        pot = polib.pofile(str(pot_path()))
    except Exception:
        errors.append("march7th.pot 缺失或不可解析（运行 python -m tools.i18n extract）")
        return errors, warnings
    pot_keys = po_keyset(pot)
    unregistered = set(entries) - pot_keys
    if unregistered:
        errors.append(f"{len(unregistered)} 条源文案未登记进 .pot（运行 python -m tools.i18n extract）")

    # trc() 的每条语境都必须在 .pot 里有对应 msgctxt 条目
    ctx_keys = _context_keys(entries)
    ctx_missing_pot = ctx_keys - pot_keys
    if ctx_missing_pot:
        errors.append(f"{len(ctx_missing_pot)} 条 trc 语境未登记进 .pot（运行 python -m tools.i18n extract）")

    for lang in LOCALES:
        try:
            po = polib.pofile(str(po_path(lang)))
        except Exception:
            errors.append(f"[{lang}] po 目录缺失或不可解析（运行 python -m tools.i18n extract）")
            continue

        # 1) 源条目集与 .pot 一致（模板之外的条目为历史遗留，保留并警告）
        keys = po_keyset(po)
        missing = pot_keys - keys
        extra = keys - pot_keys
        if missing:
            errors.append(f"[{lang}] po 缺少 {len(missing)} 个条目（运行 python -m tools.i18n extract）")
        if extra:
            warnings.append(f"[{lang}] po 有 {len(extra)} 个模板之外的条目（历史遗留，保留）")

        # 1b) trc 语境条目齐全（单独报错，便于定位是哪个语境漏了）
        ctx_missing = ctx_keys - keys
        if ctx_missing:
            errors.append(f"[{lang}] po 缺少 {len(ctx_missing)} 条 trc 语境条目（运行 python -m tools.i18n extract）")

        # 2) 占位符一致（带 .format() 的条目严格级）
        for e in po:
            values = [e.msgstr] if e.msgstr else list(e.msgstr_plural.values())
            for value in values:
                if not value:
                    continue
                if placeholders(e.msgid) != placeholders(value):
                    level = errors if e.msgid in formatted else warnings
                    level.append(f"[{lang}] po 占位符与原文不一致（msgid 长度 {len(e.msgid)}）")

        # 3) 复数条目 msgstr_plural 个数符合 Plural-Forms
        n = nplurals_of(lang)
        for e in po:
            if e.msgid_plural and len(e.msgstr_plural) != n:
                errors.append(
                    f"[{lang}] 复数条目 msgstr_plural 个数应为 {n}（msgid 长度 {len(e.msgid)}）"
                )

        # 4) .mo 与 .po 同步
        if not _mo_in_sync(po, lang):
            errors.append(f"[{lang}] .mo 与 .po 不同步（运行 python -m tools.i18n compile）")

        # 5) 位置占位符禁令同样适用于 po 条目
        for e in po:
            if e.msgid in formatted and has_positional_placeholder(e.msgid):
                errors.append(f"[{lang}] po 含位置占位符条目（msgid 长度 {len(e.msgid)}）")

        # 6) 待翻译统计 —— 仅警告
        untranslated = sum(1 for e in po if _is_untranslated(e))
        if untranslated:
            warnings.append(f"[{lang}] 有 {untranslated} 条待翻译")

    return errors, warnings


def _mo_in_sync(po, lang: str) -> bool:
    path = mo_path(lang)
    if not path.is_file():
        return False
    with tempfile.TemporaryDirectory() as td:
        tmp = os.path.join(td, f"{PO_DOMAIN}.mo")
        po.save_as_mofile(tmp)
        with open(tmp, "rb") as f:
            fresh = f.read()
    with open(str(path), "rb") as f:
        return f.read() == fresh
