"""发布包由 PyInstaller 静态收集模块，运行时拼出来的模块名不会进包"""
import ast
from pathlib import Path
import sys

import pytest

from module.content_pages import PAGES

ROOT = Path(__file__).parents[2]


def _tree(path):
    return ast.parse(path.read_text(encoding="utf-8"), str(path))


def test_packaged_code_names_modules_in_import_statements():
    sources = [ROOT / name for name in ("app.py", "main.py", "updater.py")]
    for package in ("app", "module", "tasks", "utils"):
        sources += sorted((ROOT / package).rglob("*.py"))

    dynamic = []
    for path in sources:
        for node in ast.walk(_tree(path)):
            if not isinstance(node, ast.Call):
                continue
            if getattr(node.func, "attr", getattr(node.func, "id", "")) not in ("import_module", "__import__"):
                continue
            target = node.args[0] if node.args else None
            if not (isinstance(target, ast.Constant) and target.value in sys.stdlib_module_names):
                dynamic.append(f"{path.relative_to(ROOT).as_posix()}:{node.lineno}")
    assert dynamic == []


@pytest.mark.parametrize("kind, package", [("setting", "settings"), ("task", "tasks")])
def test_content_packages_import_every_page(kind, package):
    tree = _tree(ROOT / "app" / "content" / package / "__init__.py")
    imported = {alias.name for node in tree.body if isinstance(node, ast.ImportFrom) for alias in node.names}
    assert imported == {page.id for page in PAGES if page.kind == kind}
