# coding:utf-8
"""开发期多语言（i18n）工具库（gettext 后端）。

提供以下子命令（见 ``python -m tools.i18n -h``）：

- ``extract``    扫描源码/数据源中的 tr()/tn()/trc() 字面量，把新文案并入 .pot/.po
- ``check``      校验 .pot/.po/.mo 与多语言文档，CI 与 pytest 均调用同一套规则
- ``compile``    编译 .po -> .mo（.mo 需随 .po 一起提交）

设计约定：
- msgid 即中文原文（zh_CN 为源语言），.po/.mo 位于 assets/locales/{lang}/LC_MESSAGES/；
- 复数形式的条目 msgid_plural = 文案 + PLURAL_SUFFIX（收口于 module.localization）；
- 语境形式的条目 msgctxt = trc() 的第一个参数（目录键为 'msgctxt\\x04msgid'）；
- 文案来源四类，缺任一类都会造成静默漏译：
  1) 源码里 tr()/tn()/trc() 的字面量参数（AST 扫描 SCAN_DIRS/SCAN_FILES）；
  2) TABLE_SOURCES 声明的模块级常量表 —— 取值经 tr(表[key]) 动态传入，静态扫不到；
  3) DATA_SOURCES 声明的数据文件 —— display_name 等展示字段经 tr() 传入；
  4) trc() 的语境（每个 (context, msgid) 生成一条 msgctxt 条目）。
- 运行期代码绝不写翻译目录，登记/补齐一律通过本工具进行。
"""
from __future__ import annotations

import ast
import json
import re
import sys
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

# 带语境的翻译调用：第一个参数是 msgctxt（语境），第二个参数才是文案（msgid）
CONTEXT_FUNCS = {"trc"}

# tn() 复数形式的目录键后缀，收口于 module.localization
from module.localization import PLURAL_SUFFIX  # noqa: E402


def ensure_utf8_output(streams=None) -> None:
    """把输出流切换到 UTF-8（无法编码的字符替换掉）。

    Windows 的控制台/管道可能把 stdout 绑定到 cp1252 等本地编码，
    打印中文警告会直接抛 UnicodeEncodeError（CI 曾因此挂掉）；
    本地 UTF-8 终端不复现，所以必须在工具入口统一兜底。
    """
    if streams is None:
        streams = (sys.stdout, sys.stderr)
    for stream in streams:
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

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
    """收集 tr()/tn()/trc() 的字面量参数，并区分是否紧跟 .format()。"""

    def __init__(self):
        self.literals: set[str] = set()
        self.formatted: set[str] = set()
        self.plural_literals: set[str] = set()  # 经 tn() 调用的字面量（复数条目）
        self.refs: dict[str, tuple[str, int]] = {}  # 字面量 -> 首次出现 (文件, 行号)
        self.contexts: dict[str, set[str]] = {}  # trc 字面量 -> 语境集合（msgctxt）
        self.dynamic = 0
        self._current_file = "<string>"

    @staticmethod
    def _func_name(node: ast.expr) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return None

    @staticmethod
    def _msgid_index(func_name: str) -> int | None:
        """取出该翻译函数里"文案"参数的下标（trc 的文案在第 2 个参数）。"""
        if func_name in TRANSLATION_FUNCS:
            return 0
        if func_name in CONTEXT_FUNCS:
            return 1
        return None

    def visit_Call(self, node: ast.Call) -> None:
        func_name = self._func_name(node.func)

        # tr("...").format(...) / trc("ctx", "...").format(...) 链式：占位符必须与译文严格一致
        if func_name == "format" and isinstance(node.func, ast.Attribute):
            inner = node.func.value
            if isinstance(inner, ast.Call):
                inner_name = self._func_name(inner.func)
                idx = self._msgid_index(inner_name) if inner_name else None
                if idx is not None and len(inner.args) > idx:
                    arg = inner.args[idx]
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

        # trc(context, text)：context 进 msgctxt，text 进 msgid
        elif func_name in CONTEXT_FUNCS and node.args:
            if len(node.args) < 2:
                self.dynamic += 1
            else:
                ctx_arg, text_arg = node.args[0], node.args[1]
                if not (isinstance(text_arg, ast.Constant) and isinstance(text_arg.value, str)):
                    self.dynamic += 1
                elif text_arg.value.strip():
                    # 文案本身仍作为无上下文条目登记：trc 运行期在无 msgctxt 条目时回退 tr()
                    self.literals.add(text_arg.value)
                    self.refs.setdefault(text_arg.value, (self._current_file, node.lineno))
                    if isinstance(ctx_arg, ast.Constant) and isinstance(ctx_arg.value, str) and ctx_arg.value.strip():
                        self.contexts.setdefault(text_arg.value, set()).add(ctx_arg.value)
                    else:
                        self.dynamic += 1

        self.generic_visit(node)



