"""Rebuild native Currency Wars runtime flags from the resumed game UI.

Only reads the ordinary layout and, when present, the selected strategy's core
panel. It never buys, sells, equips, starts a match or settles a saved run.
"""

import re
import time


POPULATION_CROP = (848 / 1920, 206 / 1080, 231 / 1920, 79 / 1080)
NAME_CROP = (1493 / 1920, 213 / 1080, 299 / 1920, 30 / 1080)
STARS_CROP = (1566 / 1920, 158 / 1080, 126 / 1920, 31 / 1080)
EQUIPMENT_CROPS = tuple((x / 1920, 782 / 1080, 73 / 1920, 73 / 1080)
                        for x in (1608, 1695, 1782))
STAR_IMAGE = "./assets/images/screen/currency_wars/resume_star.png"
EMPTY_IMAGE = "./assets/images/screen/currency_wars/empty_equipment.png"
GEAR_IMAGES = {
    "shoe": "./assets/images/share/aglaea/shoe.png",
    "boots": "./assets/images/share/aglaea/boots.png",
    "propeller": "./assets/images/share/aglaea/propeller.png",
    "firestorm": "./assets/images/share/aglaea/firestorm.png",
    "chainsaw": "./assets/images/share/aglaea/chainsaw.png",
}


def empty_equipment_colors_match(image, reference):
    """Color-distance check supplements correlation on nearly uniform slots."""
    from PIL import ImageChops
    image = image.convert("RGB").resize(reference.size)
    histogram = ImageChops.difference(image, reference.convert("RGB")).histogram()
    pixels = reference.width * reference.height
    if not pixels:
        return False
    means = [sum(value * count for value, count in enumerate(histogram[channel * 256:(channel + 1) * 256])) / pixels
             for channel in range(3)]
    return max(means) <= 14


def _empty_slot(auto, index):
    from PIL import Image
    crop = ((1620, 1707, 1793)[index] / 1920, 794 / 1080, 47 / 1920, 47 / 1080)
    if not auto.take_screenshot(crop=crop):
        raise RuntimeError("续跑状态恢复失败：无法读取空装备槽颜色")
    image = auto.screenshot.copy()
    if not auto.find_element(EMPTY_IMAGE, "image", 0.94, take_screenshot=False, need_ocr=False):
        return False
    with Image.open(EMPTY_IMAGE) as reference:
        return empty_equipment_colors_match(image, reference)


def _read_layout(war, auto):
    if not war.get_level() or type(war.current_level) is not int or not 3 <= war.current_level <= 10:
        raise RuntimeError("续跑状态恢复失败：未识别当前小队等级，保留对局")
    text = auto.get_single_line_text(crop=POPULATION_CROP, blacklist=["等级提升", "金币不足"])
    match = re.fullmatch(r"\s*[iI:]?\s*(\d+)\s*/\s*(\d+)\s*", text or "")
    if not match:
        raise RuntimeError("续跑状态恢复失败：未识别当前团队规模，保留对局")
    used, limit = map(int, match.groups())
    if used > limit or limit != war.current_level:
        # Existing native slot coordinates depend on history-only Peppy/Chirpy
        # and diamond counters. Do not guess those counters after a restart.
        raise RuntimeError("续跑状态恢复失败：存在额外或未知工位，尚不能还原后台布局，保留对局")
    war.peipei_count = 0
    war.diamond_count = 0
    war.update_backward()
    return used


def _core_positions(war, name):
    deployed, bench = [], []
    for zone in ("forward", "backward", "prepare"):
        characters = getattr(war, zone + "_characters")
        positions = getattr(war, zone + "_pos")
        for index, character in enumerate(characters):
            if character.name == name:
                if index >= len(positions):
                    raise RuntimeError("续跑状态恢复失败：核心工位与角色列表不一致")
                (bench if zone == "prepare" else deployed).append(positions[index])
    # Native equip methods address the deployed core by name. More than one
    # deployed copy cannot be assigned a reliable inventory counter here.
    if len(deployed) > 1:
        raise RuntimeError("续跑状态恢复失败：上场核心重名，无法确认装备归属，保留对局")
    if deployed:
        return deployed[0]
    if len(bench) == 1:
        return bench[0]
    if len(bench) > 1:
        raise RuntimeError("续跑状态恢复失败：备战席核心重名且未上场，保留对局")
    return None


