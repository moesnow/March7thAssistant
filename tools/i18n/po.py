# coding:utf-8
"""gettext(.po/.mo) 目录后端工具（JSON 双轨阶段）。

约定：
- msgid = 中文原文（key 即 msgid），源语言 zh_CN
- 复数条目：msgid_plural = 文案 + PLURAL_SUFFIX（仅元数据后缀，便于与 JSON 的
  key|plural 机械互转；GNU gettext 运行期按 msgid 查表，不受影响）
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
    """收集全部源条目：{msgid: {"ref": "path:line", "plural": bool}}（含数据源）。"""
    plurals, refs = collect_code_extras()
    data_literals, data_refs = collect_data_literals()
    entries: dict[str, dict] = {}
    for msgid, (path, line) in refs.items():
        entries[msgid] = {"ref": f"{path}:{line}", "plural": msgid in plurals}
    for msgid in data_literals:
        entries.setdefault(msgid, {"ref": data_refs.get(msgid, ""), "plural": False})
    return entries


def _occurrences(ref: str) -> list:
    if not ref:
        return []
    if ":" in ref and ref.rsplit(":", 1)[1].isdigit():
        path, line = ref.rsplit(":", 1)
        return [(path, line)]
    return [(ref, "")]


def _make_entry(msgid: str, meta: dict, lang: str | None,
                msgstr: str = "", plural_msgstr: str = "") -> polib.POEntry:
    is_plural = meta.get("plural", False)
    entry = polib.POEntry(
        msgid=msgid,
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
    """条目键集合：复数条目同时映射 msgid 与 msgid|plural。"""
    keys = set()
    for e in po:
        keys.add(e.msgid)
        if e.msgid_plural:
            keys.add(e.msgid + PLURAL_SUFFIX)
    return keys


def _index(po) -> dict:
    return {e.msgid: e for e in po}


def _build_pot(entries: dict[str, dict]) -> None:
    pot = polib.POFile(wrapwidth=78)
    pot.metadata = base_metadata("", is_pot=True)
    for msgid, meta in entries.items():
        pot.append(_make_entry(msgid, meta, None))
    pot.save(str(pot_path()))


# ---------------------------------------------------------------------------
# 迁移与生成
# ---------------------------------------------------------------------------

def migrate_po(catalogs: dict[str, dict]) -> dict:
    """JSON → .pot + 各语言 .po（一次性迁移；已存在的 msgstr 不覆盖）。

    po 条目取 zh_CN 全集（含历史遗留条目，保留译者已有工作）；
    .pot 只含源码/数据源条目（与 update-po 同一口径）。
    """
    entries = source_entries()
    base = catalogs[BASE_LOCALE]
    _build_pot(entries)

    stats = {}
    for lang in LOCALES:
        data = catalogs[lang]
        po = polib.POFile(wrapwidth=78)
        po.metadata = base_metadata(lang)
        for key in base:
            if key.endswith(PLURAL_SUFFIX) and key[: -len(PLURAL_SUFFIX)] in base:
                continue  # 复数形随单数条目合并
            is_plural = key + PLURAL_SUFFIX in base
            meta = entries.get(key, {}).copy()
            meta["ref"] = meta.get("ref", "")
            meta["plural"] = is_plural
            po.append(_make_entry(
                key, meta, lang,
                msgstr=data.get(key, ""),
                plural_msgstr=data.get(key + PLURAL_SUFFIX, ""),
            ))
        path = po_path(lang)
        os.makedirs(str(path.parent), exist_ok=True)
        po.save(str(path))
        stats[lang] = len(po)
    return stats


def update_po() -> dict:
    """把源码/数据源提取结果并入 .pot 与各 .po（新条目追加，已有译文不覆盖）。"""
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
        n = 0
        for msgid, meta in entries.items():
            if msgid in have:
                continue
            po.append(_make_entry(msgid, meta, lang,
                                  msgstr=msgid if lang == BASE_LOCALE else ""))
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

def _expected_json_value(json_d: dict, key: str, lang: str) -> str:
    """JSON 侧与 po 对齐后的期望值（nplurals=1 时复数形条目按"复数形非空优先"归一）。"""
    value = json_d.get(key, "") or ""
    if key.endswith(PLURAL_SUFFIX) and nplurals_of(lang) < 2:
        singular = json_d.get(key[: -len(PLURAL_SUFFIX)], "") or ""
        return value or singular
    return value


def check_po(catalogs: dict[str, dict], formatted: set[str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        pot = polib.pofile(str(pot_path()))
    except Exception:
        errors.append("march7th.pot 缺失或不可解析（运行 python -m tools.i18n migrate-po）")
        return errors, warnings
    pot_keys = po_keyset(pot)

    for lang in LOCALES:
        try:
            po = polib.pofile(str(po_path(lang)))
        except Exception:
            errors.append(f"[{lang}] po 目录缺失或不可解析（运行 python -m tools.i18n migrate-po）")
            continue

        # 1) 源条目集与 .pot 一致（模板之外的条目为历史遗留，保留并警告）
        keys = po_keyset(po)
        missing = pot_keys - keys
        extra = keys - pot_keys
        if missing:
            errors.append(f"[{lang}] po 缺少 {len(missing)} 个条目（运行 python -m tools.i18n update-po）")
        if extra:
            warnings.append(f"[{lang}] po 有 {len(extra)} 个模板之外的条目（历史遗留，保留）")

        # 2) 与 JSON 双轨一致
        json_d = catalogs[lang]
        mism = 0
        for k, v in json_d.items():
            if _po_value(po, k, lang) != _expected_json_value(json_d, k, lang):
                mism += 1
        rev = sum(1 for k in keys if k not in json_d)
        if mism:
            errors.append(f"[{lang}] po 与 JSON 译文不一致 {mism} 条")
        if rev:
            errors.append(f"[{lang}] po 有 JSON 没有的条目 {rev} 条")

        # 3) 占位符一致（带 .format() 的条目严格级同 JSON 侧）
        for e in po:
            values = [e.msgstr] if e.msgstr else list(e.msgstr_plural.values())
            for value in values:
                if not value:
                    continue
                if placeholders(e.msgid) != placeholders(value):
                    level = errors if e.msgid in formatted else warnings
                    level.append(f"[{lang}] po 占位符与原文不一致（msgid 长度 {len(e.msgid)}）")

        # 4) 复数条目 msgstr_plural 个数符合 Plural-Forms
        n = nplurals_of(lang)
        for e in po:
            if e.msgid_plural and len(e.msgstr_plural) != n:
                errors.append(
                    f"[{lang}] 复数条目 msgstr_plural 个数应为 {n}（msgid 长度 {len(e.msgid)}）"
                )

        # 5) .mo 与 .po 同步
        if not _mo_in_sync(po, lang):
            errors.append(f"[{lang}] .mo 与 .po 不同步（运行 python -m tools.i18n compile）")

        # 6) 位置占位符禁令同样适用于 po 条目
        for e in po:
            if e.msgid in formatted and has_positional_placeholder(e.msgid):
                errors.append(f"[{lang}] po 含位置占位符条目（msgid 长度 {len(e.msgid)}）")

    return errors, warnings


def _po_value(po, key: str, lang: str) -> str:
    """按 JSON 侧约定读取 po 译文（复数键 key|plural 映射 msgstr_plural）。"""
    idx = _index(po)
    if key.endswith(PLURAL_SUFFIX):
        singular = key[: -len(PLURAL_SUFFIX)]
        e = idx.get(singular)
        if e is None or not e.msgid_plural:
            return ""
        pos = 1 if nplurals_of(lang) >= 2 else 0
        return e.msgstr_plural.get(pos, "") or ""
    e = idx.get(key)
    if e is None or e.msgid_plural:
        return ""
    return e.msgstr or ""


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