def _rel(path) -> str:
    """源码文件名统一为仓库相对路径（POSIX 分隔符）。

    # 引用写进 .po/.pot，绝对路径会泄露本机目录结构并在不同机器间产生整文件 diff。
    """
    try:
        return Path(path).relative_to(ROOT).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


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
    """从一段源码收集 tr()/tn()/trc() 字面量，返回 (字面量, 带 .format() 的字面量, 动态调用次数)。"""
    tree = ast.parse(source, filename=filename)
    collector = _LiteralCollector()
    collector._current_file = filename
    collector.visit(tree)
    return collector.literals, collector.formatted, collector.dynamic


def collect_calls_from_source(source: str, filename: str = "<string>") -> tuple[set[str], set[str], int, set[str], dict, dict]:
    """同 collect_literals_from_source，另返回 (tn 复数字面量, 出处映射, trc 语境映射)。"""
    tree = ast.parse(source, filename=filename)
    collector = _LiteralCollector()
    collector._current_file = filename
    collector.visit(tree)
    return (collector.literals, collector.formatted, collector.dynamic,
            collector.plural_literals, collector.refs, collector.contexts)


def collect_code_extras() -> tuple[set[str], dict, dict]:
    """返回 (tn 复数字面量集合, 字面量出处映射, trc 语境映射)。"""
    plurals: set[str] = set()
    refs: dict[str, tuple[str, int]] = {}
    contexts: dict[str, set[str]] = {}
    for path in iter_source_files():
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
            collected = collect_calls_from_source(source, _rel(path))
        except (SyntaxError, ValueError):
            continue
        plurals |= collected[3]
        for k, v in collected[4].items():
            refs.setdefault(k, v)
        for k, v in collected[5].items():
            contexts.setdefault(k, set()).update(v)
    return plurals, refs, contexts


def collect_code_literals() -> tuple[set[str], set[str], int]:
    """返回 (全部字面量, 带 .format() 的字面量, 动态调用次数)。"""
    literals: set[str] = set()
    formatted: set[str] = set()
    dynamic = 0
    for path in iter_source_files():
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
            collected = collect_literals_from_source(source, _rel(path))
        except (SyntaxError, ValueError):
            continue
        literals |= collected[0]
        formatted |= collected[1]
        dynamic += collected[2]
    return literals, formatted, dynamic


# ---------------------------------------------------------------------------
# 常量表与数据源字面量
# ---------------------------------------------------------------------------

# 模块级常量表：(源码相对路径, ((变量名, 取哪些 dict 键), ...))
#   - 键为 None 表示取整个字面量里的全部字符串（常用于「值即文案」的映射表）；
#   - 键为元组表示只取这些 dict 键对应的值，避免把图标路径、task_id 等一起登记；
#   - 必须用 AST 读取、绝不 import —— 否则会把 PySide6 / qfluentwidgets 拖进工具链。
TABLE_SOURCES = [
    ("module/workflow/__init__.py", (("STEP_TYPE_LABELS", None), ("CONDITION_TYPE_LABELS", None))),
    ("module/update/version_check.py", (("_CDK_ERROR_MESSAGES", None),)),
    # 任务名与主页卡片文案：常量里存的是中文原文（msgid），显示时才 tr()
    ("utils/tasks.py", (("AVAILABLE_TASKS", None),)),
    ("app/card/card_edit_dialog.py", (
        ("HOME_EXTRA_TASKS", None),
        ("DEFAULT_CARDS", ("title", "label", "menu_items")),
    )),
]

# 取值会经 tr() 传入的数据文件（display_name 等展示字段即 msgid）
DATA_SOURCES = [
    "assets/config/character_names.json",
    "assets/config/instance_names.json",
    "assets/config/special_programs.jsonc",
]


def _collect_table_values(node: ast.AST, keys: tuple[str, ...] | None = None) -> set[str]:
    """递归取出常量表字面量里的文案。

    :param keys: 只取 dict 里这些键对应的值；为 None 时取所有值（键本身从不登记，
                 因为键通常是程序标识）。顺带支持值写成 tr("...") 的形式。
    """
    out: set[str] = set()
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str) and node.value.strip():
            out.add(node.value)
    elif isinstance(node, ast.Dict):
        for k, v in zip(node.keys, node.values):
            if keys is not None:
                if not (isinstance(k, ast.Constant) and k.value in keys):
                    continue
            out |= _collect_table_values(v, keys)
    elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        for v in node.elts:
            out |= _collect_table_values(v, keys)
    elif isinstance(node, ast.Call):
        func_name = _LiteralCollector._func_name(node.func) or ""
        idx = _LiteralCollector._msgid_index(func_name)
        if idx is not None and len(node.args) > idx:
            out |= _collect_table_values(node.args[idx], keys)
    return out


