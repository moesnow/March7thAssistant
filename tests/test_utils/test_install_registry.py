# coding:utf-8
"""utils/install_registry.py 安装登记测试。"""
import json
import os
import subprocess
import sys

import pytest

from utils import install_registry as reg
from utils.runs import process_create_time


@pytest.fixture
def registry_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "local"))
    return tmp_path


def test_register_and_find(registry_home):
    install = str(registry_home / "M7A")
    reg.register_install("v1", install_dir=install)
    entry = reg.find_install(install)
    assert entry["version"] == "v1"
    assert entry["path"] == os.path.abspath(install)
    with open(reg.registry_path(), encoding="utf-8") as f:
        assert json.load(f)["schema"] == reg.REGISTRY_SCHEMA


def test_latest_install_first_and_deduplicated(registry_home):
    a, b = str(registry_home / "A"), str(registry_home / "B")
    reg.register_install("v1", install_dir=a)
    reg.register_install("v1", install_dir=b)
    reg.register_install("v2", install_dir=a)
    installs = reg.load_installs()
    assert [entry["path"] for entry in installs] == [os.path.abspath(a), os.path.abspath(b)]
    assert installs[0]["version"] == "v2"


def test_keeps_at_most_max_installs(registry_home):
    for i in range(reg.MAX_INSTALLS + 3):
        reg.register_install("v1", install_dir=str(registry_home / f"I{i}"))
    assert len(reg.load_installs()) == reg.MAX_INSTALLS


def test_gui_running_detection(registry_home):
    install = str(registry_home / "M7A")
    reg.register_install("v1", install_dir=install)
    assert reg.is_gui_running(install) is None  # 从未登记过图形界面：未知

    reg.register_install("v1", gui_pid=os.getpid(), install_dir=install)
    assert reg.is_gui_running(install) is True
    # 命令行再次登记时保留图形界面信息
    reg.register_install("v1", install_dir=install)
    assert reg.find_install(install)["gui_pid"] == os.getpid()

    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.3)"])
    create_time = process_create_time(proc.pid)
    reg.register_install("v1", gui_pid=proc.pid, install_dir=install)
    proc.wait()
    assert reg.find_install(install)["gui_pid_create_time"] == create_time
    assert reg.is_gui_running(install) is False


def test_corrupt_registry_is_ignored(registry_home):
    os.makedirs(os.path.dirname(reg.registry_path()), exist_ok=True)
    with open(reg.registry_path(), "w", encoding="utf-8") as f:
        f.write("{broken")
    assert reg.load_installs() == []
    reg.register_install("v1", install_dir=str(registry_home / "M7A"))
    assert len(reg.load_installs()) == 1
