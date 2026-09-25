import re

import build

# 已发布旧版客户端内置的推广块清理正则（按文案 + \r\n\r\n 锚点匹配）。
# 新的发布产物必须保持可被该正则匹配，否则旧版客户端的更新弹窗会展示推广块。
_LEGACY_PROMO_RE = re.compile(
    r"\r\n\r\n\[.*?Mirror酱.*?CDK.*?下载\]\(https?://.*?mirrorchyan\.com[^\)]*\)",
    flags=re.IGNORECASE,
)


class TestGenerateChangelog:
    def _generate(self, tmp_path, monkeypatch):
        monkeypatch.setattr(build, "get_changelog", lambda version: "- 更新内容")
        out = tmp_path / "changelog.md"
        build.generate_changelog("v0.0.0", out)
        # 模拟 GitHub API 的换行归一化
        return out.read_text(encoding="utf-8").replace("\n", "\r\n")

    def test_promo_block_wrapped_in_hidden_markers(self, tmp_path, monkeypatch):
        body = self._generate(tmp_path, monkeypatch)
        assert "<!-- m7a:hide -->" in body
        assert "<!-- /m7a:hide -->" in body

    def test_promo_block_matches_legacy_client_regex(self, tmp_path, monkeypatch):
        body = self._generate(tmp_path, monkeypatch)
        assert _LEGACY_PROMO_RE.search(body)
        cleaned = _LEGACY_PROMO_RE.sub("", body)
        assert "mirrorchyan" not in cleaned
