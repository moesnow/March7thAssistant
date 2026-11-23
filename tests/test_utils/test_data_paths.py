import ast
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from utils import paths


ROOT = Path(__file__).resolve().parents[2]


def test_paths_remain_fixed_after_chdir(tmp_path, monkeypatch):
    current = paths.select(tmp_path)
    monkeypatch.setattr(paths, "_layout", current)
    monkeypatch.chdir(tmp_path.parent)
    assert Path(paths.config_path()) == current.root / "config.yaml"
    assert Path(paths.gacha_path()) == current.root / "gacha/warp.json"
    assert Path(paths.browser_profile_dir()) == current.root / "browser"
    assert Path(paths.characters_path(partial=True)) == current.root / "exports/characters.partial.json"
    assert Path(paths.universe_config_path(tmp_path, legacy=True)) == tmp_path / "info_old.yml"
    assert Path(paths.fight_config_path(tmp_path)) == tmp_path / "config.json"
    assert Path(paths.config_backup_path(tmp_path / "custom.yml")) == tmp_path / "custom.yml.bak"
    assert not current.root.exists()


def test_browser_resolves_the_profile_when_preparing_a_session(tmp_path, monkeypatch):
    from module.game.cloud import CloudGameController
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(paths, "_layout", paths.select(tmp_path))
    # Explicit binaries take the existing fast path without starting a browser or a download.
    monkeypatch.setenv('MARCH7TH_BROWSER_PATH', 'browser')
    monkeypatch.setenv('MARCH7TH_DRIVER_PATH', 'driver')
    controller = SimpleNamespace(BROWSER_INSTALL_PATH=CloudGameController.BROWSER_INSTALL_PATH,
                                 cfg=SimpleNamespace(browser_type='chrome'), log_debug=lambda _: None)
    assert CloudGameController._prepare_browser_and_driver(controller, 'chrome', False) == ('browser', 'driver')
    assert Path(controller.user_profile_path) == tmp_path / 'userdata/browser/Chrome'


def test_docker_mounts_match_the_runtime_paths():
    from ruamel.yaml import YAML
    compose = YAML(typ='safe').load(ROOT / 'docker-compose.yml')
    volumes = compose['services']['march7thassistant']['volumes']
    assert volumes == ['./userdata:/m7a/userdata']


def test_workflow_metadata_stays_absolute_after_chdir(tmp_path, monkeypatch):
    from module import workflow
    monkeypatch.chdir(tmp_path)
    root = tmp_path / 'userdata' / 'workflows'
    monkeypatch.setattr(workflow, 'WORKFLOW_USER_ROOT', str(root))
    monkeypatch.setattr(workflow, 'WORKFLOW_CURRENT_FILE', str(root / '.current'))
    name = 'working-directory-test'
    workflow.save_workflows([{'name': name}])
    saved = next(item for item in workflow.load_workflows() if item['name'] == name)
    directory = root / saved['_workflow_dir_name']
    assert saved['_workflow_base_dir'] == str(directory)
    assert (directory / 'workflow.yaml').is_file()


def test_updater_keeps_archive_marker_spelling():
    from module.update.update_engine import USER_DATA_MARKERS
    assert USER_DATA_MARKERS == ('config.yaml', 'config.yaml.bak', 'settings', 'config/workflows', 'userdata')


# Only desktop Python sources and entry points own these paths. Other trees are separate consumers.
EXCLUDED_TREES = {
    'userdata': 'Private runtime files, never application source.',
    'tests': 'Fixtures intentionally assert the literal legacy paths.',
    'docs': 'Documentation, including literal paths for users.',
    'website': 'Public documentation website.',
    'assets': 'Shipped data, sample configuration and vendored installation scripts.',
    'Android': 'Independent Android application with its own storage.',
    '3rdparty': 'External tools own their private file formats and locations.',
    'config': 'Workflow files created at runtime.',
    'settings': 'Local accounts and UI preferences.',
    'logs': 'Logs and diagnostics created at runtime.',
    'temp': 'Update staging and runtime control files.',
    'screenshots': 'User captures.',
}
EXCLUDED_FILES = {
    'utils/paths.py': 'Single source of the paths.',
    'build.py': 'Build and packaging, not a desktop runtime entry point.',
}
# Match the expression, not the entire file. A new open("temp") in main.py must still fail.
OTHER_MEANINGS = {
    ('app/content/__init__.py', '{"setting": "settings", "task": "tasks"}'),  # Python package under app.content.
    ('tasks/game/__init__.py', 'cloud_click_element("Settings", "text", 0.9, take_screenshot=False)'),  # Game button.
    ('main.py', 'mode == "temp"'),              # Currency wars / universe resume mode.
    ('main.py', 'currencywars("temp")'),
    ('main.py', 'divergent("temp")'),
    ('tasks/daily/fight.py', 'os.path.join(cfg.fight_path, "logs")'),  # External tool's own logs.
    ('tasks/weekly/universe.py', 'os.path.join(cfg.universe_path, "logs")'),
    ('utils/temporary_graphics.py', 'os.environ.get("LOCALAPPDATA", "settings")'),  # OS fallback.
    ('module/docs/paths.py', '"Settings"'),  # English breadcrumb root printed in the manuals.
}

