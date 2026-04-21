# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files


PROJECT_ROOT = Path.cwd()
DEPS_PATH = PROJECT_ROOT / ".deps"
ICON_PATH = PROJECT_ROOT / ".build-assets" / "AppIcon.icns"

datas = [
    (str(PROJECT_ROOT / "webui" / "dist"), "webui/dist"),
]

hiddenimports = [
    "webview.platforms.qt",
    "qtpy",
    "qtpy.QtCore",
    "qtpy.QtGui",
    "qtpy.QtWidgets",
    "qtpy.QtNetwork",
    "qtpy.QtWebChannel",
    "qtpy.QtWebEngineCore",
    "qtpy.QtWebEngineWidgets",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtNetwork",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtPrintSupport",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
]

for package_name in ("PySide6", "shiboken6"):
    datas += collect_data_files(package_name)


a = Analysis(
    ["app.py"],
    pathex=[str(PROJECT_ROOT), str(DEPS_PATH)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    name="Rapunzel",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    exclude_binaries=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON_PATH),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Rapunzel",
)

app = BUNDLE(
    coll,
    name="Rapunzel.app",
    icon=str(ICON_PATH),
    bundle_identifier="local.rapunzel.desktop",
    info_plist={
        "CFBundleName": "Rapunzel",
        "CFBundleDisplayName": "Rapunzel",
        "CFBundleShortVersionString": "0.1",
        "CFBundleVersion": "1",
        "NSHighResolutionCapable": True,
    },
)
