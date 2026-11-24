"""Public construction entry point for settings and task details."""
from module.content_pages import PAGES, PAGE_BY_ID
from .base import PageHost, Section


def build_page(page_id: str, host: PageHost) -> list[Section]:
    # 各页模块依赖本包的 base、backend，所以到这里才导入；写成 import 语句，PyInstaller 才会把它们打进发布包。
    from . import settings, tasks

    page = PAGE_BY_ID[page_id]
    package = {"setting": settings, "task": tasks}[page.kind]
    return getattr(package, page_id).build(host)
