# coding:utf-8
"""开发期多语言（i18n）工具库。

提供三个子命令（见 ``python -m tools.i18n -h``）：

- ``extract``  扫描源码中的 tr()/tn() 字面量，把新文案登记进翻译目录
- ``sync``     把 zh_CN 的 key 补齐到其它语言（zh_TW 用 OpenCC 预填，其余留空）
- ``check``    校验翻译目录，CI 与 pytest 均调用同一套规则

设计约定：
- zh_CN.json 为源语言目录，key 与 value 均为中文原文（key 即 msgid）；
- 其余语言 value 为译文，允许为空（空值视为"待翻译"，只警告不报错）；
- 复数形式的条目以 ``|plural`` 后缀单独成键（见 module.localization.tn）；
- 运行期代码绝不写翻译目录，登记/补齐一律通过本工具进行。
"""
from __future__ import annotations

import ast
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
LOCALE_DIR = ROOT / "assets" / "locales"
BASE_LOCALE = "zh_CN"
LOCALES = ["zh_CN", "zh_TW", "ja_JP", "ko_KR", "en_US"]

# 参与提取的源码目录/文件（tests、3rdparty 等不参与）
SCAN_DIRS = ["app", "module", "tasks", "utils", "tools"]
SCAN_FILES = ["main.py", "app.py", "updater.py", "build.py"]

# 视为翻译调用的函数名（含 self.tr(...) 形式）
TRANSLATION_FUNCS = {"tr", "tn"}

# tn() 复数形式的目录键后缀，与 module.localization.PLURAL_SUFFIX 保持一致
PLURAL_SUFFIX = "|plural"

# 占位符：{name} / {} / { } 等，{{ }} 转义不计
PLACEHOLDER_RE = re.compile(r"(?<!\{)\{([^{}]*)\}(?!\})")

# 位置占位符：{} / {0} / {1} ...
POSITIONAL_FIELD_RE = re.compile(r"(?<!\{)\{(\d*)\}(?!\})")


def has_positional_placeholder(text: str) -> bool:
    """是否含位置占位符（{} / {0} 等）；带 .format() 的文案必须使用命名占位符。"""
    return bool(POSITIONAL_FIELD_RE.search(text))


def placeholders(text: str) -> Counter:
    """提取 str.format 风格占位符的字段名集合（含出现次数）。"""
    return Counter(PLACEHOLDER_RE.findall(text))


# ---------------------------------------------------------------------------
# 源码扫描
# ---------------------------------------------------------------------------

class _LiteralCollector(ast.NodeVisitor):
    """收集 tr()/tn() 的字面量参数，并区分是否紧跟 .format()。"""

    def __init__(self):
        self.literals: set[str] = set()
        self.formatted: set[str] = set()
        self.plural_literals: set[str] = set()  # 经 tn() 调用的字面量（复数条目）
        self.refs: dict[str, tuple[str, int]] = {}  # 字面量 -> 首次出现 (文件, 行号)
        self.dynamic = 0
        self._current_file = "<string>"

    @staticmethod
    def _func_name(node: ast.expr) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return None

    def visit_Call(self, node: ast.Call) -> None:
        func_name = self._func_name(node.func)

        # tr("...").format(...) 链式：占位符必须与译文严格一致
        if func_name == "format" and isinstance(node.func, ast.Attribute):
            inner = node.func.value
            if isinstance(inner, ast.Call):
                inner_name = self._func_name(inner.func)
                if inner_name in TRANSLATION_FUNCS and inner.args:
                    arg = inner.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        self.formatted.add(arg.value)

        if func_name in TRANSLATION_FUNCS and node.args:
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if arg.value.strip():
                    self.literals.add(arg.value)
                    if func_name == "tn":
                        self.plural_literals.add(arg.value)
                    self.refs.setdefault(arg.value, (self._current_file, node.lineno))
                # 空白字符串无翻译意义，tr() 运行期会原样返回，忽略
            else:
                self.dynamic += 1

        self.generic_visit(node)


