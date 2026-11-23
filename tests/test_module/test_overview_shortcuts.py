from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from module.overview.legacy_cards import DEFAULT_CARDS
from module.overview import shortcuts as sc
from module.overview.types import Shortcut, ShortcutAction


class Config:
    control_backend = "local"
    ui_profile = "pc_1080"

    def __init__(self, **values):
        self.values = values
        self.writes = []

    def get_value(self, key, default=None):
        return self.values.get(key, default)

    def set_value(self, key, value):
        self.writes.append(key)
        self.values[key] = value


@pytest.mark.parametrize("legacy", [None, DEFAULT_CARDS, "bad", [None, 1]])
def test_install_and_defaults(legacy):
    cfg = Config(home_cards=deepcopy(legacy))
    assert sc.load_shortcuts(cfg) == sc.defaults() == sc.load_shortcuts(cfg)
    assert cfg.writes == [] and cfg.values["home_cards"] == legacy


@pytest.mark.parametrize("name", [*sc.PORTRAITS, "Evernight"])
def test_builtin_files_and_custom_namesakes(name, tmp_path):
    dark = Path("assets/app/images/dark") / (name + ".png")
    paths = [str(dark.absolute()), "./" + dark.as_posix(), str(tmp_path / dark.name)]
    if name != "Evernight":
        paths.append("assets\\app\\images\\" + name + ".jpg")
    for i, path in enumerate(paths):
        raw = [{"title": "我的清体力", "icon": path, "action_type": "single", "task_id": "power"}]
        item, = sc.migrate(raw)
        assert item.image == (path if i == 2 else None)
        assert item.icon == "UiIcon.BATTERY_CHARGE" and item.name == "我的清体力"


def test_menu_order_duplicate_actions_and_broken_rows():
    old = deepcopy(DEFAULT_CARDS[2])
    old.update(title="我的货币菜单", icon="D:/我的图/Yanqing.jpg")
    other = {"task_id": "main", "title": "副入口", "menu_items": 123, "action_type": "single"}
    cfg = Config(home_cards=[None, old, other, other])
    original = deepcopy(cfg.values["home_cards"])
    menu, second, third = sc.load_shortcuts(cfg)
    assert menu.id == "menu" and menu.image == old["icon"]
    assert [item.id for item in menu.menu] == [item["task_id"] for item in old["menu_items"]]
    assert second == third and second.id == "main"
    assert original == cfg.values["home_cards"] and cfg.writes == []


def test_editor_save_cancel_reset_and_conflict():
    cfg = Config(home_cards=[])
    assert sc.load_shortcuts(cfg) == ()
    a, b = sc.ShortcutEditor(cfg), sc.ShortcutEditor(cfg)
    menu = Shortcut("menu", "常用功能", "UiIcon.LIST", "a.png", (ShortcutAction("screenshot", "截图"),))
    a.add(menu)
    a.add(sc.defaults()[0])
    a.move(1, 0)
    a.replace(1, replace(menu, image="b.png", menu=(ShortcutAction("power", "清一次"), *menu.menu)))
    a.remove(0)
    assert sc.load_shortcuts(cfg) == ()  # 尚未按保存
    a.save()
    saved, = sc.load_shortcuts(cfg)
    assert saved.image == "b.png" and [x.id for x in saved.menu] == ["power", "screenshot"]
    b.reset()
    with pytest.raises(ValueError):
        b.save()
    a.reset()
    a.save()
    assert sc.load_shortcuts(cfg) == sc.defaults() and cfg.values["home_cards"] == []
    a.replace(0, replace(sc.defaults()[0], name=" "))
    with pytest.raises(ValueError):
        a.save()
    assert sc.load_shortcuts(cfg) == sc.defaults()


def test_existing_bad_new_key_never_reads_old_cards_or_overwrites():
    cfg = Config(overview_shortcuts=[None, {"id": "screenshot", "icon": {}, "image": 3}], home_cards=[])
    items = sc.load_shortcuts(cfg)
    assert items == (sc.defaults()[-1],) and not cfg.writes
    cfg.values[sc.KEY] = "broken"
    assert sc.load_shortcuts(cfg) == sc.defaults() and not cfg.writes