def collect_table_literals() -> tuple[set[str], dict[str, str]]:
    """读取 TABLE_SOURCES 声明的常量表字面量，返回 (字面量集合, 字面量 -> 来源)。"""
    literals: set[str] = set()
    refs: dict[str, str] = {}
    for rel, specs in TABLE_SOURCES:
        path = ROOT / rel
        if not path.is_file():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), str(path))
        except (SyntaxError, ValueError):
            continue
        by_name = {name: keys for name, keys in specs}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            else:
                continue
            matched = [t.id for t in targets if isinstance(t, ast.Name) and t.id in by_name]
            if not matched:
                continue
            if node.value is None:
                continue
            for value in _collect_table_values(node.value, by_name[matched[0]]):
                literals.add(value)
                refs.setdefault(value, f"{rel}:{node.lineno}")
    return literals, refs


def _load_jsonc(path) -> dict:
    """读取 JSON，容忍 .jsonc 的行注释与块注释。"""
    text = path.read_text(encoding="utf-8", errors="ignore")
    try:
        return json.loads(text)
    except Exception:
        pass
    stripped = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    stripped = re.sub(r"//[^\n]*", "", stripped)
    try:
        return json.loads(stripped)
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# 数据源字面量
# ---------------------------------------------------------------------------


def collect_data_literals() -> tuple[set[str], dict[str, str]]:
    """数据源驱动的翻译字面量（见 DATA_SOURCES）。

    返回 (字面量集合, 字面量 -> 来源文件)。instance_names 中「凝滞虚影」的 info
    按斜杠拆分后逐段登记，与 module.localization.get_instance_names 运行期一致；
    special_programs.jsonc 登记 special_programs[].display_name（schedule_dialog 经 tr() 传入）。
    """
    import re as _re

    literals: set[str] = set()
    refs: dict[str, str] = {}

    def add(text, ref):
        if isinstance(text, str) and text.strip():
            literals.add(text)
            refs.setdefault(text, ref)

    char_path = "assets/config/character_names.json"
    if char_path in DATA_SOURCES:
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

    sp_path = "assets/config/special_programs.jsonc"
    if sp_path in DATA_SOURCES:
        data = _load_jsonc(ROOT / sp_path)
        for prog in data.get("special_programs", []) or []:
            if isinstance(prog, dict):
                add(prog.get("display_name"), sp_path)

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


# ---------------------------------------------------------------------------
# 死键淘汰
# ---------------------------------------------------------------------------

LEGACY_WHITELIST_PATH = Path(__file__).resolve().parent / "legacy_keys.txt"


def legacy_whitelist() -> set[str]:
    """读取死键白名单（一行一个 msgid，'#' 起始为注释）。"""
    if not LEGACY_WHITELIST_PATH.is_file():
        return set()
    keys = set()
    for line in LEGACY_WHITELIST_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            keys.add(line)
    return keys


def prune_dead_keys(dry_run: bool = False) -> dict:
    """删除「未登记进 .pot」的死条目（历史遗留），返回各语言删除条数。

    判定：条目键不在 .pot 且不在 legacy_keys.txt 白名单里即为死键。
    TABLE_SOURCES / DATA_SOURCES 的取值经 extract 已进 .pot，不会被误删。
    只改 .po，删完需运行 compile 同步 .mo。
    """
    import polib

    from .po import entry_key, po_keyset, po_path, pot_path

    registered = po_keyset(polib.pofile(str(pot_path())))
    whitelist = legacy_whitelist()
    removed: dict[str, int] = {}
    for lang in LOCALES:
        path = po_path(lang)
        po = polib.pofile(str(path))
        dead = [e for e in po if entry_key(e) not in registered and entry_key(e) not in whitelist]
        if dead and not dry_run:
            for e in dead:
                po.remove(e)
            po.save(str(path))
        removed[lang] = len(dead)
    return removed


