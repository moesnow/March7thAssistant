"""Small lossless lexer for the command examples shipped with the manuals."""
import re

from .model import CodeToken

_FAMILY = {"sh": "bash", "shell": "bash", "ps1": "powershell", "pwsh": "powershell",
           "batch": "cmd", "bat": "cmd", "yml": "yaml"}
_KEYWORDS = {
    "bash": "if then else elif fi for in do done while case esac break continue export sudo cd echo",
    "powershell": "if else elseif foreach in while param function return try catch throw true false",
    "cmd": "if else for in do goto call set echo exit cd start",
    "yaml": "true false null yes no on off",
}
_KEYWORDS = {name: frozenset(words.split()) for name, words in _KEYWORDS.items()}
_STRINGS = r"""(?P<string>"(?:\\.|[^"\\\n])*"|'(?:''|\\.|[^'\\\n])*')"""
_WORDS = r"(?P<number>(?<![\w.])\d+(?:\.\d+)?(?![\w.]))|(?P<word>[\w-]+)"
_LEXERS = {name: re.compile(comment + "|" + _STRINGS + "|" + _WORDS, re.M | re.I) for name, comment in (
    ("bash", r"(?P<comment>(?<!\S)#[^\n]*)"), ("yaml", r"(?P<comment>(?<!\S)#[^\n]*)"),
    ("powershell", r"(?P<comment>#[^\n]*)"), ("cmd", r"(?P<comment>^[ \t]*@?(?:rem\b|::)[^\n]*)"),
)}


def color_code(language, text):
    name = _FAMILY.get(language.lower(), language.lower())
    if name not in _LEXERS:
        return (CodeToken("plain", text),) if text else ()
    tokens, cursor = [], 0
    for match in _LEXERS[name].finditer(text):
        kind = match.lastgroup
        if kind == "word":
            if match[0].lower() not in _KEYWORDS[name]:
                continue
            kind = "keyword"
        if cursor < match.start():
            tokens.append(CodeToken("plain", text[cursor:match.start()]))
        tokens.append(CodeToken(kind, match[0]))
        cursor = match.end()
    if cursor < len(text):
        tokens.append(CodeToken("plain", text[cursor:]))
    return tuple(tokens)
