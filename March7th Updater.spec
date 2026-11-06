# -*- mode: python ; coding: utf-8 -*-
import sys

sys.path.append(SPECPATH)
from tools.pyinstaller_openssl import OPENSSL_RUNTIME_HOOKS, python_openssl_binaries


a = Analysis(
    ['updater.py'],
    pathex=[],
    binaries=python_openssl_binaries(),
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=OPENSSL_RUNTIME_HOOKS,
    excludes=['numpy', 'pandas', 'opencc'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='March7th Updater',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
    icon=['assets\\logo\\Updater.ico'],
)
