"""角色面板导出：解析和遍历逻辑。OCR 样本来自实机，保留了真实的噪声。"""
import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from PIL import Image

from tasks.character_export import CharacterExport, parser
from tasks.character_export import reader as reader_module
from tasks.character_export.parser import Line as L
from tasks.character_export.reader import PageError


SUMMARY = [
    L("☆丹恒·腾荒", 1541, 142), L("存护", 1534, 184), L("等级80/80", 1553, 256),
    L("生命值", 1564, 369), L("3025-", 1851, 370), L("攻击力：", 1572, 406), L("2968", 1850, 406),
    L("防御力", 1564, 443), L("1101", 1851, 443), L("速度", 1554, 478), L("107", 1858, 478),
    L("暴击率", 1565, 514), L("81.1%", 1844, 514), L("暴击伤害", 1577, 551), L("180.2%", 1839, 551),
]
TOTALS = {"生命值": 3025, "攻击力": 2968, "防御力": 1101, "速度": 107, "暴击率": 81.1, "暴击伤害": 180.2}

SCREEN_1 = [
    L("基础属性", 488, 387), L("?", 460, 439), L("生命值", 520, 437), L("2106", 1190, 437),
    L("攻击力", 520, 478), L("1222", 1199, 478), L("防御力", 520, 519), L("923", 1205, 519),
    L("速度", 508, 559), L("107", 1205, 559), L("进阶属性", 488, 621),
    L("暴击率", 502, 672), L("81.1%", 1192, 673), L("暴击伤害", 530, 713), L("180.2%", 1185, 714),
    L("击破特攻", 533, 754), L("11.0%", 1193, 755), L("+", 462, 793),
    L("治疗量加成", 535, 791), L("00%", 1198, 792, 0.689),
]
EXTRAS = [L("+919", 1270, 437), L("+1746", 1269, 477), L("+177", 1269, 519)]
SCREEN_2 = [
    L("治疗量加成", 535, 351), L("0.0%", 1198, 352),
    L("能量恢复效率", 557, 392), L("119.4%", 1185, 392), L("效果命中", 532, 432), L("12.0%", 1191, 432),
    L("？", 1416, 433), L("效果抵抗", 533, 474), L("31.5%", 1191, 474), L("欢愉度", 520, 515), L("28.0%", 1191, 515),
    L("伤害属性", 488, 577),
    L("物理属性伤害提高", 561, 627), L("0.0%", 1198, 628), L("火属性伤害提高", 551, 669), L("0.0%", 1199, 669),
    L("冰属性伤害提高", 550, 709), L("0.0%", 1198, 708), L("雷属性伤害提高", 567, 750), L("0.0%", 1198, 750),
]
SCREEN_3 = [
    L("风属性伤害提高", 557, 396), L("0.0%", 1199, 397), L("量子属性伤害提高", 578, 438), L("0.0%", 1199, 438),
    L("虚数属性伤害提高", 575, 479), L("0.0%", 1198, 478), L("物理属性抗性提高", 580, 518), L("0.0%", 1199, 519),
    L("火属性抗性提高", 569, 560), L("0.0%", 1198, 560), L("冰属性抗性提高", 568, 600), L("0.0%", 1197, 601),
    L("雷属性抗性提高", 568, 640), L("0.0%", 1198, 642), L("风属性抗性提高", 568, 682), L("0.0%", 1198, 683),
    L("量子属性抗性提高", 580, 723), L("0.0%", 1198, 723), L("虚数属性抗性提高", 580, 763), L("0.0%", 1199, 764),
]
LIGHT_CONE = [
    L("花花世界迷人眼", 1605, 140), L("欢愉", 1561, 185), L("等级80/80", 1554, 254),
    L("生命值", 1567, 322), L("1058", 1848, 322), L("攻击力", 1565, 358), L("582", 1854, 358),
    L("防御力", 1566, 394), L("463", 1854, 394), L("光锥技能", 1538, 448),
    L("以下效果对【欢愉】命途角色生", 1700, 492), L("效", 1544, 524), L("叠影1阶", 1573, 569),
]
RELIC = [
    L("头部", 1512, 230), L("+15", 1514, 262),
    L("生命值", 1575, 310), L("705", 1853, 311), L("防御力", 1566, 355), L("4.3%", 1824, 354),
    L("暴击率", 1566, 393), L("11.3%", 1820, 393), L("3", 1866, 393),
    L("暴击伤害", 1576, 431), L("12.3%", 1819, 432), L("攻击力", 1566, 470), L("3.8%", 1825, 470),
    L("套装效果", 1539, 531), L("闪耀功勋的魔法少女(4)", 1613, 567), L("二件套：暴击伤害提高16%", 1685, 605),
]


def full_rows():
    rows, problems = parser.merge_stat_rows([
        parser.parse_stat_screen(SCREEN_1, EXTRAS),
        parser.parse_stat_screen(SCREEN_2),
        parser.parse_stat_screen(SCREEN_3),
    ])
    assert problems == []
    return rows


def test_lines_are_sorted_and_use_design_coordinates():
    result = [
        [[[0, 20], [10, 20], [10, 30], [0, 30]], ("下", 0.9)],
        [[[0, 0], [10, 0], [10, 10], [0, 10]], ("上", 0.8)],
    ]
    lines = parser.lines_from_ocr(result, (100, 200))
    assert [line.text for line in lines] == ["上", "下"]
    assert lines[0] == L("上", 105, 205, 0.8)
    assert parser.lines_from_ocr(False) == []


@pytest.mark.parametrize(("text", "name"), [
    ("丹恒?腾荒", "丹恒·腾荒"), ("阮.梅", "阮·梅"), ("☆花火", "花火"), ("银狼LV.999", "银狼LV.999"), ("Saber", "Saber"),
])
def test_name_is_normalized(text, name):
    assert parser.parse_summary([L(text, 1541, 142), L("欢愉", 1534, 184), L("等级80/80", 1553, 256)])["name"] == name


@pytest.mark.parametrize(("text", "value"), [("109.2", 1092), ("126,3", 1263), ("1101", 1101)])
def test_star_noise_inside_summary_digits(text, value):
    lines = [*summary_lines("火花"), L("防御力", 1564, 443), L(text, 1850, 443)]
    assert parser.parse_summary(lines)["totals"]["防御力"] == value


def test_summary_tolerates_real_noise():
    summary = parser.parse_summary(SUMMARY)
    assert summary["name"] == "丹恒·腾荒"
    assert (summary["path"], summary["level"], summary["max_level"]) == ("存护", 80, 80)
    assert summary["totals"] == TOTALS


@pytest.mark.parametrize("lines", [
    [L("存护", 1534, 184), L("等级80/80", 1553, 256)],
    [L("火花", 1541, 142), L("等级80/80", 1553, 256)],
    [L("火花", 1541, 142), L("欢愉", 1534, 184)],
])
def test_summary_rejects_missing_fields(lines):
    with pytest.raises(parser.ParseError):
        parser.parse_summary(lines)


@pytest.mark.parametrize(("text", "path"), [("欢愉", "欢愉"), ("聚巡猎", "巡猎"), ("￥巡猎", "巡猎"), ("丰绕", "丰饶")])
def test_path_matching(text, path):
    assert parser.match_path(text) == path


def test_faded_row_is_left_for_the_next_screen():
    rows = parser.parse_stat_screen(SCREEN_1, EXTRAS)
    assert "治疗量加成" not in rows
    assert rows["生命值"] == {"value": 2106, "extra": 919}
    assert rows["暴击伤害"] == {"value": 180.2, "extra": None}


def test_malformed_value_is_skipped_not_guessed():
    rows = parser.parse_stat_screen([
        L("攻击力", 520, 478), L("2+1746", 1269, 477), L("暴击率", 502, 672), L("00%", 1192, 673),
    ])
    assert rows == {}


