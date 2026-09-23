"""轻量级版本号解析与比较（替代 packaging.version 的版本比较用途）。

完整实现 PEP 440 的排序语义，覆盖本项目历史发布使用过的版本号写法：

- ``2026.4.28-beta`` / ``2.0.6-beta1``：beta 预发布，小于同版本号的正式版
- ``2.7.0-pre`` / ``2.7.0-pre2``：pre 是 rc 的别名，按 rc 排序
- ``2026.4.30-1``：隐式 post 发布（等价于 ``2026.4.30.post1``），大于 ``2026.4.30``
- ``1.3.0.1``：四段数字版本
- ``3.7.0`` 与 ``3.7`` 视为相等（末尾 0 不参与比较）

排序规则：dev < alpha < beta < rc < 正式版 < post；
后缀分隔符 ``-`` ``_`` ``.`` 等价，大小写不敏感，允许前缀 v/V。
无法识别的后缀不会导致解析失败，退化为按数字部分比较。
"""
import re
from functools import total_ordering

# PEP 440 版本号格式（简化但排序语义完整）
_VERSION_PATTERN = re.compile(
    r"""^\s*v?
    (?:(?P<epoch>[0-9]+)!)?
    (?P<release>[0-9]+(?:\.[0-9]+)*)
    (?:
        [-_.]*
        (?P<pre_l>alpha|a|beta|b|preview|pre|rc|c)
        [-_.]*
        (?P<pre_n>[0-9]+)?
    )?
    (?:
        (?:-(?P<implicit_post_n>[0-9]+))
        |
        (?:
            [-_.]*
            (?P<post_l>post|rev|r)
            [-_.]*
            (?P<post_n>[0-9]+)?
        )
    )?
    (?:[-_.]*(?P<dev_l>dev)[-_.]*(?P<dev_n>[0-9]+)?)?
    (?:\+(?P<local>[a-z0-9]+(?:[-_.][a-z0-9]+)*))?
    \s*$""",
    re.VERBOSE | re.IGNORECASE,
)

# 无法完全识别时的兜底：提取开头的数字部分
_LENIENT_PATTERN = re.compile(r"^\s*v?(\d+(?:\.\d+)*)", re.IGNORECASE)

# 预发布后缀别名（PEP 440：pre/preview/c 都是 rc 的别名）
_PRE_ALIASES = {"alpha": "a", "a": "a", "beta": "b", "b": "b", "preview": "rc", "pre": "rc", "rc": "rc", "c": "rc"}
_PRE_RANK = {"a": 0, "b": 1, "rc": 2}


@total_ordering
class Version:
    """解析并比较版本号。用法与 packaging.version.Version 保持一致：

    >>> Version("2026.4.28-beta") < Version("2026.4.28")
    True

    :param text: 版本号字符串，可带 v 前缀。
    :raises ValueError: 版本号不含数字部分、无法解析时抛出。
    """

    def __init__(self, text):
        self._text = str(text).strip()
        match = _VERSION_PATTERN.match(self._text)
        if match:
            self._epoch = int(match.group("epoch") or 0)
            self._release = self._normalize_release(match.group("release"))
            pre_l = match.group("pre_l")
            self._pre = (_PRE_ALIASES[pre_l.lower()], int(match.group("pre_n") or 0)) if pre_l else None
            if match.group("implicit_post_n") is not None:
                # 隐式 post（2026.4.30-1）与显式 post（2026.4.30.post1）等价
                self._post = int(match.group("implicit_post_n"))
            elif match.group("post_l"):
                self._post = int(match.group("post_n") or 0)
            else:
                self._post = None
            self._dev = int(match.group("dev_n") or 0) if match.group("dev_l") else None
            self._local = bool(match.group("local"))
        else:
            # 兜底：按开头数字部分比较，忽略无法识别的后缀，避免解析失败
            fallback = _LENIENT_PATTERN.match(self._text)
            if not fallback:
                raise ValueError(f"无效的版本号: {self._text}")
            self._epoch = 0
            self._release = self._normalize_release(fallback.group(1))
            self._pre = None
            self._post = None
            self._dev = None
            self._local = False

    @staticmethod
    def _normalize_release(release: str):
        """将数字部分转为元组并去除末尾的 0（3.7.0 与 3.7 相等）。"""
        parts = [int(part) for part in release.split(".")]
        while parts and parts[-1] == 0:
            parts.pop()
        return tuple(parts)

    def _cmp_key(self):
        """生成比较键，排序语义与 PEP 440 一致。"""
        # 预发布阶段：纯 dev 版本排在所有预发布之前，无预发布则排在之后
        if self._pre is None and self._post is None and self._dev is not None:
            pre_key = (0,)
        elif self._pre is None:
            pre_key = (2,)
        else:
            pre_key = (1, _PRE_RANK[self._pre[0]], self._pre[1])
        # post 版本大于无 post 的版本（隐式 post 与显式 post 等价）
        post_key = (1, self._post) if self._post is not None else (0,)
        # dev 版本小于对应的正式版本
        dev_key = (0, self._dev) if self._dev is not None else (1,)
        local_key = (1,) if self._local else (0,)
        return self._epoch, self._release, pre_key, post_key, dev_key, local_key

    def __eq__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
        return self._cmp_key() == other._cmp_key()

    def __lt__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
        return self._cmp_key() < other._cmp_key()

    def __hash__(self):
        return hash(self._cmp_key())

    def __str__(self):
        return self._text

    def __repr__(self):
        return f"Version({self._text!r})"
