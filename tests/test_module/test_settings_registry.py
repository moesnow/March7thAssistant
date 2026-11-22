import subprocess
import sys
from pathlib import Path

from ruamel.yaml import YAML

from module.settings_registry import SETTINGS, Scope, find_setting


def test_registry_import_is_independent_of_the_gui_and_local_config():
    subprocess.run([sys.executable, '-c', """
import sys
import module.settings_registry
assert not {'PySide6', 'qfluentwidgets', 'module.config'} & sys.modules.keys()
"""], check=True)


def test_keys_locations_and_scopes_are_consistent():
    example = YAML(typ='safe').load(Path('assets/config/config.example.yaml'))
    keys = [key for setting in SETTINGS for key in setting.keys]
    locations = [(s.tab, s.group, s.parents, s.title) for s in SETTINGS]
    assert len(keys) == len(set(keys))
    assert len(locations) == len(set(locations))
    assert set(keys) <= example.keys()
    for setting in SETTINGS:
        assert set(setting.state_keys + setting.secret_keys) <= set(setting.keys)
        assert all(find_setting(key) is setting for key in setting.keys)
    assert find_setting('currencywars_timestamp').key_scope('currencywars_timestamp') == Scope.STATE
    assert find_setting('notify_telegram_token').scope == Scope.SECRET
    assert find_setting('github_token').key_scope('github_token') == Scope.SECRET