def test_all_screens_build_full_stats():
    stats, problems = parser.build_stats(full_rows(), TOTALS)
    assert problems == []
    assert stats["base"]["hp"] == {"total": 3025, "base": 2106, "extra": 919}
    assert stats["base"]["def"] == {"total": 1101, "base": 923, "extra": 177}
    assert stats["base"]["spd"] == {"total": 107, "base": 107, "extra": 0}
    assert stats["advanced"]["elation"] == 28.0
    assert stats["advanced"]["outgoing_healing"] == 0.0
    assert len(stats["damage"]) == 14
    assert stats["other"] == {}


def test_cross_check_reports_misread_values():
    rows = full_rows()
    rows["攻击力"] = {"value": 1222, "extra": 1146}
    _, problems = parser.build_stats(rows, TOTALS)
    assert problems == ["攻击力 总值 2968 与 1222+1146 不符"]


def test_missing_total_falls_back_to_popup_values():
    totals = {key: value for key, value in TOTALS.items() if key != "防御力"}
    stats, problems = parser.build_stats(full_rows(), totals)
    assert problems == []
    assert stats["base"]["def"] == {"total": 1100, "base": 923, "extra": 177}


def test_missing_rows_are_reported():
    rows = full_rows()
    del rows["火属性抗性提高"]
    del rows["速度"]
    _, problems = parser.build_stats(rows, TOTALS)
    assert set(problems) == {"缺少属性：火属性抗性提高", "缺少属性：速度"}


def test_elation_is_optional():
    rows = full_rows()
    del rows["欢愉度"]
    stats, problems = parser.build_stats(rows, TOTALS)
    assert problems == []
    assert "elation" not in stats["advanced"]


def test_unknown_stat_is_kept():
    rows = parser.parse_stat_screen([L("忆灵能量上限", 530, 500), L("12.5%", 1190, 500)])
    assert rows == {"忆灵能量上限": {"value": 12.5, "extra": None}}
    all_rows = {**full_rows(), **rows}
    stats, problems = parser.build_stats(all_rows, TOTALS)
    assert stats["other"] == {"忆灵能量上限": 12.5}
    assert problems == ["未知属性：忆灵能量上限"]


def test_unreadable_unknown_label_is_not_trusted():
    assert parser.parse_stat_screen([L("公需属性伤害提高", 530, 700, 0.83), L("0.0%", 1190, 700)]) == {}


@pytest.mark.parametrize(("text", "expected"), [
    ("能量上限", "能量上限"), ("+治疗量加成", "治疗量加成"), ("悠雷属性伤害提高", "雷属性伤害提高"),
    ("攻击力：", "攻击力"), ("能重恢复效率", "能量恢复效率"), ("忆灵能量上限", None), ("属性详情", None),
    ("公需属性伤害提高", None), ("大属性伤害提高", None), ("量了属性伤害提高", "量子属性伤害提高"),
])
def test_label_matching_tolerates_misreads_but_not_new_labels(text, expected):
    assert parser.match_label(text, parser.ALL_STATS) == expected


def test_max_energy_is_a_flat_value():
    rows = parser.parse_stat_screen([L("能量上限", 530, 399), L("140", 1190, 399)])
    assert rows == {"能量上限": {"value": 140, "extra": None}}


def test_extra_value_without_sign():
    rows = parser.parse_stat_screen([L("攻击力", 520, 478), L("1222", 1199, 478)], [L("1746", 1269, 477)])
    assert rows["攻击力"] == {"value": 1222, "extra": 1746}


def test_trailing_punctuation_is_noise():
    assert parser.parse_flat("582.") == 582
    assert parser.parse_flat("1263，") == 1263
    assert parser.parse_flat("58.2") is None
    assert parser.parse_percent("183.7%.") == 183.7


def test_negative_extra_value():
    rows = parser.parse_stat_screen([L("速度", 508, 559), L("98", 1205, 559)], [L("-6", 1260, 559)])
    assert rows["速度"] == {"value": 98, "extra": -6}
    all_rows = {**full_rows(), **rows}
    stats, problems = parser.build_stats(all_rows, {**TOTALS, "速度": 92})
    assert problems == []
    assert stats["base"]["spd"] == {"total": 92, "base": 98, "extra": -6}


def test_overlapping_rows_must_agree():
    rows, problems = parser.merge_stat_rows([
        {"暴击率": {"value": 81.1, "extra": None}},
        {"暴击率": {"value": 87.1, "extra": None}},
    ])
    assert rows["暴击率"]["value"] == 81.1
    assert problems == ["暴击率 两次读数不一致：81.1 / 87.1"]


def test_light_cone():
    assert parser.parse_light_cone(LIGHT_CONE) == {
        "name": "花花世界迷人眼", "path": "欢愉", "level": 80, "max_level": 80,
        "superimposition": 1, "stats": {"hp": 1058, "atk": 582, "def": 463},
    }


def test_light_cone_value_comes_from_its_own_cell():
    lines = [L("1582", line.x, line.y) if line.text == "582" else line for line in LIGHT_CONE]
    assert parser.parse_light_cone(lines, {358: "582"})["stats"]["atk"] == 582


@pytest.mark.parametrize("empty", [None, ""])
def test_failed_light_cone_cell_cannot_use_noisy_block_value(empty):
    lines = [L("1582", line.x, line.y) if line.text == "582" else line for line in LIGHT_CONE]
    with pytest.raises(parser.ParseError, match="光锥属性"):
        parser.parse_light_cone(lines, {358: empty})


@pytest.mark.parametrize(("text", "expected"), [("等级80/8", (80, 80)), ("等级50/5", (50, 50)), ("等级1/20", (1, 20))])
def test_gray_level_cap_may_lose_its_last_digit(text, expected):
    lines = [L(text, line.x, line.y) if line.text == "等级80/80" else line for line in LIGHT_CONE]
    cone = parser.parse_light_cone(lines)
    assert (cone["level"], cone["max_level"]) == expected


def test_impossible_level_is_rejected():
    lines = [L("等级80/70", line.x, line.y) if line.text == "等级80/80" else line for line in LIGHT_CONE]
    with pytest.raises(parser.ParseError):
        parser.parse_light_cone(lines)


@pytest.mark.parametrize(("text", "name"), [
    ("决心如汗珠般闪耀，", "决心如汗珠般闪耀"), ("片刻，留在眼底", "片刻，留在眼底"), ("舞！舞！舞！", "舞！舞！舞！"),
])
def test_light_cone_name_keeps_only_real_punctuation(text, name):
    lines = [L(text, line.x, line.y) if line.text == "花花世界迷人眼" else line for line in LIGHT_CONE]
    assert parser.parse_light_cone(lines)["name"] == name


def test_empty_light_cone():
    assert parser.parse_light_cone([L("未装备", 1540, 140), L("等级0/0", 1554, 254), L("未装备光锥", 1686, 741)]) is None


def test_light_cone_rejects_partial_read():
    with pytest.raises(parser.ParseError):
        parser.parse_light_cone(LIGHT_CONE[:3])


@pytest.mark.parametrize(("text", "expected"), [
    ("10/10", (10, 10)), ("6/12", (6, 12)), ("3/7", (3, 7)), ("1/1", (1, 1)),
    ("10/1", None), ("0/10", None), ("6", None), ("", None),
])
def test_trace_label(text, expected):
    assert parser.parse_trace_label(text) == expected


def test_skill_panel():
    lines = [L("战技", 1001, 142), L("海底捞月", 1064, 190), L("[强化]", 1044, 233), L("等级12", 1403, 238)]
    assert parser.parse_skill_panel(lines) == ("战技", 12)
    with pytest.raises(parser.ParseError):
        parser.parse_skill_panel(lines[:2])


def test_relic_piece_ignores_upgrade_badge():
    piece = parser.parse_relic_piece(RELIC)
    assert piece["slot"] == "头部"
    assert piece["level"] == 15
    assert (piece["set"], piece["set_count"]) == ("闪耀功勋的魔法少女", 4)
    assert piece["main_stat"] == {"stat": "hp", "value": 705, "percent": False}
    assert piece["sub_stats"][1] == {"stat": "crit_rate", "value": 11.3, "percent": True}
    assert len(piece["sub_stats"]) == 4


