from unittest.mock import Mock

import pytest

from tasks.daily import synthesis


def _ocr_lines(*texts):
    return [([(0, i * 24), (100, i * 24), (100, i * 24 + 20), (0, i * 24 + 20)], (text, 0.99)) for i, text in enumerate(texts)]


@pytest.mark.parametrize("texts", [
    ("252/3", "合成数量：1", "84", "+"),
    ("4929/3", "合成数量：1", "1643", "+"),
    ("162/3", "合成数量：1", "54", "+"),
    ("252/3", "合成数量：", "1", "84", "+"),
])
def test_verify_training_recipe_ignores_adjacent_max_craft_count(monkeypatch, texts):
    fake_auto = Mock()
    fake_auto.find_element.return_value = ((0, 0), (1, 1))
    fake_auto.ocr_result = _ocr_lines(*texts)
    monkeypatch.setattr(synthesis, "auto", fake_auto)

    assert synthesis.Synthesis._verify_training_recipe() is True


@pytest.mark.parametrize("texts", [
    ("252/3", "合成数量：2", "84", "+"),
    ("252/3", "合成数量：10", "84", "+"),
    ("2/3", "合成数量：1", "0", "+"),
    ("252/3", "84", "+"),
])
def test_verify_training_recipe_rejects_wrong_amount_or_insufficient_materials(monkeypatch, texts):
    fake_auto = Mock()
    fake_auto.find_element.return_value = ((0, 0), (1, 1))
    fake_auto.ocr_result = _ocr_lines(*texts)
    monkeypatch.setattr(synthesis, "auto", fake_auto)

    assert synthesis.Synthesis._verify_training_recipe() is False


def test_verify_training_recipe_aborts_if_title_missing(monkeypatch):
    fake_auto = Mock()
    fake_auto.find_element.return_value = None
    monkeypatch.setattr(synthesis, "auto", fake_auto)

    assert synthesis.Synthesis._verify_training_recipe() is False
    fake_auto.perform_ocr.assert_not_called()