def iter_source_files():
    """遍历参与提取的源码文件。"""
    for d in SCAN_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            yield p
    for f in SCAN_FILES:
        p = ROOT / f
        if p.is_file():
            yield p


def collect_literals_from_source(source: str, filename: str = "<string>") -> tuple[set[str], set[str], int]:
    """从一段源码收集 tr()/tn() 字面量，返回 (字面量, 带 .format() 的字面量, 动态调用次数)。"""
    tree = ast.parse(source, filename=filename)
    collector = _LiteralCollector()
    collector._current_file = filename
    collector.visit(tree)
    return collector.literals, collector.formatted, collector.dynamic


def collect_calls_from_source(source: str, filename: str = "<string>") -> tuple[set[str], set[str], int, set[str], dict]:
    """同 collect_literals_from_source，另返回 (tn 复数字面量, 出处映射)。"""
    tree = ast.parse(source, filename=filename)
    collector = _LiteralCollector()
    collector._current_file = filename
    collector.visit(tree)
    return collector.literals, collector.formatted, collector.dynamic, collector.plural_literals, collector.refs


def collect_code_extras() -> tuple[set[str], dict]:
    """返回 (tn 复数字面量集合, 字面量出处映射)。"""
    plurals: set[str] = set()
    refs: dict[str, tuple[str, int]] = {}
    for path in iter_source_files():
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
            collected = collect_calls_from_source(source, str(path).replace("\\", "/"))
        except (SyntaxError, ValueError):
            continue
        plurals |= collected[3]
        for k, v in collected[4].items():
            refs.setdefault(k, v)
    return plurals, refs


def collect_code_literals() -> tuple[set[str], set[str], int]:
    """返回 (全部字面量, 带 .format() 的字面量, 动态调用次数)。"""
    literals: set[str] = set()
    formatted: set[str] = set()
    dynamic = 0
    for path in iter_source_files():
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
            collected = collect_literals_from_source(source, str(path))
        except (SyntaxError, ValueError):
            continue
        literals |= collected[0]
        formatted |= collected[1]
        dynamic += collected[2]
    return literals, formatted, dynamic


# ---------------------------------------------------------------------------
# 目录读写
# ---------------------------------------------------------------------------

def _load_raw(path: Path) -> tuple[dict, list]:
    """读取目录并检测重复 key（json 默认静默去重，这里显式暴露）。"""
    dups: list[str] = []

    def hook(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                dups.append(k)
            result[k] = v
        return result

    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=hook)
    return data, dups


def load_catalogs() -> tuple[dict[str, dict], list[str]]:
    """读取全部语言目录，返回 ({lang: {key: value}}, 错误列表)。"""
    catalogs: dict[str, dict] = {}
    errors: list[str] = []
    for lang in LOCALES:
        path = LOCALE_DIR / f"{lang}.json"
        if not path.is_file():
            errors.append(f"[{lang}] 目录文件缺失: {path}")
            catalogs[lang] = {}
            continue
        try:
            data, dups = _load_raw(path)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            errors.append(f"[{lang}] JSON 解析失败: {e}")
            catalogs[lang] = {}
            continue
        if dups:
            errors.append(f"[{lang}] 存在重复 key: {len(dups)} 个")
        if any(not isinstance(v, str) for v in data.values()):
            errors.append(f"[{lang}] 存在非字符串 value")
        catalogs[lang] = data
    return catalogs, errors


def dump_catalog(lang: str, data: dict) -> None:
    """按仓库约定格式（4 空格缩进、UTF-8、结尾换行）写回目录。"""
    path = LOCALE_DIR / f"{lang}.json"
    text = json.dumps(data, ensure_ascii=False, indent=4) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def _s2t(text: str) -> str:
    """简体转繁体（OpenCC），失败时原样返回。"""
    try:
        from opencc import OpenCC
        return OpenCC("s2t").convert(text)
    except Exception:
        return text


