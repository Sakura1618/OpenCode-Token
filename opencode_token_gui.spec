# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


PROJECT_ROOT = Path(SPECPATH).resolve()


a = Analysis(
    [str(PROJECT_ROOT / "opencode_token_gui.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[(str(PROJECT_ROOT / "opencode_token_app" / "prices.json"), "opencode_token_app")],
    hiddenimports=["matplotlib.backends.backend_tkagg"],
    hookspath=[],
    hooksconfig={"matplotlib": {"backends": ["TkAgg"]}},
    runtime_hooks=[],
    excludes=[
        "PySide2",
        "PySide6",
        "PyQt5",
        "PyQt6",
        "shiboken2",
        "shiboken6",
        "matplotlib.backends.backend_qt",
        "matplotlib.backends.backend_qt5",
        "matplotlib.backends.backend_qt5agg",
        "matplotlib.backends.backend_qtcairo",
        "matplotlib.backends.backend_qtagg",
        "matplotlib.backends.qt_compat",
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="opencode_token_gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
