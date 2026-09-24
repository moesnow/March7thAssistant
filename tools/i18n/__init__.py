# coding:utf-8
"""开发期多语言（i18n）工具库（gettext 后端）。

提供以下子命令（见 ``python -m tools.i18n -h``）：

- ``extract``    扫描源码/数据源中的 tr()/tn()/trc() 字面量，把新文案并入 .pot/.po
- ``check``      校验 .pot/.po/.mo 与多语言文档，CI 与 pytest 均调用同一套规则
- ``compile``    编译 .po -> .mo（.mo 需随 .po 一起提交）

设计约定：
- msgid 即中文原文（zh_CN 为源语言），.po/.mo 位于 assets/locales/{lang}/LC_MESSAGES/；
- 复数形式的条目 msgid_plural = 文案 + PLURAL_SUFFIX（收口于 module.localization）；
- 数据源（character_names/instance_names）由 collect_data_literals() 一并登记；
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

# tn() 复数形式的目录键后缀，收口于 module.localization
from module.localization import PLURAL_SUFFIX  # noqa: E402

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
# 数据源字面量
# ---------------------------------------------------------------------------


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
    """登记新文案（并入 .pot/.po；复数条目随 tn() 自动升级），返回统计信息。"""
    from .po import update_po
    _, _, dynamic = collect_code_literals()
    added = update_po()
    return {"new_keys": sum(added.values()), "synced": added, "dynamic_calls": dynamic}


def run_checks() -> tuple[list[str], list[str]]:
    """校验翻译目录，返回 (错误列表, 警告列表)；错误非空即应视为失败。"""
    errors: list[str] = []
    warnings: list[str] = []
    _, formatted, _ = collect_code_literals()

    # 1) 带 .format() 的字面量禁止位置占位符（译文无法调整语序）
    for key in sorted(formatted):
        if has_positional_placeholder(key):
            errors.append(f"位置占位符请改为命名占位符（key 长度 {len(key)}）")

    # 2) 多语言文档：表格行数一致、语言后缀命名合法 —— 仅警告
    warnings.extend(check_docs())

    # 3) gettext 目录（.pot/.po/.mo）
    try:
        from .po import check_po
        po_errors, po_warnings = check_po(formatted)
        errors.extend(po_errors)
        warnings.extend(po_warnings)
    except Exception as e:
        errors.append(f"gettext 目录校验失败: {e}")

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