def test_missing_relic_value_comes_from_its_own_cell():
    lines = [line for line in RELIC if line.text != "3.8%"]
    with pytest.raises(parser.ParseError):
        parser.parse_relic_piece(lines)
    piece = parser.parse_relic_piece(lines, {470: "4"})
    assert piece["sub_stats"][3] == {"stat": "atk", "value": 4, "percent": False}


@pytest.mark.parametrize("block", ["*9.7%", "t9.7%", "19.7%"])
def test_star_next_to_a_short_value_cannot_change_it(block):
    lines = [L(block, line.x, line.y) if line.text == "11.3%" else line for line in RELIC]
    piece = parser.parse_relic_piece(lines, {393: "9.7%"})
    assert piece["sub_stats"][1] == {"stat": "crit_rate", "value": 9.7, "percent": True}


def test_noise_in_label_column_is_not_a_substat():
    piece = parser.parse_relic_piece([L("2", 1503, 312), *RELIC])
    assert len(piece["sub_stats"]) == 4


def test_unmeasured_cell_can_use_block_value():
    assert parser.parse_relic_piece(RELIC, {})["sub_stats"][1]["value"] == 11.3


@pytest.mark.parametrize("empty", [None, ""])
def test_failed_relic_cell_cannot_use_noisy_block_value(empty):
    # 60 帧实机：单格 OCR 为空，整块却把速度 6 识别成了 60.。
    lines = [L("速度", line.x, line.y) if line.text == "攻击力" else line for line in RELIC]
    lines = [L("60.", line.x, line.y) if line.text == "3.8%" else line for line in lines]
    with pytest.raises(parser.ParseError, match="速度 数值未识别"):
        parser.parse_relic_piece(lines, {470: empty})


@pytest.mark.parametrize("row", [0, 1])
def test_numeric_crops_remove_star_dot_but_keep_decimal_points(row):
    # 30 帧实机：两行分别为有/无干扰的帧；四列是 10.8%、4、7.7%、21。
    with Image.open(Path(__file__).parent / "fixtures/character_relic_values.png") as samples:
        cells = [samples.crop((col * 94, row * 34, (col + 1) * 94, (row + 1) * 34)) for col in range(4)]
    attack = reader_module._white_text(cells[3])[:, :, 0]
    assert not attack[:, 78:81].any()  # 2 和 1 之间的星星，不是真小数点。
    assert np.count_nonzero(attack[:, 66:76]) >= 70
    assert np.count_nonzero(attack[:, 82:89]) >= 55
    for index, y in [(0, 23), (2, 24)]:
        percent = reader_module._white_text(cells[index])[:, :, 0]
        assert (percent[y:y + 3, 53:55] == 255).all()  # 真实百分比中的小数点。
        cropped, (dx, dy) = reader_module._numeric_crop(cells[index])
        assert (cropped[y-dy:y-dy+3, 53-dx:55-dx] == 255).all()


@pytest.mark.parametrize("column", [0, 1])
def test_single_digit_crop_keeps_strokes_and_adds_margin(column):
    # 实机中去背景后被漏检的 9、6，移除大片左侧空白并补齐边距。
    with Image.open(Path(__file__).parent / "fixtures/character_single_digits.png") as image:
        cell = image.crop((column*94, 0, (column+1)*94, 34))
    prepared, (dx, dy) = reader_module._numeric_crop(cell)
    assert prepared.shape[1] < cell.width
    assert not prepared[:16].any() and not prepared[-16:].any()
    assert not prepared[:, :16].any() and not prepared[:, -16:].any()
    original = reader_module._white_text(cell)
    # 处理后的字形及其坐标仍能精确对应原图，没有重画数字。
    h, w = prepared.shape[:2]
    assert np.array_equal(prepared[16:-16, 16:-16], original[dy+16:dy+h-16, dx+16:dx+w-16])


def test_successful_numeric_cells_are_filtered_without_extra_ocr(monkeypatch):
    reader = reader_module.CharacterReader.__new__(reader_module.CharacterReader)
    reader.ocr_pool = SimpleNamespace(submit=lambda function, *args: Done(function(*args)))
    calls = []
    monkeypatch.setattr(reader_module, "_recognize", lambda pixels, origin: calls.append((np.array(pixels), origin)) or [L("6", *origin)])
    image = Image.new("RGB", (1920, 1080), (100, 120, 200))
    cells = reader._submit_cells(image, reader_module.RELIC_VALUES)
    assert len(cells) == len(calls) == 4
    assert [origin for _, origin in calls] == [(1760, y - 17) for y in reader_module.RELIC_VALUES]
    assert all(not pixels.any() for pixels, _ in calls)
    reader._submit(image, reader_module.RELIC_PIECE_BOX)
    assert (calls[-1][0] == (100, 120, 200)).all()  # 彩色主词条、套装正文不做此处理。


@pytest.mark.parametrize("text", ["6", "9", "21", "10.8%"])
def test_numeric_detection_miss_recognizes_the_same_crop_directly(text, monkeypatch):
    calls = []
    pixels = np.zeros((54, 47, 3), dtype=np.uint8)

    def recognize(image, **options):
        calls.append((image.copy(), options))
        if options.get("recognition_only"):
            return [[[[0, 0], [47, 0], [47, 54], [0, 54]], (text, 0.99)]]
        return []

    monkeypatch.setattr(reader_module, "ocr", SimpleNamespace(recognize_multi_lines=recognize))
    result = reader_module._recognize_numeric(pixels, (1800, 400))
    assert [line.text for line in result] == [text]
    assert result[0].x == 1823.5 and result[0].y == 427
    assert [options for _, options in calls] == [{}, {"recognition_only": True}]
    assert all(np.array_equal(image, pixels) for image, _ in calls)


def test_numeric_both_recognition_paths_can_fail_without_guessing(monkeypatch):
    monkeypatch.setattr(reader_module, "ocr", SimpleNamespace(recognize_multi_lines=lambda *args, **kwargs: []))
    assert reader_module._recognize_numeric(np.zeros((34, 94, 3), dtype=np.uint8), (0, 0)) == []


def test_invalid_decimal_without_percent_is_still_rejected():
    with pytest.raises(parser.ParseError, match="攻击力 2.1"):
        parser.parse_relic_piece(RELIC, {470: "2.1"})


def test_relic_piece_rejects_partial_read():
    with pytest.raises(parser.ParseError):
        parser.parse_relic_piece(RELIC[:5])


def test_relic_set_names_come_from_project_data():
    names = reader_module.load_relic_sets()
    assert {"骇域漫游的信使", "繁星竞技场", "天国@直播间"} <= names


@pytest.mark.parametrize(("name", "expected"), [
    ("孩域漫游的信使", "骇域漫游的信使"), ("骇域漫游的信使", "骇域漫游的信使"), ("从未出现过的新套装", "从未出现过的新套装"),
])
def test_relic_set_name_is_corrected(name, expected):
    assert parser.correct_relic_set(name, {"骇域漫游的信使", "繁星竞技场"}) == expected


def test_relic_set_name_with_missing_character_is_corrected():
    assert parser.correct_relic_set("毁焚骨的大公", {"毁烬焚骨的大公", "繁星竞技场"}) == "毁烬焚骨的大公"


def test_ambiguous_relic_set_name_is_kept():
    assert parser.correct_relic_set("甲乙丙丁", {"甲乙丙戊", "甲乙丙己"}) == "甲乙丙丁"


def relic_reader():
    relic_reader = reader_module.CharacterReader.__new__(reader_module.CharacterReader)
    relic_reader.known_relic_sets = {"闪耀功勋的魔法少女"}
    return relic_reader


def relic_lines(slot, value="3.8%"):
    lines = [L(slot, 1512, 230) if line.text == "头部" else line for line in RELIC]
    return [L(value, line.x, line.y) if line.text == "3.8%" else line for line in lines]


