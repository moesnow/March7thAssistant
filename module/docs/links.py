"""Classify links at parse time. Rendering code dispatches solely by Link.kind."""
from urllib.parse import parse_qs, unquote, urlsplit
import re

from module.localization.languages import LANGS

from .catalog import DOCUMENTS, source_for
from .model import Link

_IDS = {name.casefold(): name for name in DOCUMENTS}


def classify_link(url, source):
    from module.navigation import parse_link
    from .reader import resolve_anchor

    def document(name, anchor="", *, web=False, written_language=None):
        if not name or (name != source.id and name not in DOCUMENTS):
            return None
        dest = source if name == source.id else source_for(name, source.language)
        if not dest.path.is_file():
            return None
        resolved = resolve_anchor(dest, anchor, web=web, written_language=written_language) if anchor else ""
        if anchor and not resolved and not web:
            return None
        return Link("doc", "doc:" + name + ("#" + resolved if resolved else ""))

    try:
        parts = urlsplit(url)
        scheme = parts.scheme.lower()
        official = scheme in ("http", "https") and parts.netloc.lower() == "m7a.top"
        web = ((official and parts.path in ("", "/", "/docs", "/docs/")) or
               (not scheme and not parts.netloc and not parts.path)) and parts.fragment.startswith("/assets/docs/")
        if web:
            route = urlsplit(parts.fragment)
            path = route.path
            anchor = parse_qs(route.query).get("id", [""])[0]
        elif scheme in ("http", "https"):
            return Link("external", url) if parts.hostname else None
        elif scheme == "mailto":
            return Link("external", url) if parts.path else None
        elif scheme == "doc":
            name = _IDS.get(unquote(parts.path).casefold())
            return document(name, parts.fragment)
        elif scheme:
            return Link("app", url) if parse_link(url) else None
        elif parts.netloc or parts.query:
            return None
        elif not parts.path:
            return document(source.id, parts.fragment) if parts.fragment else None
        else:
            path, anchor = parts.path, parts.fragment
        match = re.fullmatch(r"(?:/assets/docs/|\./)?([\w-]+?)(?:\.md)?", unquote(path), re.I)
        if not match:
            return None
        stem = match[1]
        lang = next((code for code in LANGS if stem.endswith("_" + code)), None)
        name = _IDS.get((stem.removesuffix("_" + lang) if lang else stem).casefold())
        return document(name, anchor, web=web, written_language=lang)
    except (ValueError, UnicodeError):
        return None
