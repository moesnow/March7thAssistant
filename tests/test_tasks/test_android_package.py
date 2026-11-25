"""在 APK 的源码范围内冷启动，避免开发机完整源码掩盖 Android 漏包。"""
import ast
import fnmatch
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from zipfile import ZipFile

import pytest


ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / "Android/app/src/main/python/android_task.py"


@pytest.fixture
def packaged_project(tmp_path):
    workspace = tmp_path / "project"
    workspace.mkdir()
    # 本地构建后也可直接检查 Gradle 实际生成的 project.zip。
    archive = os.environ.get("M7A_ANDROID_PROJECT_ZIP")
    if archive:
        with ZipFile(archive) as source:
            source.extractall(workspace)
        return workspace

    # 普通 Python CI 无需安装 Android SDK；直接使用构建文件的同一组打包规则。
    gradle = (ROOT / "Android/app/build.gradle").read_text(encoding="utf-8")
    block = re.search(r"    from\(repo\) \{\n(.*?)\n    }", gradle, re.S)
    assert block is not None
    rules = {"include": [], "exclude": []}
    for line in block[1].splitlines():
        if not line.strip() or line.lstrip().startswith("//"):
            continue
        rule = re.fullmatch(r"\s*(include|exclude) (.*)", line)
        assert rule is not None, f"未支持的打包规则：{line}"
        rules[rule[1]].extend(ast.literal_eval(f"[{rule[2]}]"))
    files = set()
    for pattern in rules["include"]:
        # Gradle 的目录 /** 包含文件，Path.glob 的末尾 ** 仅返回目录。
        files.update(ROOT.glob(pattern + "/*" if pattern.endswith("/**") else pattern))
    for source in files:
        relative = source.relative_to(ROOT)
        if not source.is_file() or any(fnmatch.fnmatchcase(relative.as_posix(), p) for p in rules["exclude"]):
            continue
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return workspace


SMOKE = r'''
import importlib.util
import json
import os
from pathlib import Path
import sys

# 二进制依赖使用宿主实现；项目模块全部在切换平台后从打包目录导入。
import cv2
import numpy
from PIL import Image
import requests
from ruamel.yaml import YAML

workspace, entry, task = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
os.chdir(workspace)
sys.path.insert(0, str(workspace))
sys.platform = "android"
spec = importlib.util.spec_from_file_location("android_task", entry)
android_task = importlib.util.module_from_spec(spec)
spec.loader.exec_module(android_task)

class ImportsReady(BaseException):
    pass

class Bridge:
    def isCancelled(self):
        return False

    def ocrStarting(self):
        from module.config import cfg
        from module.overview.plan import TOUCH, select_steps
        from module.overview.readings import save_reading
        from utils import paths

        assert paths.layout().root == workspace
        assert paths.layout().mode == "legacy"
        assert Path(paths.config_path()) == workspace / "config.yaml"
        assert Path(paths.logs_dir()) == workspace / "logs"
        # 日常编排和体力进度在进入游戏后才调用这些延迟依赖。
        select_steps(TOUCH, cfg, dict.fromkeys(TOUCH, lambda: True), touch=True)
        save_reading(cfg, "overview_power", 120)
        from module.accounts.errors import AccountError
        account_error = AccountError("account_mismatch", "测试账号不符")
        class WrongAccountConfig:
            def set_value(self, key, value):
                raise account_error
        try:
            save_reading(WrongAccountConfig(), "overview_power", 120)
        except AccountError as error:
            assert error is account_error
        else:
            raise AssertionError("账号异常必须继续传播")
        for name, module in tuple(sys.modules.items()):
            if name.split(".")[0] in {"module", "tasks", "utils"}:
                file = getattr(module, "__file__", None)
                assert file is None or Path(file).is_relative_to(workspace), (name, file)
        assert "module.accounts.runtime" not in sys.modules
        raise ImportsReady()

    def log(self, time_ms, level, category, message, heading):
        print(message)

    def reportProgress(self, payload):
        pass

    def cleaning(self):
        pass

with (workspace / "assets/config/config.example.yaml").open(encoding="utf-8") as source:
    defaults = YAML(typ="safe").load(source)
settings = json.dumps({key: defaults[key] for key in android_task.SETTING_KEYS})
try:
    result = android_task.run(str(workspace), "test", 29, "10", "test", False, task,
                              settings, False, False, "zh_CN", Bridge())
except ImportsReady:
    print("Android imports ready:", task)
else:
    raise AssertionError(f"未能完成 Python 初始化：{result}")
'''


def cold_start(workspace, task):
    env = {key: value for key, value in os.environ.items()
           if key not in {"M7A_DATA_DIR", "M7A_SESSION_LAYOUT", "MARCH7TH_CONFIG_READONLY"}}
    return subprocess.run(
        [sys.executable, "-I", "-X", "utf8", "-c", SMOKE, str(workspace), str(ENTRY), task],
        cwd=workspace, env=env, capture_output=True, text=True, encoding="utf-8", timeout=45,
    )


@pytest.mark.parametrize("task", ["ROUTINE", "DAILY", "POWER"])
def test_packaged_android_tasks_finish_python_initialization(packaged_project, task):
    result = cold_start(packaged_project, task)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"Android imports ready: {task}" in result.stdout


def test_missing_paths_cannot_fall_back_to_the_checkout(packaged_project):
    (packaged_project / "utils/paths.py").unlink()
    result = cold_start(packaged_project, "ROUTINE")
    assert result.returncode != 0
    assert "cannot import name 'paths'" in result.stderr