def test_second_read_only_fills_the_pieces_that_failed():
    reader = relic_reader()
    first, problems = reader.finish_relics([
        ("头部", Done(relic_lines("头部")), {}),
        ("手部", Done(relic_lines("手部", "*3.8%")), {}),
    ])
    assert [piece["slot"] for piece in first["pieces"]] == ["头部"]
    assert len(problems) == 2  # 手部读错，头部显示 4 件却只读到 1 件的问题也要暴露
    second, problems = reader.finish_relics([
        ("头部", Done(relic_lines("头部", "*3.8%")), {}),
        ("手部", Done(relic_lines("手部")), {}),
    ], first["by_slot"])
    assert [piece["slot"] for piece in second["pieces"]] == ["头部", "手部"]
    assert second["pieces"][0]["sub_stats"][3]["value"] == 3.8
    assert problems == ["闪耀功勋的魔法少女 显示 4 件，实际读到 2 件"]


def test_failed_numeric_cell_uses_existing_relic_retry():
    from tasks.character_export import _finish

    reader = relic_reader()
    lines = [L("速度", line.x, line.y) if line.text == "攻击力" else line for line in RELIC]
    lines = [L("60.", line.x, line.y) if line.text == "3.8%" else line for line in lines]
    lines = [L(line.text.replace("(4)", "(1)"), line.x, line.y) for line in lines]
    calls = []

    def retry(first):
        calls.append(first)
        return reader.finish_relics([("头部", Done(lines), {470: Done([L("6", 1845, 470)])})], first["by_slot"])

    result, problems = _finish([("头部", Done(lines), {470: Done([])})], reader.finish_relics, retry)
    assert len(calls) == 1
    assert problems == []
    assert result["pieces"][0]["sub_stats"][3] == {"stat": "spd", "value": 6, "percent": False}


def test_relic_sets_are_counted_from_pieces():
    pieces = [{"set": "闪耀功勋的魔法少女", "set_count": 4}] * 4 + [{"set": "天国@直播间", "set_count": 2}] * 2
    sets, problems = parser.summarize_relic_sets(pieces)
    assert sets == [{"name": "闪耀功勋的魔法少女", "pieces": 4}, {"name": "天国@直播间", "pieces": 2}]
    assert problems == []


def test_relic_set_count_mismatch_is_reported():
    pieces = [{"set": "闪耀功勋的魔法少女", "set_count": 4}] * 3
    _, problems = parser.summarize_relic_sets(pieces)
    assert problems == ["闪耀功勋的魔法少女 显示 4 件，实际读到 3 件"]


@pytest.mark.parametrize(("name", "switchable", "expected"), [
    ("星", True, True), ("一个改过的名字", True, True), ("三月七", True, False), ("火花", False, False),
])
def test_trailblazer_detection(name, switchable, expected):
    assert parser.is_trailblazer(name, switchable) is expected


class Done:
    """已完成的 OCR 任务。"""

    def __init__(self, value):
        self.value = value

    def result(self):
        return self.value


def summary_lines(name, path="欢愉"):
    return [L(name, 1541, 142), L(path, 1534, 184), L("等级80/80", 1553, 256)]


class FakeReader:
    """按脚本提供顶栏的每一页，只记录选中和翻页。"""

    def __init__(self, pages):
        self.pages = pages
        self.page = 0
        self.selected = None
        self.closed = False
        self.resets = 0
        self.tab = "detail"

    def reset(self):
        self.page = 0
        self.resets += 1

    def close(self):
        self.closed = True

    def avatar_slots(self):
        return list(range(len(self.pages[self.page])))

    def select_avatar(self, x, required=False):
        self.selected = self.pages[self.page][x]

    def begin_summary(self):
        return Done(summary_lines(self.selected))

    def open_tab(self, tab):
        self.tab = tab

    def grab(self):
        pass

    def next_avatars(self):
        if self.page + 1 >= len(self.pages):
            return False
        self.page += 1
        return True

    def previous_avatars(self):
        self.pages[self.page] = self.back_pages.pop(0)
        return True


@pytest.fixture
def export(tmp_path, monkeypatch):
    def create(pages):
        reader = FakeReader(pages)
        job = CharacterExport(reader, output=str(tmp_path / "characters.json"), partial=str(tmp_path / "characters.partial.json"))
        job.read = []

        def read_character():
            name = reader.selected
            job.read.append(name)
            job.seen.add((name, "欢愉"))
            job.characters.append({"name": name, "warnings": []})

        monkeypatch.setattr(job, "read_character", read_character)
        return job

    monkeypatch.setattr("tasks.character_export.screen", SimpleNamespace(change_to=lambda target: None))
    return create


def test_walk_skips_avatars_repeated_after_dragging(export):
    job = export([["甲", "乙", "丙"], ["丙", "丁", "戊"], ["戊", "己"]])
    job._walk()
    assert job.read == ["甲", "乙", "丙", "丁", "戊", "己"]


def test_walk_handles_larger_overlap(export):
    job = export([["甲", "乙", "丙"], ["乙", "丙", "丁"]])
    job._walk()
    assert job.read == ["甲", "乙", "丙", "丁"]


def test_overshooting_drag_goes_back_instead_of_skipping_characters(export):
    job = export([["甲", "乙"], ["丁", "戊"]])
    job.reader.back_pages = [["乙", "丙", "丁"]]
    job._walk()
    assert job.read == ["甲", "乙", "丙", "丁"]


def test_keeps_reading_pages_after_a_restart(export, monkeypatch):
    job = export([["甲", "乙"], ["乙", "丙"], ["丙", "丁"]])
    original = job.read_character
    failures = [True]

    def flaky():
        if job.reader.selected == "丙" and failures:
            failures.pop()
            raise PageError("界面没有响应")
        original()

    monkeypatch.setattr(job, "read_character", flaky)
    assert job._walk_with_restarts() is True
    assert job.read == ["甲", "乙", "丙", "丁"]


def test_cannot_find_read_character_after_dragging(export):
    job = export([["甲"], ["丁"]])
    job.reader.back_pages = [["戊"], ["己"], ["庚"]]
    with pytest.raises(PageError):
        job._walk()


def test_run_enters_and_finishes_at_phone_menu(export, monkeypatch):
    targets = []
    monkeypatch.setattr("tasks.character_export.screen", SimpleNamespace(change_to=targets.append))
    job = export([["甲"]])
    job.run()
    assert targets == ["menu", "character", "menu"]


def test_run_writes_output_and_removes_partial(export, tmp_path):
    job = export([["甲", "乙"]])
    job._save(job.partial, False)
    assert job.run() is True
    data = json.loads((tmp_path / "characters.json").read_text(encoding="utf-8"))
    assert data["complete"] is True
    assert data["schema_version"] == 1
    assert [character["name"] for character in data["characters"]] == ["甲", "乙"]
    assert not (tmp_path / "characters.partial.json").exists()
    assert not (tmp_path / "characters.json.tmp").exists()
    assert job.reader.closed


def test_interrupted_walk_restarts_and_skips_read_characters(export, monkeypatch):
    job = export([["甲", "乙", "丙"]])
    original = job.read_character
    failures = [True]

    def flaky():
        if job.reader.selected == "乙" and failures:
            failures.pop()
            raise PageError("界面没有响应")
        original()

    monkeypatch.setattr(job, "read_character", flaky)
    assert job._walk_with_restarts() is True
    assert job.read == ["甲", "乙", "丙"]
    assert job.reader.resets == 2


def test_character_that_keeps_failing_is_skipped_and_the_rest_are_read(export, tmp_path, monkeypatch):
    job = export([["甲", "乙", "丙"], ["丙", "丁"]])
    original = job.read_character

    def broken():
        if job.reader.selected == "乙":
            raise PageError("界面没有响应")
        original()

    monkeypatch.setattr(job, "read_character", broken)
    assert job.run() is False
    data = json.loads((tmp_path / "characters.json").read_text(encoding="utf-8"))
    assert data["complete"] is False
    assert [character["name"] for character in data["characters"]] == ["甲", "丙", "丁"]
    assert data["failed"] == [{"name": "乙", "path": "欢愉"}]


