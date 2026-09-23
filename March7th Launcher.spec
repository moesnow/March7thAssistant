# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

binaries = []
datas = []

binaries += collect_dynamic_libs('openvino', search_patterns=['openvino_intel_cpu_plugin.dll', 'openvino_onnx_frontend.dll'])

datas += collect_data_files('rapidocr')


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'selenium.webdriver.chrome.webdriver',
        'selenium.webdriver.chrome.service',
        'selenium.webdriver.chrome.options',
        'selenium.webdriver.edge.webdriver',
        'selenium.webdriver.edge.service',
        'selenium.webdriver.edge.options',
        'selenium.webdriver.chromium.webdriver',
        'selenium.webdriver.chromium.service',
        'selenium.webdriver.chromium.options',
        'selenium.webdriver.remote.webdriver',
        'selenium.webdriver.remote.connection',
        'selenium.webdriver.common.service',
        'selenium.webdriver.common.selenium_manager',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='March7th Launcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
    icon=['assets\\logo\\March7th.ico'],
    contents_directory='libraries',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='March7th Launcher',
)