def test_unsupported_entries_survive_filter_and_restore():
    cfg = Config(home_cards=deepcopy(DEFAULT_CARDS[1:]))
    editor = sc.ShortcutEditor(cfg)
    cfg.control_backend = "adb"
    assert all(s.id != "autoplot" for s in sc.display_shortcuts(cfg))
    assert len(sc.display_shortcuts(cfg)) == 1  # 日常子菜单
    assert len(editor.items) == len(sc.load_shortcuts(cfg)) == len(DEFAULT_CARDS) - 1
    cfg.control_backend = "local"
    assert len(sc.display_shortcuts(cfg)) == len(editor.items)


def test_display_and_opening_editor_reuse_conversion_without_writes(monkeypatch):
    cfg = Config(home_cards=deepcopy(DEFAULT_CARDS[1:3]))
    cfg.writes_suspended = True
    convert = Mock(wraps=sc.migrate)
    monkeypatch.setattr(sc, "migrate", convert)
    expected = sc.load_shortcuts(cfg)
    assert sc.display_shortcuts(cfg) == expected
    editor = sc.ShortcutEditor(cfg)
    assert editor.items == list(expected) and convert.call_count == 1
    with pytest.raises(ValueError):
        editor.save()
    cfg.writes_suspended = False
    cfg.values["home_cards"][0]["title"] = "另一个窗口修改了旧卡片"
    with pytest.raises(ValueError):
        editor.save()
    assert convert.call_count == 2
    assert cfg.writes == [] and sc.KEY not in cfg.values
    fresh = sc.ShortcutEditor(cfg)
    fresh.save()
    assert cfg.writes == [sc.KEY] and sc.load_shortcuts(cfg)[0].name == cfg.values["home_cards"][0]["title"]


def test_failed_save_keeps_draft_for_retry(monkeypatch):
    cfg = Config(home_cards=[])
    editor = sc.ShortcutEditor(cfg)
    editor.reset()
    with monkeypatch.context() as patch:
        patch.setattr(cfg, "set_value", Mock(side_effect=OSError("只读")))
        with pytest.raises(OSError):
            editor.save()
    assert editor.items == list(sc.defaults()) and sc.KEY not in cfg.values
    editor.save()
    assert sc.load_shortcuts(cfg) == sc.defaults() and cfg.writes == [sc.KEY]


def test_translated_factory_cards_and_similar_custom_order(monkeypatch):
    from module import localization
    monkeypatch.setattr(localization, "translations_of", lambda name: {"en_US": "old " + name})
    old = deepcopy(DEFAULT_CARDS)
    for card in old:
        card["title"] = "old " + card["title"]
        for item in card["menu_items"]:
            item["label"] = "old " + item["label"]
    assert sc.migrate(old) == sc.defaults()
    old.reverse()
    assert len(sc.migrate(old)) == len(DEFAULT_CARDS)


def test_first_save_with_two_file_backed_editors(tmp_path):
    from module.config.config import Config as FileConfig

    path = tmp_path / "config.yaml"
    path.write_text("home_cards: []\n", encoding="utf-8")

    def reader():
        config = FileConfig.__new__(FileConfig)
        FileConfig.__init__(config, "assets/config/version.txt", "assets/config/config.example.yaml", str(path))
        return config

    first, second = reader(), reader()
    initial = path.read_bytes()
    a, b = sc.ShortcutEditor(first), sc.ShortcutEditor(second)
    assert sc.display_shortcuts(first) == ()
    assert path.read_bytes() == initial and not (tmp_path / ".overview-shortcuts.lock").exists()
    a.add(sc.defaults()[0])
    b.add(sc.defaults()[1])
    a.save()
    with pytest.raises(ValueError):
        b.save()
    assert b.items == [sc.defaults()[1]]
    stored = reader()
    assert sc.load_shortcuts(stored) == (sc.defaults()[0],)
    assert stored.get_value("home_cards") == []