def test_several_failed_characters_do_not_exhaust_later_characters(export, monkeypatch):
    job = export([["甲", "佩拉", "黑塔", "貊泽", "三月七", "乙"]])
    original = job.read_character
    reads = []

    def broken():
        reads.append(job.reader.selected)
        if job.reader.selected not in ("甲", "乙"):
            raise PageError("切换到星魂页：界面未稳定")
        original()

    monkeypatch.setattr(job, "read_character", broken)
    assert job.run() is False
    assert job.read == ["甲", "乙"]
    assert [item["name"] for item in job.failed] == ["佩拉", "黑塔", "貊泽", "三月七"]
    assert all(reads.count(item["name"]) == 2 for item in job.failed)


def test_navigation_failures_do_not_count_as_character_read_failures(export, monkeypatch):
    job = export([["甲"], ["甲", "乙"]])
    original = job.reader.select_avatar
    failures = [True] * 3

    def select(x, required=False):
        if job.reader.page == 1 and x == 1 and failures:
            failures.pop()
            raise PageError("无法切换角色")
        return original(x, required)

    monkeypatch.setattr(job.reader, "select_avatar", select)
    assert job.run() is True
    assert job.read == ["甲", "乙"]
    assert not job.failed
    assert not any(job.attempts.values())


def test_gives_up_when_interface_keeps_failing(export, tmp_path, monkeypatch):
    job = export([["甲", "乙"]])
    original = job.read_character
    calls = []

    def broken():
        if job.reader.selected == "甲":
            original()
            return
        calls.append(1)
        job.attempts.clear()
        raise PageError("界面没有响应")

    monkeypatch.setattr(job, "read_character", broken)
    assert job.run() is False
    assert len(calls) == 8
    data = json.loads((tmp_path / "characters.json").read_text(encoding="utf-8"))
    assert [character["name"] for character in data["characters"]] == ["甲"]


def test_no_characters_is_an_error(export):
    job = export([[]])
    with pytest.raises(RuntimeError, match="简体中文"):
        job.run()
    assert job.reader.closed


def test_stopped_run_keeps_previous_output(export, tmp_path, monkeypatch):
    (tmp_path / "characters.json").write_text("上一次的结果", encoding="utf-8")
    job = export([["甲", "乙"]])
    original = job.read_character

    def stopped():
        if job.reader.selected == "乙":
            raise KeyboardInterrupt
        original()
        job._save(job.partial, False)

    monkeypatch.setattr(job, "read_character", stopped)
    with pytest.raises(KeyboardInterrupt):
        job.run()
    assert (tmp_path / "characters.json").read_text(encoding="utf-8") == "上一次的结果"
    assert json.loads((tmp_path / "characters.partial.json").read_text(encoding="utf-8"))["complete"] is False


class SectionReader:
    """读取层的替身：每段读取都成功，finish 的行为由测试指定。"""

    def __init__(self):
        self.tab = "detail"
        self.calls = []
        self.first_summary = full_summary_lines()
        self.switchable = False

    def grab(self):
        pass

    def begin_summary(self):
        return Done(full_summary_lines())

    def begin_detail(self):
        self.calls.append(("detail",))
        self.tab = "detail"
        return {"summary": Done(self.first_summary), "element": "火", "switchable": self.switchable, "stats": "stats"}

    def read_eidolon(self):
        self.calls.append(("eidolon",))
        self.tab = "eidolons"
        return 2

    def begin_stats(self, careful=False):
        self.calls.append(("stats", careful))
        return "stats"

    def finish_stats(self, pending, totals):
        return {"base": {}}, []

    def open_traces(self):
        self.calls.append(("traces",))
        return "frame"

    def begin_traces(self, path, frame):
        return "traces"

    def finish_traces(self, pending):
        return [{"type": "普攻", "level": 6, "max_level": 6}], []

    def read_skills_by_panel(self):
        self.calls.append(("panel",))
        return [{"type": "普攻", "level": 6, "max_level": None}], []

    def begin_light_cone(self):
        self.calls.append(("light_cone",))
        return "cone"

    def finish_light_cone(self, pending):
        return None, []

    def begin_relics(self):
        self.calls.append(("relics",))
        return []

    def finish_relics(self, pending, known=None):
        return {"sets": [], "pieces": [], "by_slot": {}}, []

    def open_tab(self, tab):
        self.tab = tab


def read_one(reader, tmp_path, name="火花"):
    job = CharacterExport(reader, output=str(tmp_path / "out.json"), partial=str(tmp_path / "part.json"))
    reader.first_summary = full_summary_lines(name)
    job.read_character()
    return job.characters[0]


def test_character_structure(tmp_path):
    reader = SectionReader()
    character = read_one(reader, tmp_path)
    assert character == {
        "name": "火花", "is_trailblazer": False, "path_switchable": False, "path": "欢愉", "element": "火",
        "level": 80, "max_level": 80, "eidolon": 2, "stats": {"base": {}}, "light_cone": None,
        "skills": [{"type": "普攻", "level": 6, "max_level": 6}],
        "relics": {"sets": [], "pieces": []}, "warnings": [],
    }


def test_characters_are_read_back_and_forth_to_skip_one_tab_click(tmp_path):
    reader = SectionReader()
    job = CharacterExport(reader, output=str(tmp_path / "out.json"), partial=str(tmp_path / "part.json"))
    job.read_character()
    assert [call[0] for call in reader.calls] == ["detail", "traces", "light_cone", "relics", "eidolon"]
    assert reader.tab == "eidolons"

    reader.calls.clear()
    reader.first_summary = full_summary_lines("银狼")
    job.read_character()
    assert [call[0] for call in reader.calls] == ["eidolon", "relics", "light_cone", "traces", "detail"]
    assert reader.tab == "detail"
    assert [character["name"] for character in job.characters] == ["火花", "银狼"]


def test_stats_problems_trigger_one_careful_reread(tmp_path):
    reader = SectionReader()
    results = [({"base": "第一次"}, ["缺少属性：速度"]), ({"base": "第二次"}, [])]
    reader.finish_stats = lambda pending, totals: results.pop(0)
    character = read_one(reader, tmp_path)
    assert character["stats"] == {"base": "第二次"}
    assert character["warnings"] == []
    assert reader.calls.count(("stats", True)) == 1


def test_problems_that_survive_the_reread_become_warnings(tmp_path):
    reader = SectionReader()
    reader.finish_stats = lambda pending, totals: ({"base": {}}, ["攻击力 总值不符"])
    character = read_one(reader, tmp_path)
    assert character["warnings"] == ["攻击力 总值不符"]


def full_summary_lines(name="火花", without=()):
    lines = summary_lines(name)
    for index, (label, value) in enumerate(TOTALS.items()):
        if label not in without:
            y = 369 + index * 36
            lines += [L(label, 1564, y), L(f"{value}%" if isinstance(value, float) else str(value), 1850, y)]
    return lines


def test_missing_total_is_reread_without_reopening_the_popup(tmp_path):
    reader = SectionReader()
    seen = {}

    def finish_stats(pending, totals):
        seen.update(totals)
        return {"base": {}}, []

    reader.finish_stats = finish_stats
    job = CharacterExport(reader, output=str(tmp_path / "out.json"), partial=str(tmp_path / "part.json"))
    reader.first_summary = full_summary_lines(without=("防御力",))
    job.read_character()
    assert seen == TOTALS
    assert job.characters[0]["warnings"] == []
    assert ("stats", True) not in reader.calls


def test_missing_crit_total_needs_no_warning(tmp_path):
    reader = SectionReader()
    reader.begin_summary = lambda: Done(full_summary_lines(without=("暴击率",)))
    job = CharacterExport(reader, output=str(tmp_path / "out.json"), partial=str(tmp_path / "part.json"))
    reader.first_summary = full_summary_lines(without=("暴击率",))
    job.read_character()
    assert job.characters[0]["warnings"] == []


def test_total_that_cannot_be_read_is_reported(tmp_path):
    reader = SectionReader()
    reader.begin_summary = lambda: Done(full_summary_lines(without=("防御力",)))
    job = CharacterExport(reader, output=str(tmp_path / "out.json"), partial=str(tmp_path / "part.json"))
    reader.first_summary = full_summary_lines(without=("防御力",))
    job.read_character()
    assert job.characters[0]["warnings"] == ["详情页没有读到防御力，未能交叉校验"]


