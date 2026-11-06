"""打包时的 OpenSSL 处理：三个 spec 共用 tools/pyinstaller_openssl.py"""
import os
import runpy
from pathlib import Path

import pytest

from tools.pyinstaller_openssl import OPENSSL_DLLS, OPENSSL_RUNTIME_HOOKS, python_openssl_binaries

REPO = Path(__file__).resolve().parents[2]
SPECS = ["March7th Assistant.spec", "March7th Launcher.spec", "March7th Updater.spec"]
OPENSSL_ENV_KEYS = ("SSLKEYLOGFILE", "OPENSSL_CONF")


@pytest.mark.parametrize("spec", SPECS)
def test_spec_uses_shared_openssl_rules(spec):
    text = (REPO / spec).read_text(encoding="utf-8")
    assert "python_openssl_binaries()" in text
    assert "runtime_hooks=OPENSSL_RUNTIME_HOOKS" in text


def test_binaries_point_to_interpreter_dlls_dir(monkeypatch):
    monkeypatch.setattr("sys.base_prefix", os.path.join("build", "python"))

    assert python_openssl_binaries() == [
        (os.path.join("build", "python", "DLLs", name), ".") for name in OPENSSL_DLLS
    ]


def test_runtime_hook_removes_openssl_env(monkeypatch):
    for key in OPENSSL_ENV_KEYS:
        monkeypatch.setenv(key, "value")

    for hook in OPENSSL_RUNTIME_HOOKS:
        runpy.run_path(hook)

    assert not [key for key in OPENSSL_ENV_KEYS if key in os.environ]
