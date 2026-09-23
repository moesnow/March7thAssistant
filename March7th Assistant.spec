# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

binaries = []
datas = []

binaries += collect_dynamic_libs('openvino', search_patterns=['openvino_intel_cpu_plugin.dll', 'openvino_onnx_frontend.dll'])

datas += collect_data_files('rapidocr')


a = Analysis(
    ['main.py'],
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
    excludes=['PySide6'],
    noarchive=False,
    optimize=0,
)
# 裁剪确认用不到的二进制与数据，减小打包体积：
# - rapidocr 的 _infer 模型：OCR 固定使用 MOBILE 模型（module/ocr/ocr.py）
# - opencv_videoio_ffmpeg：视频编解码，项目不处理视频
# - Pillow 的 _avif 插件：项目只处理 PNG/JPEG 截图
# - selenium-manager 的 macOS/Linux 版本：Windows 发行版只用 windows 版
# - *.lib：MSVC 链接期导入库，运行时用不到
def _is_excluded(dest_name: str) -> bool:
    dest = dest_name.replace('\\', '/').lower()
    base = dest.rsplit('/', 1)[-1]
    if base.endswith('.lib'):
        return True
    if dest.startswith('rapidocr/') and base.endswith('_infer.onnx'):
        return True
    if 'opencv_videoio_ffmpeg' in base or base.startswith('_avif.'):
        return True
    if dest.startswith('selenium/webdriver/common/macos/') or dest.startswith('selenium/webdriver/common/linux/'):
        return True
    return False


a.binaries = [item for item in a.binaries if not _is_excluded(item[0])]
a.datas = [item for item in a.datas if not _is_excluded(item[0])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='March7th Assistant',
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
    icon=['assets\\logo\\Terminal.ico'],
    contents_directory='libraries',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='March7th Assistant',
)