def test_mismatch_rereads_totals_and_popup(tmp_path):
    reader = SectionReader()
    results = [({"base": {}}, ["防御力 总值 1181 与 923+177 不符"]), ({"base": "第二次"}, [])]
    seen = []

    def finish_stats(pending, totals):
        seen.append(totals["防御力"])
        return results.pop(0)

    reader.finish_stats = finish_stats
    job = CharacterExport(reader, output=str(tmp_path / "out.json"), partial=str(tmp_path / "part.json"))
    reader.first_summary = [line if line.text != "1101" else L("1181", 1850, line.y) for line in full_summary_lines()]
    job.read_character()
    assert seen == [1181, 1101]
    assert job.characters[0]["stats"] == {"base": "第二次"}


def test_unreadable_section_keeps_going(tmp_path):
    reader = SectionReader()

    def fail(pending):
        raise parser.ParseError("光锥读取失败")

    reader.finish_light_cone = fail
    character = read_one(reader, tmp_path)
    assert character["light_cone"] is None
    assert character["warnings"] == ["光锥读取失败", "光锥读取失败"]
    assert character["relics"] == {"sets": [], "pieces": []}


def test_trace_failure_falls_back_to_skill_panel(tmp_path):
    reader = SectionReader()

    def fail(pending):
        raise parser.ParseError("行迹标签读取失败")

    reader.finish_traces = fail
    character = read_one(reader, tmp_path)
    assert character["skills"] == [{"type": "普攻", "level": 6, "max_level": None}]
    assert character["warnings"] == []
    assert ("panel",) in reader.calls


def test_duplicate_found_late_is_dropped(tmp_path):
    reader = SectionReader()
    job = CharacterExport(reader, output=str(tmp_path / "out.json"), partial=str(tmp_path / "part.json"))
    job.seen.add(("火花", "欢愉"))
    job.read_character()
    assert job.characters == []


def test_trailblazer_keeps_ocr_name(tmp_path):
    reader = SectionReader()
    reader.switchable = True
    character = read_one(reader, tmp_path, name="我起的名字")
    assert character["name"] == "我起的名字"
    assert character["is_trailblazer"] is True
    assert character["path_switchable"] is True


def test_avatar_slots_are_found_at_any_offset():
    canvas = np.zeros((1080, 1920, 3), dtype=np.uint8)
    for x in range(549, 1500, 108):
        cv2.circle(canvas, (x, 65), 34, (200, 180, 120), 3)
        cv2.circle(canvas, (x, 65), 26, (90, 90, 90), -1)
    slots = reader_module.find_avatar_slots(Image.fromarray(canvas))
    expected = list(range(549, 1441, 108))
    assert len(slots) == len(expected)
    assert all(abs(found - x) <= 8 for found, x in zip(slots, expected))


def test_popup_end_is_read_from_scrollbar():
    track = Image.new("RGB", (1920, 1080), (200, 200, 200))
    assert not reader_module.CharacterReader._popup_at_end(track)
    track.paste((60, 60, 60), (1470, 640, 1482, 785))
    assert reader_module.CharacterReader._popup_at_end(track)


def test_every_path_has_a_trace_layout():
    assert set(reader_module.TRACE_LAYOUT) == set(parser.PATHS)
    for layout in reader_module.TRACE_LAYOUT.values():
        assert {"普攻", "战技", "终结技", "天赋"} <= set(layout)


def test_every_template_exists():
    paths = [*reader_module.ELEMENT_TEMPLATES.values(), reader_module.PATH_SWITCH, reader_module.RELIC_EMPTY_SLOT,
             reader_module.RELIC_UNEQUIP, reader_module.EIDOLON_LOCK, reader_module.EIDOLON_UNLOCKED,
             "./assets/images/screen/character.png"]
    assert len(reader_module.ELEMENT_TEMPLATES) == 7
    for path in paths:
        assert Path(path).is_file(), path


@pytest.fixture
def eidolon_frames():
    # 实机裁剪，每行依次是六个槽位：首次进入的空页、0 魂、6 魂、2 魂、入场动画。
    samples = Image.open(Path(__file__).parent / "fixtures/character_eidolons.png")
    frames = []
    for row in range(5):
        frame = Image.new("RGB", (1920, 1080))
        for col, (x, y) in enumerate(reader_module.EIDOLON_SLOTS):
            frame.paste(samples.crop((col * 90, row * 90, (col + 1) * 90, (row + 1) * 90)), (x - 45, y - 45))
        frames.append(frame)
    return frames


@pytest.fixture
def eidolon_reader(monkeypatch):
    reader = reader_module.CharacterReader.__new__(reader_module.CharacterReader)
    reader.templates = {}
    reader.tab = "eidolons"
    clock = SimpleNamespace(now=0.0, captures=0)

    def sleep(seconds):
        clock.now += seconds

    monkeypatch.setattr(reader_module, "time", SimpleNamespace(monotonic=lambda: clock.now, sleep=sleep))

    def feed(frames):
        clock.captures = 0
        reader.frame = frames[0]

        def capture():
            frame = frames[min(clock.captures, len(frames) - 1)]
            clock.captures += 1
            clock.now += 0.05
            return frame, None, None

        # 使用真正的 grab，保证识别循环每次重新截图。
        monkeypatch.setattr(reader_module, "auto", SimpleNamespace(take_screenshot=capture))

    return reader, feed, clock


def ui_frame(color=0, box=reader_module.RIGHT_PANEL):
    frame = Image.new("RGB", (1920, 1080))
    x, y, width, height = box
    frame.paste((color, color, color), (x, y, x + width, y + height))
    return frame


def test_settle_requires_elapsed_stability_not_two_identical_captures(eidolon_reader):
    reader, feed, clock = eidolon_reader
    # 中间两张重复帧仍在淡入，不能仅因为两次截图相同就开始 OCR。
    feed([ui_frame(100)] * 2 + [ui_frame(200)] * 4)
    assert reader._settle(reader_module.RIGHT_PANEL, ui_frame()).getpixel((1500, 150)) == (200, 200, 200)
    assert clock.captures >= 5


def test_settle_detects_cumulative_slow_fade(eidolon_reader):
    reader, feed, clock = eidolon_reader
    feed([ui_frame(color) for color in range(100, 141, 4)])
    frame = reader._settle(reader_module.RIGHT_PANEL)
    assert frame.getpixel((1500, 150)) == (140, 140, 140)
    assert clock.captures > 11


@pytest.mark.parametrize("key", ["esc", "e"])
def test_action_does_not_repeat_input_after_response_during_long_animation(key, eidolon_reader, monkeypatch):
    reader, feed, _ = eidolon_reader
    feed([ui_frame(color) for color in [0, 100, 200, 100, 200, 100, 200, 200, 200]])
    presses = []
    monkeypatch.setattr(reader, "_press", presses.append)
    frame = reader._act(lambda: reader._press(key), reader_module.RIGHT_PANEL, timeout=0.2)
    assert frame.getpixel((1500, 150)) == (200, 200, 200)
    assert presses == [key]


def test_action_retries_input_that_did_not_respond(eidolon_reader):
    reader, feed, _ = eidolon_reader
    feed([ui_frame()] * 5 + [ui_frame(200)] * 5)
    actions = []
    reader._act(lambda: actions.append(1), reader_module.RIGHT_PANEL, timeout=0.2)
    assert actions == [1, 1]


def test_action_failure_identifies_the_operation(eidolon_reader):
    reader, feed, _ = eidolon_reader
    feed([ui_frame()])
    with pytest.raises(PageError, match="退出遗器详情"):
        reader._act(lambda: None, reader_module.RIGHT_PANEL, operation="退出遗器详情")


def test_eidolon_tab_does_not_require_animated_artwork_to_stop(eidolon_reader, monkeypatch):
    reader, feed, clock = eidolon_reader
    frames = [ui_frame()]
    for color in [100, 200] * 20:
        frame = ui_frame(color)
        x, y, width, height = reader_module.TAB_TITLE
        frame.paste((255, 255, 255), (x, y, x + width, y + height))
        frames.append(frame)
    feed(frames)
    reader.tab = "relics"
    clicks = []
    monkeypatch.setattr(reader, "_click", lambda *pos: clicks.append(pos))
    reader.open_tab("eidolons")
    assert reader.tab == "eidolons"
    assert clicks == [(reader_module.TAB_X, reader_module.TAB_Y["eidolons"])]
    assert clock.now < 0.5