# Only the dictionary keys identify a desktop page. Values and file operations are checked normally.
PAGE_ID_TABLES = {('module/navigation.py', 'TOP_PAGES'), ('module/search/setting_text.py', 'PAGE_DESCRIPTIONS')}

DATA_DIRS = {
    'settings', 'config/workflows', 'logs', 'screenshots', 'temp', '3rdparty/webbrowser/userprofile',
}
DATA_FILES = {
    'config.yaml', 'config.yaml.bak', 'warp.json', 'characters.json', 'characters.partial.json',
    'cookies.enc', 'qrcode_login.png', 'info.yml', 'info_old.yml', 'crash.log', 'config_diag.log', 'userprofile',
    '3rdparty/fhoe-rail/config.json',
}


def _literal_path(node):
    """Also recognize Paths built from components, and the stable prefix of an f-string."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Attribute) and node.attr == 'fight_path':
        return '3rdparty/Fhoe-Rail'
    if isinstance(node, ast.JoinedStr):
        return ''.join(_literal_path(part) or '{}' for part in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return '/'.join(_literal_path(part) or '{}' for part in (node.left, node.right))
    if isinstance(node, ast.Call) and ast.unparse(node.func) in ('os.path.join', 'Path', 'pathlib.Path'):
        return '/'.join(_literal_path(arg) or '{}' for arg in node.args)
    return ''


def _is_data_path(value):
    name = value.replace('\\', '/').removeprefix('{}/').removeprefix('./').lower().rstrip('/')
    return (name in DATA_FILES or name.startswith('config.yaml.') or
            any(name == folder or name.startswith(folder + '/') for folder in DATA_DIRS))


def _unmanaged_paths(source, relative):
    tree = ast.parse(source)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    for node, parent in parents.items():
        value = _literal_path(node)
        if not value or not _is_data_path(value) or isinstance(parent, ast.Expr):
            continue
        if value == 'settings' and isinstance(parent, ast.Dict) and node in parent.keys:
            owner = parents.get(parent)
            if isinstance(owner, ast.Assign) and any(isinstance(target, ast.Name) and
                    (relative, target.id) in PAGE_ID_TABLES for target in owner.targets):
                continue
        if any((relative, ast.get_source_segment(source, item)) in OTHER_MEANINGS for item in (node, parent)):
            continue
        yield f'{relative}:{node.lineno}: {value}'


@pytest.mark.parametrize('relative, declaration', [
    ('module/navigation.py', 'TOP_PAGES = {"settings": ("设置", "settingInterface", "FIF.SETTING")}'),
    ('module/search/setting_text.py', 'PAGE_DESCRIPTIONS = {"settings": "调整程序设置"}'),
    ('app/content/__init__.py', 'package = {"setting": "settings", "task": "tasks"}[kind]'),
])
def test_page_ids_do_not_exempt_file_access(relative, declaration):
    source = declaration + '\nopen("settings")\nfolder = Path("settings") / "accounts"'
    errors = list(_unmanaged_paths(source, relative))
    assert f'{relative}:2: settings' in errors
    assert f'{relative}:3: settings/accounts' in errors
    assert not any(error.startswith(f'{relative}:1:') for error in errors)


def test_runtime_uses_central_paths():
    errors = []
    for directory, folders, files in os.walk(ROOT):
        # Ignore hidden tooling dirs and generated files, including pytest's private working directory.
        folders[:] = [d for d in folders if not d.startswith('.') and d != '__pycache__'
                      and not (Path(directory) == ROOT and d in EXCLUDED_TREES)]
        for filename in files:
            if not filename.endswith(('.py', '.pyw')):
                continue
            path = Path(directory, filename)
            relative = path.relative_to(ROOT).as_posix()
            if relative in EXCLUDED_FILES:
                continue
            source = path.read_text(encoding='utf-8-sig')
            errors.extend(_unmanaged_paths(source, relative))
    assert not errors, '\n' + '\n'.join(errors)
