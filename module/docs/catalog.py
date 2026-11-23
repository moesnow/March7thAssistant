"""Desktop sidebar order, local manuals and their published docsify routes."""
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from module.localization.languages import LANGS, localized_doc_path


@dataclass(frozen=True, slots=True)
class Manual:
    id: str
    name: str
    icon: str
    kind: str = "article"


SIDEBAR = (
    Manual("Tutorial", "使用教程", "FIF.BOOK_SHELF"),
    Manual("FAQ", "常见问题", "FIF.HELP", "faq"),
    Manual("Background", "后台运行", "FIF.GAME"),
    Manual("Workflow", "流程编排", "FIF.CODE"),
    Manual("TasksTable", "每日实训对照表", "UiIcon.CLIPBOARD_TASK", "table"),
    Manual("Changelog", "更新日志", "FIF.UPDATE", "changelog"),
)
RELATED = (
    Manual("Android", "安卓版教程", "FIF.PHONE"),
    Manual("Agent", "AI 助手", "FIF.ROBOT"),
    Manual("DesktopTwin", "桌面分身", "FIF.CONNECT"),
    Manual("Docker", "Docker 部署", "FIF.COMMAND_PROMPT"),
    Manual("Termux", "Termux 安卓部署", "FIF.COMMAND_PROMPT"),
)
DOCUMENTS = {manual.id: manual for manual in (*SIDEBAR, *RELATED)}


@dataclass(frozen=True, slots=True)
class Source:
    id: str
    language: str
    path: Path

    @property
    def stamp(self) -> tuple[int, int]:
        try:
            stat = self.path.stat()
            return stat.st_mtime_ns, stat.st_size
        except OSError:
            return 0, -1


def source_for(doc_id: str, language: str | None = None) -> Source:
    manual = DOCUMENTS[doc_id]
    path = Path(localized_doc_path(manual.id, language)).absolute()
    suffix = path.stem.removeprefix(manual.id + "_")
    return Source(manual.id, suffix if suffix in LANGS else "zh_CN", path)


def website_url(doc_id: str, anchor: str = "", language: str | None = None) -> str:
    source = source_for(doc_id, language)
    url = "https://m7a.top/docs/#/assets/docs/" + source.path.stem
    if anchor:
        from .reader import website_anchor
        web_id = website_anchor(source, anchor)
        if web_id:
            # docsify 4.13.1 lowercases encodeURIComponent(key=value).
            url += "?id=" + quote(web_id, safe="-_.!~*'()").lower()
    return url


def current_version() -> str:
    from utils.cli_entry import read_version
    return read_version()