def run_checks() -> tuple[list[str], list[str]]:
    """校验翻译目录，返回 (错误列表, 警告列表)；错误非空即应视为失败。"""
    errors: list[str] = []
    warnings: list[str] = []
    _, formatted, _ = collect_code_literals()
    # tn() 的复数文案自带 str.format，占位符必须与译文严格一致，同样纳入严格集合
    plurals, _, _ = collect_code_extras()
    strict = formatted | plurals

    # 1) 需要 .format() 的文案禁止位置占位符（译文无法调整语序）
    for key in sorted(strict):
        if has_positional_placeholder(key):
            errors.append(f"位置占位符请改为命名占位符（key 长度 {len(key)}）")

    # 2) 多语言文档：表格行数一致、语言后缀命名合法、译文缺失 —— 仅警告
    warnings.extend(check_docs())

    # 3) gettext 目录（.pot/.po/.mo）
    try:
        from .po import check_po
        po_errors, po_warnings = check_po(strict)
        errors.extend(po_errors)
        warnings.extend(po_warnings)
    except Exception as e:
        errors.append(f"gettext 目录校验失败: {e}")

    return errors, warnings


# 界面实际加载的文档基名（help_interface / changelog_interface 经 localized_doc_path 读取）。
# 后缀登记校验、译文完整性校验、zh_TW 生成共用此清单，防止多处清单漂移。
DOC_BASES = ("Tutorial", "Workflow", "FAQ", "TasksTable", "Changelog")


def check_docs(docs_dir: Path | None = None) -> list[str]:
    """多语言文档校验（警告级）。

    - TasksTable 各语言版本表格行数须与基准版一致（防止改漏一份）
    - {Base}_{后缀}.md 的后缀须在 module.localization.languages 注册表声明
    - 帮助页/更新日志实际加载的文档，声明了 docs_suffix 的语言必须有对应译文
    """
    warnings: list[str] = []
    from module.localization.languages import LANGS

    if docs_dir is None:
        docs_dir = ROOT / "assets" / "docs"
    suffixes = {m["docs_suffix"] for m in LANGS.values() if m["docs_suffix"]}
    bases = DOC_BASES

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

    # 界面实际加载的文档（app/help_interface.py 与 changelog_interface.py 经 localized_doc_path 读取）
    for b in DOC_BASES:
        if not (docs_dir / f"{b}.md").is_file():
            continue  # 缺基准文档由其它校验负责
        for code, meta in LANGS.items():
            suf = meta["docs_suffix"]
            if not suf:
                continue
            if not (docs_dir / f"{b}_{suf}.md").is_file():
                warnings.append(f"文档 {b}_{suf}.md 缺失（{code} 用户将看到中文基准文档）")
    return warnings


# ---------------------------------------------------------------------------
# zh_TW 文档生成（繁体由简体基准机械转换，不需要人工翻译）
# ---------------------------------------------------------------------------

# 界面会加载的文档；zh_TW 版本由简体基准经 OpenCC s2twp 生成（清单与 DOC_BASES 同源）
ZH_TW_DOC_BASES = DOC_BASES

# 译文文档第 3 行的声明（界面按行号剥离，位置固定：第 1 行标题 / 第 2 行空行 / 第 3 行声明 / 第 4 行空行）
ZH_TW_DOC_NOTE = "> 本文件由簡體中文版經 OpenCC 簡繁轉換產生，用語以台灣習慣為準；內容如有差異，請以簡體中文版為準。"

# 纯表格文档不带声明（与其它语言保持一致）
ZH_TW_DOC_NO_NOTE = {"TasksTable"}


def render_zh_tw_doc(base: str, docs_dir: Path | None = None) -> str:
    """把简体基准文档渲染成 zh_TW 版本（OpenCC s2twp + 第 3 行声明）。"""
    from opencc import OpenCC

    docs_dir = Path(docs_dir) if docs_dir else ROOT / "assets" / "docs"
    lines = OpenCC("s2twp").convert((docs_dir / f"{base}.md").read_text(encoding="utf-8")).split("\n")
    if base not in ZH_TW_DOC_NO_NOTE:
        lines[2:2] = [ZH_TW_DOC_NOTE, ""]
    return "\n".join(lines)


def generate_zh_tw_docs(docs_dir: Path | None = None, write: bool = True) -> dict[str, bool]:
    """生成 assets/docs/*_zh_TW.md，返回 {文档基名: 是否需要更新}。

    简体基准改动后必须重新运行，否则繁体文档会落后于简体（tests 有守护用例）。
    """
    docs_dir = Path(docs_dir) if docs_dir else ROOT / "assets" / "docs"
    stale: dict[str, bool] = {}
    for base in ZH_TW_DOC_BASES:
        rendered = render_zh_tw_doc(base, docs_dir)
        dst = docs_dir / f"{base}_zh_TW.md"
        old = dst.read_text(encoding="utf-8") if dst.is_file() else None
        stale[base] = old != rendered
        if write and stale[base]:
            dst.write_text(rendered, encoding="utf-8", newline="\n")
    return stale