@pytest.mark.parametrize("tab", ["detail", "light_cone", "traces", "relics"])
def test_tab_change_can_leave_the_right_panel_unchanged(tab, eidolon_reader, monkeypatch):
    reader, feed, clock = eidolon_reader
    feed([ui_frame()] + [ui_frame(255, reader_module.TAB_TITLE)] * 15)
    clicks = []
    monkeypatch.setattr(reader, "_click", lambda *pos: clicks.append(pos))
    reader.open_tab(tab)
    assert reader.tab == tab
    assert clicks == [(reader_module.TAB_X, reader_module.TAB_Y[tab])]
    assert clock.now < 0.6


def test_panel_can_settle_with_sparse_background_particles(eidolon_reader, monkeypatch):
    reader, feed, clock = eidolon_reader
    frames = [ui_frame()]
    for color in [100, 200] * 20:
        frame = ui_frame(255, reader_module.TAB_TITLE)
        # 与 30 帧实机相近：右栏约 0.8% 像素持续变化，正文不变。
        frame.paste((color, color, color), (1500, 120, 1540, 160))
        frames.append(frame)
    feed(frames)
    monkeypatch.setattr(reader, "_click", lambda *pos: None)
    reader.open_tab("traces")
    assert clock.now < 0.6


@pytest.mark.parametrize("required", [False, True])
def test_delayed_avatar_response_keeps_original_reference(required, eidolon_reader, monkeypatch):
    reader, feed, _ = eidolon_reader
    reader.tab = "detail"
    old = ui_frame()
    new = ui_frame(200)
    x, y, width, height = reader_module.BREADCRUMB
    new.paste((255, 255, 255), (x, y, x + width, y + height))
    feed([old] * 9 + [new] * 10)
    clicks = []
    monkeypatch.setattr(reader, "_click", lambda *pos: clicks.append(pos))
    assert reader.select_avatar(600, required=required)
    assert clicks == [(600, reader_module.AVATAR_Y)]


def test_first_avatar_animation_is_not_a_character_name_change(eidolon_reader, monkeypatch):
    reader, feed, _ = eidolon_reader
    reader.tab = "detail"
    feed([ui_frame()] + [ui_frame(255, (440, 60, 80, 40))] * 40)
    monkeypatch.setattr(reader, "_click", lambda *pos: None)
    with pytest.raises(PageError, match="无法切换角色"):
        reader.select_avatar(600, required=True)


def test_avatar_summary_must_respond_before_reading(eidolon_reader, monkeypatch):
    reader, feed, _ = eidolon_reader
    reader.tab = "detail"
    feed([ui_frame()] + [ui_frame(255, reader_module.BREADCRUMB)] * 40)
    monkeypatch.setattr(reader, "_click", lambda *pos: None)
    with pytest.raises(PageError, match="详情区域"):
        reader.select_avatar(600, required=True)


def test_eidolon_empty_first_frames_are_not_six(eidolon_frames, eidolon_reader):
    empty, _, _, two, _ = eidolon_frames
    reader, feed, clock = eidolon_reader
    feed([empty] * 4 + [two] * 5)
    assert reader.read_eidolon() == 2
    assert clock.captures > 4


@pytest.mark.parametrize("count", range(7))
def test_eidolon_all_counts_need_visible_nodes(count, eidolon_frames, eidolon_reader):
    _, zero, six, _, _ = eidolon_frames
    frame = zero.copy()
    for x, y in reader_module.EIDOLON_SLOTS[:count]:
        frame.paste(six.crop((x - 45, y - 45, x + 45, y + 45)), (x - 45, y - 45))
    reader, feed, clock = eidolon_reader
    feed([frame])
    assert reader.read_eidolon() == count
    assert clock.now < 0.5  # 已经就绪的角色无需长时间固定等待，6 魂也一样。


@pytest.mark.parametrize("sample", [0, 4])
def test_eidolon_unready_or_frozen_animation_times_out(sample, eidolon_frames, eidolon_reader):
    reader, feed, clock = eidolon_reader
    feed([eidolon_frames[sample]])
    with pytest.raises(parser.ParseError, match="星魂"):
        reader.read_eidolon()
    assert clock.now <= 3.2


def test_eidolon_never_returns_last_unstable_sample(eidolon_frames, eidolon_reader):
    _, zero, _, two, _ = eidolon_frames
    reader, feed, clock = eidolon_reader
    feed([zero, two] * 40)
    with pytest.raises(parser.ParseError, match="星魂"):
        reader.read_eidolon()
    assert clock.captures < 80


def test_eidolon_ready_only_at_deadline_is_not_success(eidolon_frames, eidolon_reader):
    empty, _, _, two, _ = eidolon_frames
    reader, feed, _ = eidolon_reader
    feed([empty] * 29 + [two])
    with pytest.raises(parser.ParseError, match="星魂"):
        reader.read_eidolon()


def test_eidolon_unknown_frame_resets_stability(eidolon_frames, eidolon_reader):
    empty, _, six, two, _ = eidolon_frames
    reader, feed, clock = eidolon_reader
    feed([six, empty, six, two, two, two])
    assert reader.read_eidolon() == 2
    assert clock.captures >= 6


def test_eidolon_non_contiguous_visible_states_are_rejected(eidolon_frames, eidolon_reader):
    _, zero, six, _, _ = eidolon_frames
    frame = zero.copy()
    x, y = reader_module.EIDOLON_SLOTS[1]
    frame.paste(six.crop((x - 45, y - 45, x + 45, y + 45)), (x - 45, y - 45))
    reader, feed, _ = eidolon_reader
    feed([frame])
    with pytest.raises(parser.ParseError, match="不连续"):
        reader.read_eidolon()


def test_eidolon_missing_lock_match_is_not_an_unlocked_node(eidolon_frames, eidolon_reader, monkeypatch):
    reader, feed, _ = eidolon_reader
    feed([eidolon_frames[1]])
    # 灰色锁定节点即使模板漏检，也不能被当成亮圈的已解锁节点。
    monkeypatch.setattr(reader, "_score", lambda *args: 0)
    with pytest.raises(parser.ParseError, match="星魂"):
        reader.read_eidolon()


@pytest.mark.parametrize("color", [0, 255])
def test_eidolon_uniform_background_is_not_ready(color, eidolon_reader):
    reader, feed, _ = eidolon_reader
    feed([Image.new("RGB", (1920, 1080), (color, color, color))])
    with pytest.raises(parser.ParseError, match="星魂"):
        reader.read_eidolon()


def test_eidolon_readiness_is_checked_again_for_next_character(eidolon_frames, eidolon_reader):
    empty, zero, six, two, _ = eidolon_frames
    reader, feed, _ = eidolon_reader
    for expected, frame in [(6, six), (2, two), (0, zero)]:
        feed([empty] * 4 + [frame] * 5)
        assert reader.read_eidolon() == expected


def test_eidolon_avatar_change_requires_panel_response(monkeypatch):
    reader = reader_module.CharacterReader.__new__(reader_module.CharacterReader)
    reader.tab = "eidolons"
    reader.frame = Image.new("RGB", (1920, 1080))
    monkeypatch.setattr(reader, "grab", lambda: reader.frame)
    monkeypatch.setattr(reader, "_click", lambda *args: None)
    # 名字变了，星魂区域却仍然是上一个角色。
    monkeypatch.setattr(reader, "_settle", lambda box, *args, **kwargs: reader.frame if box == reader_module.BREADCRUMB else None)
    with pytest.raises(PageError, match="星魂"):
        reader.select_avatar(600, required=True)


