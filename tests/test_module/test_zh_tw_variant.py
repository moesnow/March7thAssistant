# coding:utf-8
"""繁体回退的用语口径守护测试。

约定：zh_TW 的运行期回退（_s2t）与文档生成（render_zh_tw_doc）同用 OpenCC s2twp，
统一产出台湾用语，避免「軟件（机械字形）」与「軟體（文档）」两套用语并存。
样例均为通用词汇，不引用项目译文。
"""
import pytest

from module.localization import _s2t


class TestZhTwTaiwanVocabulary:
    def test_it_terms_use_taiwan_vocabulary(self):
        samples = {
            "软件更新": "軟體更新",
            "网络设置": "網路設定",
            "鼠标点击": "滑鼠點選",
            "文件夹": "資料夾",
            "内存不足": "記憶體不足",
            "服务器": "伺服器",
        }
        for src, expected in samples.items():
            got = _s2t(src)
            if got != expected:
                pytest.fail(f"繁体回退应产出台湾用语（{src} -> {expected}）")

    def test_same_shape_text_unchanged(self):
        # 简繁同形文案转换后不变 —— 这是合法结果，不得被当作转换失败
        assert _s2t("最高置信度") == "最高置信度"

    def test_opencc_unavailable_returns_none(self, monkeypatch):
        import module.localization as loc

        def boom(*a, **k):
            raise RuntimeError("no opencc")
        monkeypatch.setattr(loc, "OpenCC", boom, raising=False)
        monkeypatch.setattr("opencc.OpenCC", boom)
        monkeypatch.setattr(loc, "_s2t_converter", None)  # 模拟首次构造
        assert _s2t("任意") is None
