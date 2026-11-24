"""Resolve desktop links without importing a GUI or the user's configuration."""
from dataclasses import dataclass
from urllib.parse import unquote

from module.content_pages import PAGE_BY_ID
from module.docs.catalog import DOCUMENTS
from module.settings_registry import Setting, find_setting
from module.tool_catalog import TOOL_BY_ID

TOP_PAGES = {
    "overview": ("总览", "homeInterface", "FIF.HOME"),
    "tasks": ("任务", "taskInterface", "UiIcon.CLIPBOARD_TASK"),
    "run": ("运行", "logInterface", "FIF.COMMAND_PROMPT"),
    "warp": ("抽卡记录", "warpInterface", "FIF.SHARE"),
    "tools": ("工具箱", "toolsInterface", "FIF.DEVELOPER_TOOLS"),
    "workflow": ("流程编排", "workflowInterface", "FIF.CODE"),
    "help": ("帮助", "helpInterface", "FIF.BOOK_SHELF"),
    "accounts": ("账号", "accountsInterface", "FIF.PEOPLE"),
    "settings": ("设置", "settingInterface", "FIF.SETTING"),
}


def parse_link(link: str) -> tuple[str, str, str] | None:
    if not isinstance(link, str):
        return None
    kind, colon, target = link.partition(":")
    page, fragment, anchor = target.partition("#")
    page, anchor = unquote(page), unquote(anchor)
    if not colon or not page.strip() or fragment and (kind not in ("doc", "task") or not anchor):
        return None
    if kind == "setting" and page == "scheduled_time":
        return ("run", "schedule", "")
    if kind == "run":
        from utils.runs import is_valid_run_id
        valid = page in ("current", "schedule", "history") or is_valid_run_id(page)
    elif kind == "setting":
        valid = find_setting(page) is not None
    elif kind == "category":
        valid = page in PAGE_BY_ID and PAGE_BY_ID[page].kind == "setting"
    elif kind == "task":
        item = find_setting(anchor)
        valid = page in PAGE_BY_ID and PAGE_BY_ID[page].kind == "task" and (not anchor or item and item.page == page)
    elif kind == "doc":
        page = next((name for name in DOCUMENTS if name.casefold() == page.casefold()), "")
        valid = bool(page)
    elif kind == "page":
        valid = page in TOP_PAGES
    elif kind == "tool":
        valid = page in TOOL_BY_ID
    else:
        return None
    return (kind, page, anchor) if valid else None


@dataclass(frozen=True)
class Target:
    interface: str
    page: str
    item: Setting | None = None
    anchor: str = ""
    kind: str = "page"


def resolve_link(link):
    route = parse_link(link)
    if route is None:
        return None
    kind, name, anchor = route
    if kind in ("setting", "task"):
        item = find_setting(name if kind == "setting" else anchor)
        page = item.page if item else name
        if page == "run":
            return Target("logInterface", "schedule", kind="run")
        attr = "taskInterface" if PAGE_BY_ID[page].kind == "task" else "settingInterface"
        return Target(attr, page, item, kind=kind)
    if kind == "page":
        return Target(TOP_PAGES[name][1], name)
    attr = {"doc": "helpInterface", "category": "settingInterface", "tool": "toolsInterface", "run": "logInterface"}
    return Target(attr[kind], name, anchor=anchor, kind=kind)