def _read_core(war, auto, name, allowed_gear):
    position = _core_positions(war, name)
    if position is None:
        return None
    if not auto.click_element(position, "crop"):
        raise RuntimeError("续跑状态恢复失败：无法打开核心角色面板，保留对局")
    time.sleep(0.3)
    actual_name = auto.get_single_line_text(crop=NAME_CROP)
    if (actual_name or "").strip() != name:
        raise RuntimeError("续跑状态恢复失败：核心角色面板姓名不符，保留现场")
    stars = auto.find_element(STAR_IMAGE, "image_with_multiple_targets", 0.9, crop=STARS_CROP)
    if not isinstance(stars, list) or not 1 <= len(stars) <= 4:
        raise RuntimeError("续跑状态恢复失败：无法确认核心星级，保留角色面板")
    equipment = []
    for index, crop in enumerate(EQUIPMENT_CROPS):
        matches = [kind for kind in allowed_gear
                   if auto.find_element(GEAR_IMAGES[kind], "image", 0.92, crop=crop,
                                        scale_range=(0.65, 1.30))]
        empty = _empty_slot(auto, index)
        if len(matches) == 1 and not empty:
            equipment.append(matches[0])
        elif not matches and empty:
            equipment.append(None)
        else:
            raise RuntimeError(f"续跑状态恢复失败：核心装备槽{index + 1}为空或类型无法确认，保留角色面板")
    war.click_origin()
    return {"stars": len(stars), "equipment": equipment}


def restore_resume_state(war, auto, cfg):
    """Call once in preparation after rewards, before native buys/sells.

    Raise RuntimeError on unknown data; the caller must preserve the saved run.
    Returns a small diagnostic result, not a serialized game-state snapshot.
    """
    used = _read_layout(war, auto)
    war.check_character_status()
    deployed_count = sum(bool(character.name) for zone in ("forward", "backward")
                         for character in getattr(war, zone + "_characters"))
    if deployed_count != used:
        raise RuntimeError("续跑状态恢复失败：已识别角色数与团队规模不符，保留对局")
    war.reset_tracked_characters()
    for zone in ("forward", "backward", "prepare"):
        war.mark_tracked_characters(getattr(war, zone + "_characters"))
    strategy = cfg.currencywars_strategy
    if strategy == "aglaea":
        core = _read_core(war, auto, "阿格莱雅", ("shoe", "boots", "propeller"))
        gear = core["equipment"] if core else []
        war.has_aglaea_three_star = bool(core and core["stars"] >= 3)
        war.shoe_count = gear.count("shoe") + 2 * gear.count("boots")
        war.propeller_count = gear.count("propeller")
        war.allow_buy_experience = (war.has_aglaea_three_star
                                    and all(war.has_tracked_character(name) for name in ("风堇", "缇宝", "藿藿")))
        war.allow_equip_weapons = war.shoe_count >= 4 and war.propeller_count >= 1
    elif strategy == "seele":
        core = _read_core(war, auto, "希儿", ("firestorm", "chainsaw", "shoe"))
        gear = core["equipment"] if core else []
        war.has_seele = core is not None
        war.has_seele_three_star = bool(core and core["stars"] >= 3)
        war.seele_firestorm_count = gear.count("firestorm")
        war.seele_chainsaw_count = gear.count("chainsaw")
        war.allow_seele_equip_weapons = war.seele_firestorm_count >= 2 and war.seele_chainsaw_count >= 1
        war.seele_missing_basic_equips.clear()
    return {"strategy": strategy, "level": war.current_level, "deployed_count": deployed_count}
