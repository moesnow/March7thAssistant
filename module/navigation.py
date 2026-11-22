"""Parse desktop navigation targets without importing the GUI."""
from urllib.parse import unquote


def parse_link(link: str) -> tuple[str, str, str] | None:
    if not isinstance(link, str):
        return None
    kind, colon, target = link.partition(':')
    page, fragment, anchor = target.partition('#')
    if not colon or kind not in ('setting', 'task', 'doc') or not page.strip():
        return None
    if kind == 'setting' and fragment:
        return None
    return kind, unquote(page), unquote(anchor)