def sync_catalogs(catalogs: dict[str, dict] | None = None) -> dict[str, int]:
    """把 zh_CN 的 key 补齐到其它语言，返回各语言新增数量。

    - zh_TW 预填 OpenCC 简转繁结果（可由译者继续润色）
    - 其余语言留空（空值 = 待翻译）
    - tn() 复数字面量同时登记 key|plural 条目
    """
    if catalogs is None:
        catalogs, errors = load_catalogs()
        if errors:
            raise RuntimeError("翻译目录不可用: " + "; ".join(errors))
    base = catalogs[BASE_LOCALE]
    added: dict[str, int] = {}
    for lang in LOCALES:
        if lang == BASE_LOCALE:
            continue
        data = catalogs[lang]
        before = len(data)
        for key in base:
            if key not in data:
                data[key] = _s2t(key) if lang == "zh_TW" else ""
        added[lang] = len(data) - before
        if added[lang]:
            dump_catalog(lang, data)
    return added


def collect_data_literals() -> tuple[set[str], dict[str, str]]:
    """数据源驱动的翻译字面量（character_names / instance_names）。

    返回 (字面量集合, 字面量 -> 来源文件)。instance_names 中「凝滞虚影」的 info
    按斜杠拆分后逐段登记，与 module.localization.get_instance_names 运行期一致。
    """
    import re as _re

    literals: set[str] = set()
    refs: dict[str, str] = {}

    def add(text, ref):
        if isinstance(text, str) and text.strip():
            literals.add(text)
            refs.setdefault(text, ref)

    char_path = "assets/config/character_names.json"
    try:
        data = json.loads((ROOT / char_path).read_text(encoding="utf-8"))
        for v in data.values():
            add(v, char_path)
    except Exception:
        pass

    inst_path = "assets/config/instance_names.json"
    try:
        data = json.loads((ROOT / inst_path).read_text(encoding="utf-8"))
        for inst_type, names in data.items():
            add(inst_type, inst_path)
            for raw_name, info in names.items():
                add(raw_name, inst_path)
                if isinstance(info, str):
                    if inst_type == "凝滞虚影" and "/" in info:
                        for part in _re.split(r"\s*/\s*", info):
                            add(part.strip(), inst_path)
                    else:
                        add(info, inst_path)
    except Exception:
        pass

    return literals, refs


# ---------------------------------------------------------------------------
# 提取与校验
# ---------------------------------------------------------------------------

def extract() -> dict:
    """登记新文案并补齐各语言骨架，返回统计信息。"""
    literals, _, dynamic = collect_code_literals()
    plurals, _ = collect_code_extras()
    catalogs, errors = load_catalogs()
    if errors:
        raise RuntimeError("翻译目录不可用: " + "; ".join(errors))

    base = catalogs[BASE_LOCALE]
    new_keys = sorted(k for k in literals if k not in base)
    for key in new_keys:
        base[key] = key
    plural_new = 0
    for key in sorted(plurals):
        pk = key + PLURAL_SUFFIX
        if pk not in base:
            base[pk] = key  # zh 预填原文（中文单复数同形）
            plural_new += 1
    if new_keys or plural_new:
        dump_catalog(BASE_LOCALE, base)
    added = sync_catalogs(catalogs)
    return {"new_keys": len(new_keys) + plural_new, "synced": added, "dynamic_calls": dynamic}


