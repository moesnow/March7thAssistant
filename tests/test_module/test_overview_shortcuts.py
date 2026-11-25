from copy import deepcopy
from dataclasses import replace
from unittest.mock import Mock

import pytest

from module.overview import shortcuts as sc
from module.overview.types import Shortcut, ShortcutAction
from module.task_catalog import BY_ID


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


@pytest.mark.parametrize("values", [{}, {"home_cards": []},
                                    {"home_cards": [{"task_id": "main", "title": "旧主页按钮"}]}])
def test_no_saved_shortcuts_use_defaults(values):
    cfg = Config(**values)
    items = sc.load_shortcuts(cfg)
    names = ("运行一次", "循环运行", "中途接管")
    assert [(item.id, item.name, tuple((child.id, child.name) for child in item.menu)) for item in items] == [
        ("routine", "日常", ()), ("power", "清体力", ()),
        ("menu", "货币战争", tuple(zip(("currencywars", "currencywarsloop", "currencywarstemp"), names))),
        ("menu", "差分宇宙", tuple(zip(("divergent", "divergentloop", "divergenttemp"), names))),
    ]
    assert tuple((child.id, child.name) for child in items[2].menu) == BY_ID["currencywars"].menu
    assert cfg.writes == []


def test_saved_defaults_follow_later_defaults(monkeypatch):
    cfg = Config()
    sc.ShortcutEditor(cfg).save()
    editor = sc.ShortcutEditor(cfg)
    editor.remove(0)
    editor.save()
    assert len(cfg.values[sc.KEY]) == 3
    editor.reset()
    editor.save()
    assert cfg.values[sc.KEY] is None and cfg.writes == [sc.KEY] * 3
    later = (Shortcut("main", "完整运行", "FIF.PLAY"),)
    monkeypatch.setattr(sc, "defaults", lambda: later)
    assert sc.load_shortcuts(cfg) == later


def test_saved_menu_order_and_icons_survive_obsolete_image_fields():
    row = {"id": "menu", "name": "我的货币菜单", "icon": "UiIcon.STAR", "image": "custom.png",
           "menu": [{"id": "currencywars", "name": "打一局"}, {"id": "currencywarsloop", "name": "循环"}]}
    other = {"id": "main", "name": "副入口", "image": "main.png"}
    cfg = Config(overview_shortcuts=[None, row, other, other])
    original = deepcopy(cfg.values[sc.KEY])
    editor = sc.ShortcutEditor(cfg)
    menu, second, third = editor.items
    assert menu == Shortcut("menu", "我的货币菜单", "UiIcon.STAR", (
        ShortcutAction("currencywars", "打一局"), ShortcutAction("currencywarsloop", "循环")))
    assert second == third == Shortcut("main", "副入口", "FIF.PLAY")
    assert cfg.values[sc.KEY] == original and cfg.writes == []
    editor.save()
    assert all("image" not in item for item in cfg.values[sc.KEY])
    assert sc.load_shortcuts(cfg) == (menu, second, third)


def test_editor_save_cancel_reset_and_conflict():
    cfg = Config(overview_shortcuts=[])
    assert sc.load_shortcuts(cfg) == ()
    a, b = sc.ShortcutEditor(cfg), sc.ShortcutEditor(cfg)
    menu = Shortcut("menu", "常用功能", "UiIcon.LIST", (ShortcutAction("screenshot", "截图"),))
    a.add(menu)
    a.add(sc.defaults()[0])
    a.move(1, 0)
    a.replace(1, replace(menu, menu=(ShortcutAction("power", "清一次"), *menu.menu)))
    a.remove(0)
    assert sc.load_shortcuts(cfg) == ()  # 尚未按保存
    a.save()
    saved, = sc.load_shortcuts(cfg)
    assert saved.icon == "UiIcon.LIST" and [x.id for x in saved.menu] == ["power", "screenshot"]
    b.reset()
    with pytest.raises(ValueError):
        b.save()
    a.reset()
    a.save()
    assert sc.load_shortcuts(cfg) == sc.defaults()
    a.replace(0, replace(sc.defaults()[0], name=" "))
    with pytest.raises(ValueError):
        a.save()
    assert sc.load_shortcuts(cfg) == sc.defaults()


def test_invalid_shortcuts_use_fallbacks_without_writing():
    cfg = Config(overview_shortcuts=[None, {"id": "screenshot", "icon": {}}])
    items = sc.load_shortcuts(cfg)
    assert items == (Shortcut("screenshot", "游戏截图", sc.icon_for("screenshot")),) and not cfg.writes
    cfg.values[sc.KEY] = "broken"
    assert sc.load_shortcuts(cfg) == sc.defaults() and not cfg.writes


def test_unsupported_entries_survive_filter_and_restore():
    cfg = Config(overview_shortcuts=[
        {"id": "menu", "name": "日常", "menu": [{"id": "routine"}, {"id": "currencywars"}]},
        {"id": "autoplot"}, {"id": "divergent"},
    ])
    editor = sc.ShortcutEditor(cfg)
    cfg.control_backend = "adb"
    menu, = sc.display_shortcuts(cfg)
    assert menu.id == "menu" and [child.id for child in menu.menu] == ["routine"]
    assert tuple(editor.items) == sc.load_shortcuts(cfg)
    cfg.control_backend = "local"
    assert len(sc.display_shortcuts(cfg)) == len(editor.items)


def test_display_and_opening_editor_leave_config_untouched():
    cfg = Config(overview_shortcuts=[{"id": "power", "name": "我的清体力"}])
    cfg.writes_suspended = True
    expected = sc.load_shortcuts(cfg)
    assert sc.display_shortcuts(cfg) == expected
    editor = sc.ShortcutEditor(cfg)
    assert editor.items == list(expected)
    with pytest.raises(ValueError):
        editor.save()
    cfg.writes_suspended = False
    cfg.values[sc.KEY][0]["name"] = "另一个窗口修改了快捷启动"
    with pytest.raises(ValueError):
        editor.save()
    assert cfg.writes == []
    fresh = sc.ShortcutEditor(cfg)
    fresh.save()
    assert cfg.writes == [sc.KEY] and sc.load_shortcuts(cfg)[0].name == "另一个窗口修改了快捷启动"


def test_failed_save_keeps_draft_for_retry(monkeypatch):
    cfg = Config(overview_shortcuts=[])
    editor = sc.ShortcutEditor(cfg)
    editor.reset()
    with monkeypatch.context() as patch:
        patch.setattr(cfg, "set_value", Mock(side_effect=OSError("只读")))
        with pytest.raises(OSError):
            editor.save()
    assert editor.items == list(sc.defaults()) and cfg.values[sc.KEY] == []
    editor.save()
    assert sc.load_shortcuts(cfg) == sc.defaults() and cfg.writes == [sc.KEY]


def test_first_save_with_two_file_backed_editors(tmp_path):
    from module.config.config import Config as FileConfig

    path = tmp_path / "config.yaml"
    path.write_text("overview_shortcuts: []\nhome_cards: [{task_id: power, title: 旧版按钮}]\n", encoding="utf-8")

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
    assert "home_cards" not in stored.yaml.load(path)
    editor = sc.ShortcutEditor(stored)
    editor.reset()
    editor.save()
    assert stored.yaml.load(path)[sc.KEY] is None and sc.load_shortcuts(reader()) == sc.defaults()
