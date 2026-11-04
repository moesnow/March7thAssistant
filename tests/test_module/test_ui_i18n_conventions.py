# coding:utf-8
"""界面文案的多语言约定守护（对应 I18N.md 第二节）。

两条约定：

1. **界面调用里的中文必须套 `tr()`**：`setText` / `setWindowTitle` / `InfoBar(error=…)` /
   `TeachingTip.create(title=…)` / `_show_msg(...)` 之类会把文本显示给用户，直接写中文字面量
   就等于该处永不翻译。
   例外（有意为之，不检查）：
   - 日志调用（`log.info` / `self._log` / `appendLog` 等）按约定记中文原文；
   - 通知正文（`notify(...)`、`send_notification_with_screenshot(...)`）：通知模块自身完全不翻译，
     全仓库调用点都传中文，是否整体本地化尚未决策，故不纳入守护。

2. **包装器不翻译，调用点负责 `tr()`**：像 `_show_msg(parent, title, content)`、
   `InfoBar.error(title=..., content=...)` 这类包装器/组件的入参应当由调用点传入已翻译文本。
   若包装器对入参再 `tr()` 一次，调用点已翻译的文本会二次查表、命中不到条目，
   既浪费又会在 DEBUG 日志里刷「缺失翻译」。
   例外（有意为之）：
   - `app/card/card_edit_dialog.py::display_label()`：入参本身就是 msgid（常量/配置里存的中文原文），
     由它负责解析成当前语言；
   - `module/localization/trc()`：无 msgctxt 条目时回退 `tr()`。
"""
import ast
import re

from tools.i18n import iter_source_files

CJK = re.compile(r"[\u3400-\u9fff]")

# ---- 约定 1 的扫描规则 ----
LOG_CALLEES = {"log", "logger", "self.logger", "self._log", "_log", "self.log"}
UI_ATTRS = {
    "setText", "setPlaceholderText", "setToolTip", "setWindowTitle", "setTitle",
    "addItem", "addItems", "setLabel", "setContent", "setSubtitle", "setCaption",
    "setInformativeText", "setDetailedText", "setStatusTip", "setWhatsThis",
}
UI_INFO_OBJECTS = {"InfoBar", "TeachingTip"}
UI_INFO_KW = {"text", "title", "content", "caption", "label", "placeholder",
              "yesButtonText", "cancelButtonText", "subtitle", "description"}

# ---- 约定 2 的允许例外 ----
WRAPPER_ALLOWLIST = {
    ("app/card/card_edit_dialog.py", "display_label"),      # 入参是 msgid，本就是由它解析
    ("module/localization/__init__.py", "trc"),              # 无 msgctxt 条目时回退 tr()
}


def _dotted(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}"
    return "?"


def _callee(call: ast.Call):
    """返回 (点分调用者名, 属性名)。"""
    f = call.func
    if isinstance(f, ast.Attribute):
        return _dotted(f.value), f.attr
    if isinstance(f, ast.Name):
        return f.id, f.id
    return "", ""


def _wrapped_string_ids(tree) -> set[int]:
    """被 tr()/tn()/trc() 包裹的字符串常量的 id 集合。"""
    wrapped = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _callee(node)[1] in ("tr", "tn", "trc"):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    wrapped.add(id(arg))
    return wrapped


def _is_log_call(dotted: str) -> bool:
    return (dotted in LOG_CALLEES
            or dotted.startswith("log.")
            or dotted.startswith("self.logger")
            or dotted.startswith("self._log")
            or dotted.endswith(".appendLog"))


def _parsed_sources():
    for path in iter_source_files():
        source = path.read_text(encoding="utf-8", errors="ignore")
        try:
            tree = ast.parse(source, str(path))
        except (SyntaxError, ValueError):
            continue
        rel = str(path).replace("\\", "/").split("March7thAssistant/")[-1]
        yield rel, tree


class TestUiLiteralsAreTranslated:
    def test_no_raw_chinese_in_ui_calls(self):
        offenders = []
        for rel, tree in _parsed_sources():
            wrapped = _wrapped_string_ids(tree)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                dotted, attr = _callee(node)
                if _is_log_call(dotted):
                    continue
                candidates = []
                if attr in UI_ATTRS:
                    candidates += list(node.args)
                if dotted.split(".")[0] in UI_INFO_OBJECTS or attr == "_show_msg":
                    candidates += list(node.args)
                    candidates += [kw.value for kw in node.keywords if kw.arg in UI_INFO_KW]
                for arg in candidates:
                    if (isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                            and CJK.search(arg.value) and id(arg) not in wrapped):
                        offenders.append(f"{rel}:{node.lineno} {dotted}(...) {arg.value[:40]!r}")
        assert offenders == [], (
            "界面文案必须套 tr()（日志与通知正文除外，见本测试文件顶部说明）:\n"
            + "\n".join(offenders)
        )


class TestNoWrapperRetranslation:
    def test_wrapper_does_not_translate_its_own_param(self):
        offenders = []
        for rel, tree in _parsed_sources():
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if (rel, node.name) in WRAPPER_ALLOWLIST:
                    continue
                args = node.args
                params = {a.arg for a in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)}
                if args.vararg:
                    params.add(args.vararg.arg)
                if args.kwarg:
                    params.add(args.kwarg.arg)
                if not params:
                    continue
                for sub in ast.walk(node):
                    if not (isinstance(sub, ast.Call) and _callee(sub)[1] in ("tr", "tn", "trc")):
                        continue
                    if any(isinstance(a, ast.Name) and a.id in params for a in sub.args):
                        offenders.append(f"{rel}:{sub.lineno} 函数 {node.name}() 对入参再翻译一次")
                        break
        assert offenders == [], (
            "包装器不应翻译自己的入参（调用点负责 tr()）:\n" + "\n".join(offenders)
        )
