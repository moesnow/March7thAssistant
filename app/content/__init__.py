"""Public construction entry point for settings and task details."""
from importlib import import_module

from module.content_pages import PAGES, PAGE_BY_ID
from .base import PageHost, Section


def build_page(page_id: str, host: PageHost) -> list[Section]:
    page = PAGE_BY_ID[page_id]
    package = {"setting": "settings", "task": "tasks"}[page.kind]
    return import_module(f"app.content.{package}.{page_id}").build(host)
