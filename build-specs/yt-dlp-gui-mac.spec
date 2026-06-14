# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for macOS build

import ast
from pathlib import Path


def read_app_version():
    """Read APP_VERSION from the lightweight version module without importing PySide6."""
    try:
        spec_dir = Path(SPEC).resolve().parent
    except NameError:
        spec_dir = Path(__file__).resolve().parent

    version_file = spec_dir.parent / 'yt_dlp_gui' / 'version.py'
    module = ast.parse(version_file.read_text(encoding='utf-8'))
    for node in module.body:
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == 'APP_VERSION' for target in node.targets)
        ):
            return ast.literal_eval(node.value)

    raise RuntimeError(f"APP_VERSION not found in {version_file}")


APP_VERSION = read_app_version()
block_cipher = None

a = Analysis(
    ['../yt-dlp-gui.py'],
    pathex=[],
    binaries=[],
    datas=[('../assets', 'assets')],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtNetwork',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Unused Qt modules (safe to exclude)
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        'PySide6.QtPrintSupport',
        'PySide6.QtQml',
        'PySide6.QtQuick',
        'PySide6.QtQuickWidgets',
        'PySide6.QtSql',
        'PySide6.QtSvg',
        'PySide6.QtSvgWidgets',
        'PySide6.QtTest',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtXml',
        'PySide6.Qt3DCore',
        'PySide6.Qt3DRender',
        'PySide6.QtBluetooth',
        'PySide6.QtDBus',
        'PySide6.QtDesigner',
        'PySide6.QtHelp',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.QtNfc',
        'PySide6.QtPositioning',
        'PySide6.QtRemoteObjects',
        'PySide6.QtSensors',
        'PySide6.QtSerialPort',
        'PySide6.QtWebChannel',
        'PySide6.QtWebSockets',
        # Only exclude Python modules we're certain aren't needed
        'tkinter',
        'unittest',
        'pydoc',
        'doctest',
        'pdb',
        'bdb',
        'sqlite3',
        'distutils',
        'setuptools',
        'pip',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='yt-dlp-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,
    upx=False,
    upx_exclude=[],
    name='yt-dlp-gui',
)

app = BUNDLE(
    coll,
    name='yt-dlp-gui.app',
    icon='../assets/logo.png',
    bundle_identifier='com.mme89.yt-dlp-gui',
    version=APP_VERSION,
    info_plist={
        'CFBundleName': 'yt-dlp GUI',
        'CFBundleDisplayName': 'yt-dlp GUI',
        'CFBundleShortVersionString': APP_VERSION,
        'CFBundleVersion': APP_VERSION,
        'NSHighResolutionCapable': 'True',
        'LSMinimumSystemVersion': '13.0.0',
    },
)
