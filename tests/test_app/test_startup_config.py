"""旧更新器传入只读角色时，主程序仍应保存设置；不启动 GUI 或请求提权。"""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
CONFIG_LOADER = """
import importlib.util
from pathlib import Path
import sys

def load_config(root):
    sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location(
        "config_under_test", Path(root) / "module/config/config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = module.Config("version.txt", "example.yaml", "config.yaml")
    return module, config
"""


@pytest.mark.parametrize("readonly", [None, "1", "true"])
@pytest.mark.parametrize("frozen", [False, True])
def test_gui_inherited_role_saves_before_project_imports(tmp_path, readonly, frozen):
    # 保持真实入口代码，仅将工作目录重定向到临时安装，避免碰到用户配置。
    entry = tmp_path / "app.py"
    entry.write_bytes((ROOT / "app.py").read_bytes())
    (tmp_path / "version.txt").write_text("test", encoding="utf-8")
    for name in ("example.yaml", "config.yaml"):
        (tmp_path / name).write_text("game_launch_method: direct\n", encoding="utf-8")
    env = os.environ.copy()
    env.pop("MARCH7TH_CONFIG_READONLY", None)
    if readonly is not None:
        env["MARCH7TH_CONFIG_READONLY"] = readonly
    script = """
import builtins
import json
import os
from pathlib import Path
import runpy
import sys

root, entry, frozen = sys.argv[1:]
if frozen == "True":
    sys.frozen = True
    sys.executable = str(Path(entry).with_name("March7th Launcher.exe"))
original_import = builtins.__import__

def inspect_startup(name, *args, **kwargs):
    if name == "utils.dpi":
        # 在首次项目导入处检查角色；包括 --autostart 在内的配置加载都必须晚于此处。
        module, config = load_config(root)
        config.set_value("game_launch_method", "epic")
        with open("config.yaml", encoding="utf-8") as stream:
            disk = config.yaml.load(stream)
        print(json.dumps({"readonly": module.Config._readonly,
                          "memory": config.get_value("game_launch_method"),
                          "disk": disk["game_launch_method"]}))
        raise SystemExit(0)
    return original_import(name, *args, **kwargs)

builtins.__import__ = inspect_startup
sys.argv = [entry, "--autostart", "--no-silent"]
runpy.run_path(entry, run_name="__main__")
"""
    script = CONFIG_LOADER + script
    result = subprocess.run(
        [sys.executable, "-c", script, str(ROOT), str(entry), str(frozen)],
        cwd=tmp_path, env=env, capture_output=True, text=True, check=True, timeout=30,
    )
    assert json.loads(result.stdout) == {"readonly": False, "memory": "epic", "disk": "epic"}

    # 新进程重新加载同一文件，覆盖任务进程不能读取 GUI 内存中设置的实际场景。
    reader = CONFIG_LOADER + """
import json
module, config = load_config(sys.argv[1])
print(json.dumps(config.get_value("game_launch_method")))
"""
    result = subprocess.run(
        [sys.executable, "-c", reader, str(ROOT)], cwd=tmp_path, env=env,
        capture_output=True, text=True, check=True, timeout=30,
    )
    assert json.loads(result.stdout) == "epic"