def run_checks() -> tuple[list[str], list[str]]:
    """校验翻译目录，返回 (错误列表, 警告列表)；错误非空即应视为失败。"""
    errors: list[str] = []
    warnings: list[str] = []

    catalogs, load_errors = load_catalogs()
    errors.extend(load_errors)
    if load_errors:
        return errors, warnings

    base = catalogs[BASE_LOCALE]
    base_keys = set(base)

    # 1) 各语言 key 集合必须一致
    for lang in LOCALES:
        if lang == BASE_LOCALE:
            continue
        missing = base_keys - set(catalogs[lang])
        extra = set(catalogs[lang]) - base_keys
        if missing:
            errors.append(f"[{lang}] 缺少 {len(missing)} 个 key（运行 python -m tools.i18n sync 补齐）")
        if extra:
            errors.append(f"[{lang}] 存在 {len(extra)} 个 zh_CN 没有的 key")

    literals, formatted, _ = collect_code_literals()

    # 2) 源码字面量必须已登记（tests 不参与提取，见模块 docstring）
    unregistered = sorted(k for k in literals if k not in base_keys)
    if unregistered:
        errors.append(
            f"源码中有 {len(unregistered)} 条 tr()/tn() 字面量未登记"
            f"（运行 python -m tools.i18n extract 登记）"
        )

    # 3) 占位符一致性：带 .format() 的条目严格校验（翻译丢失占位符会直接抛异常），
    #    其余条目仅警告，避免对说明性文本里的字面大括号误伤
    for lang in LOCALES:
        for key, value in catalogs[lang].items():
            if not isinstance(value, str) or not value.strip():
                continue
            if placeholders(key) != placeholders(value):
                level = errors if key in formatted else warnings
                level.append(f"[{lang}] 占位符与原文不一致（key 长度 {len(key)}）")

    # 3b) 带 .format() 的字面量禁止位置占位符（译文无法调整语序）
    for key in sorted(formatted):
        if has_positional_placeholder(key):
            errors.append(f"位置占位符请改为命名占位符（key 长度 {len(key)}）")

    # 4) 空值（待翻译）—— 仅警告
    for lang in LOCALES:
        if lang == BASE_LOCALE:
            continue
        empty = sum(1 for v in catalogs[lang].values() if not str(v).strip())
        if empty:
            warnings.append(f"[{lang}] 有 {empty} 条待翻译（value 为空）")

    # 5) 孤儿 key（数据源已声明的除外）—— 仅警告
    data_literals, _ = collect_data_literals()
    referenced = literals | {k + PLURAL_SUFFIX for k in literals} | data_literals
    orphans = base_keys - referenced
    if orphans:
        warnings.append(f"zh_CN 有 {len(orphans)} 个 key 未在源码字面量中出现（历史遗留）")

    # 6) 多语言文档：表格行数一致、语言后缀命名合法 —— 仅警告
    warnings.extend(check_docs())

    # 7) gettext 双轨目录（.pot/.po/.mo）
    try:
        from .po import check_po
        po_errors, po_warnings = check_po(catalogs, formatted)
        errors.extend(po_errors)
        warnings.extend(po_warnings)
    except ImportError:
        pass

    return errors, warnings


def check_docs() -> list[str]:
    """多语言文档校验（警告级）。

    - TasksTable 各语言版本表格行数须与基准版一致（防止改漏一份）
    - {Base}_{后缀}.md 的后缀须在 module.localization.languages 注册表声明
    """
    warnings: list[str] = []
    from module.localization.languages import LANGS

    docs_dir = ROOT / "assets" / "docs"
    suffixes = {m["docs_suffix"] for m in LANGS.values() if m["docs_suffix"]}
    bases = ("Tutorial", "FAQ", "Changelog", "TasksTable")

    def table_rows(p: Path) -> int:
        return sum(1 for line in p.read_text(encoding="utf-8").splitlines() if line.strip().startswith("|"))

    base = docs_dir / "TasksTable.md"
    if base.is_file():
        rows = table_rows(base)
        for f in sorted(docs_dir.glob("TasksTable_*.md")):
            if table_rows(f) != rows:
                warnings.append(f"文档 {f.name} 表格行数与 TasksTable.md 不一致（可能改漏一份）")

    for f in sorted(docs_dir.glob("*.md")):
        stem = f.stem
        for b in bases:
            if stem.startswith(b + "_"):
                suf = stem[len(b) + 1:]
                if suf not in suffixes:
                    warnings.append(f"文档 {f.name} 的语言后缀 {suf!r} 未在语言注册表声明")
                break
    return warnings