def test_eidolon_avatar_waits_past_previous_characters_nodes(eidolon_frames, eidolon_reader, monkeypatch):
    empty, _, six, two, _ = eidolon_frames
    reader, feed, _ = eidolon_reader
    old = six.copy()
    renamed = six.copy()
    loading = empty.copy()
    ready = two.copy()
    # 名字先变，旧角色节点稍后才消失；真实 _settle 必须等待右侧星魂区域也变化。
    x, y, width, height = reader_module.BREADCRUMB
    for frame in [renamed, loading, ready]:
        frame.paste((255, 255, 255), (x, y, x + width, y + height))
    feed([old] + [renamed] * 5 + [loading] * 2 + [ready] * 5)
    monkeypatch.setattr(reader, "_click", lambda *args: None)
    assert reader.select_avatar(600, required=True)
    assert reader.read_eidolon() == 2


def test_eidolon_background_motion_cannot_confirm_new_character(eidolon_frames, eidolon_reader, monkeypatch):
    _, _, six, two, _ = eidolon_frames
    reader, feed, _ = eidolon_reader
    frames = [six.copy()]
    x, y, width, height = reader_module.BREADCRUMB
    for index in range(20):
        frame = six.copy()
        frame.paste((255, 255, 255), (x, y, x + width, y + height))
        # 右侧立绘已在动，但六个节点仍是上个角色，不能提前把 2 魂读成 6 魂。
        color = 100 if index % 2 else 200
        frame.paste((color, color, color), (1480, 120, 1880, 300))
        frames.append(frame)
    ready = two.copy()
    ready.paste((255, 255, 255), (x, y, x + width, y + height))
    feed(frames + [ready] * 5)
    monkeypatch.setattr(reader, "_click", lambda *args: None)
    assert reader.select_avatar(600, required=True)
    assert reader.read_eidolon() == 2


def test_eidolon_fading_previous_nodes_must_settle_before_reading(eidolon_frames, eidolon_reader, monkeypatch):
    _, _, six, two, _ = eidolon_frames
    reader, feed, _ = eidolon_reader
    x, y, width, height = reader_module.BREADCRUMB
    frames = [six.copy()]
    for brightness in [1, 1, 0.98, 0.94, 0.90, 0.86, 0.82, 0.78]:
        frame = six.point(lambda value: round(value * brightness))
        frame.paste((255, 255, 255), (x, y, x + width, y + height))
        frames.append(frame)
    ready = two.copy()
    ready.paste((255, 255, 255), (x, y, x + width, y + height))
    feed(frames + [ready] * 8)
    monkeypatch.setattr(reader, "_click", lambda *args: None)
    assert reader.select_avatar(600, required=True)
    assert reader.read_eidolon() == 2


def test_eidolon_unready_uses_existing_retry(eidolon_frames, eidolon_reader):
    empty, _, _, two, _ = eidolon_frames
    reader, feed, clock = eidolon_reader
    feed([empty] * 31 + [two] * 5)
    assert CharacterExport(reader)._read_eidolon() == 2
    assert clock.now > 3


def test_eidolon_failure_cannot_save_a_character(tmp_path, eidolon_frames, eidolon_reader, monkeypatch):
    reader, feed, _ = eidolon_reader
    feed([eidolon_frames[0]])
    sections = SectionReader()
    monkeypatch.setattr(sections, "read_eidolon", reader.read_eidolon)
    job = CharacterExport(sections, partial=str(tmp_path / "partial.json"))
    with pytest.raises(parser.ParseError, match="星魂"):
        job.read_character()
    assert job.characters == []
    assert not Path(job.partial).exists()


def test_missing_avatar_bar_is_retryable():
    reader = reader_module.CharacterReader.__new__(reader_module.CharacterReader)
    reader.frame = Image.new("RGB", (1920, 1080))
    with pytest.raises(PageError, match="头像"):
        reader.avatar_slots()


@pytest.mark.parametrize("types", [[], ["普攻", "战技", "终结技"]])
def test_incomplete_skill_list_is_not_a_success(types, monkeypatch):
    reader = reader_module.CharacterReader.__new__(reader_module.CharacterReader)
    reader.frame = None
    monkeypatch.setattr(reader_module, "auto", SimpleNamespace())
    monkeypatch.setattr(reader, "open_tab", lambda tab: None)
    monkeypatch.setattr(reader, "_act", lambda *args, **kwargs: None)
    monkeypatch.setattr(reader, "_press", lambda key: None)
    monkeypatch.setattr(reader, "_settle", lambda *args, **kwargs: None)
    monkeypatch.setattr(reader, "_submit", lambda *args: Done([L(skill, 1600, 450) for skill in types]))
    with pytest.raises(parser.ParseError, match="技能列表"):
        reader.read_skills_by_panel()


@pytest.mark.parametrize("preview_animation", [False, True])
def test_skill_fallback_clicks_icons_and_checks_content_during_preview(preview_animation, monkeypatch):
    reader = reader_module.CharacterReader.__new__(reader_module.CharacterReader)
    reader.frame = object()
    labels = [L("普攻", 1567, 519), L("天赋", 1806, 518), L("终结技", 1685, 540),
              L("欢愉技", 1685, 652), L("战技", 1567, 679)]
    panels = iter([Done([L(line.text, 1000, 142), L("等级10", 1400, 238)]) for line in labels])
    clicks = []

    def act(action, box, **kwargs):
        action()
        if preview_animation and box == reader_module.SKILL_PANEL:
            raise PageError("预览动画尚未静止")

    monkeypatch.setattr(reader_module, "auto", SimpleNamespace())
    monkeypatch.setattr(reader, "open_tab", lambda tab: None)
    monkeypatch.setattr(reader, "_click", lambda x, y: clicks.append((x, y)))
    monkeypatch.setattr(reader, "_act", act)
    monkeypatch.setattr(reader, "_press", lambda key: None)
    monkeypatch.setattr(reader, "_settle", lambda *args, **kwargs: None)
    monkeypatch.setattr(reader, "_submit", lambda image, box: Done(labels) if box == reader_module.SKILL_LABELS else next(panels))
    skills, problems = reader.read_skills_by_panel()
    assert (1685, 608) in clicks
    assert {skill["type"] for skill in skills} == {line.text for line in labels}
    assert problems == []


def test_unconfirmed_equipped_relic_is_not_an_empty_slot(monkeypatch):
    reader = reader_module.CharacterReader.__new__(reader_module.CharacterReader)
    monkeypatch.setattr(reader, "open_tab", lambda tab: None)
    monkeypatch.setattr(reader, "_score", lambda *args: 0)
    monkeypatch.setattr(reader, "_act", lambda *args, **kwargs: None)
    monkeypatch.setattr(reader, "_wait_unequip_button", lambda frame: None)
    with pytest.raises(PageError, match="头部"):
        reader.begin_relics()


@pytest.mark.parametrize(("position", "slot"), [((866, 393), "连结绳"), ((971, 636), "位面球")])
def test_single_planar_relic_uses_the_actual_overview_position(position, slot, monkeypatch):
    reader = reader_module.CharacterReader.__new__(reader_module.CharacterReader)
    frame = object()
    monkeypatch.setattr(reader_module, "auto", SimpleNamespace())
    monkeypatch.setattr(reader, "open_tab", lambda tab: frame)
    monkeypatch.setattr(reader, "_act", lambda *args, **kwargs: frame)
    monkeypatch.setattr(reader, "_score", lambda image, template, box: 0 if box[:2] == (position[0]-30, position[1]-30) else 1)
    monkeypatch.setattr(reader, "_wait_unequip_button", lambda image: image)
    monkeypatch.setattr(reader, "_submit", lambda *args, **kwargs: Done([]))
    monkeypatch.setattr(reader, "_submit_cells", lambda *args: {})
    pending = reader.begin_relics()
    assert [piece[0] for piece in pending] == [slot]


def test_relic_from_wrong_slot_is_rejected():
    result, problems = relic_reader().finish_relics([("手部", Done(RELIC), {})])
    assert result["pieces"] == []
    assert any("部位" in problem for problem in problems)


def test_incomplete_export_reports_task_failure(monkeypatch):
    from tasks import character_export

    monkeypatch.setattr(character_export, "CharacterExport", lambda: SimpleNamespace(run=lambda: False))
    with pytest.raises(RuntimeError, match="未完成"):
        character_export.run()
