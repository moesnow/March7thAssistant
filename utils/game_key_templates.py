from functools import lru_cache
from pathlib import Path
from string import ascii_lowercase, digits


PROMPT_KEY_DEFAULTS = {
    "hotkey_interact": "f",
    "hotkey_character_details": "c",
}
_FUNCTION_KEYS = tuple(f"f{number}" for number in range(1, 13))
_F1_PREFIX_KEYS = frozenset(_FUNCTION_KEYS[9:])
_PROMPT_KEYS = frozenset(ascii_lowercase + digits) | {"space", *_FUNCTION_KEYS}
_TEMPLATE_ROOT = "./assets/images/share/base/key_prompts"
_MATCH_THRESHOLD = 0.9

# 分数接近的字形需在同一键帽位置核对，避免在错误的提示上发送按键。
_LOOKALIKES = (tuple("dgoq"), tuple("08"), tuple("1i"), tuple("efp"), _FUNCTION_KEYS)


def key_prompt_path(key: str | None) -> str | None:
    if not isinstance(key, str) or key not in _PROMPT_KEYS:
        return None
    path = f"{_TEMPLATE_ROOT}/{key}.png"
    return path if Path(path).is_file() else None


@lru_cache(maxsize=len(_PROMPT_KEYS))
def _read_prompt_template(path):
    from utils.image_utils import ImageUtils

    return ImageUtils.read_image(path)


def find_key_prompt(auto, key: str, crop, *, legacy_f=None, scale_range=None):
    """在指定区域查找已配置的键帽。默认 F 可沿用调用方原有模板。"""
    if key == "f" and legacy_f is not None:
        return auto.find_element(legacy_f, "image", _MATCH_THRESHOLD, crop=crop)
    path = key_prompt_path(key)
    if path is None:
        return None
    matched = auto.find_element(path, "image", _MATCH_THRESHOLD, crop=crop, relative=True, scale_range=scale_range)
    rivals = next((group for group in _LOOKALIKES if key in group), ())
    if not matched or not rivals:
        return matched

    import cv2
    import numpy as np
    from utils.image_utils import ImageUtils

    template = _read_prompt_template(path)
    if template is None:
        return None
    rival_templates = []
    for rival in rivals:
        if rival == key or (rival == "f1" and key in _F1_PREFIX_KEYS):
            continue
        rival_path = key_prompt_path(rival)
        rival_template = _read_prompt_template(rival_path) if rival_path else None
        if rival_template is not None:
            rival_templates.append((rival, rival_template))

    # F1 与 F10 至 F12 的键帽宽度不同，核对时需保留候选的完整字形。
    width = template.shape[1]
    widest = max((item.shape[1] for _, item in rival_templates), default=width)
    horizontal_padding = 2 + max(0, widest - width)
    (left, top), (right, bottom) = matched
    region = np.asarray(auto.screenshot)[max(0, top - 2):bottom + 2,
                                         max(0, left - horizontal_padding):right + horizontal_padding]
    if region.shape[0] < template.shape[0] or region.shape[1] < width:
        return None
    region = cv2.cvtColor(region, cv2.COLOR_RGB2BGR)
    score, _ = ImageUtils.scale_and_match_template(region, template, scale_range=scale_range)
    for rival, rival_template in rival_templates:
        if region.shape[0] < rival_template.shape[0] or region.shape[1] < rival_template.shape[1]:
            continue
        rival_score, _ = ImageUtils.scale_and_match_template(region, rival_template, scale_range=scale_range)
        # 较短的 F1 前缀在战斗 HUD 上可能分数更高，完整键帽优先。
        rival_threshold = _MATCH_THRESHOLD if key == "f1" and rival in _F1_PREFIX_KEYS else score - 0.015
        if rival_score >= rival_threshold:
            return None
    return matched


def find_interact_prompt(auto, key: str, *, compact=False):
    if compact:
        left = 1040 if key == "space" or key in _FUNCTION_KEYS else 1078
        crop = (left / 1920, 595 / 1080, (1115 - left) / 1920, 37 / 1080)
        legacy_f = "./assets/images/screen/divergent_universe/f.png"
    else:
        crop = (998 / 1920, 473 / 1080, 392 / 1920, 296 / 1080)
        legacy_f = "./assets/images/share/base/F.png"
    return find_key_prompt(auto, key, crop, legacy_f=legacy_f)


def find_character_details_prompt(auto, key: str):
    # 战斗 HUD 左下角键帽比按键设置和大世界交互提示小。
    crop = (0, 898 / 1080, 78 / 1920, 58 / 1080)
    return find_key_prompt(auto, key, crop, scale_range=(0.75, 0.9))
