# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_root = Path(SPEC).resolve().parents[1]
backend_hiddenimports = collect_submodules("backend.app")
launcher_hiddenimports = [
    "launcher.app",
    "launcher.paths",
    "launcher.instance",
    "launcher.server",
    "launcher.logging_config",
]

datas = [
    (str(project_root / "frontend" / "dist"), "frontend/dist"),
    (str(project_root / "config" / "settings.example.toml"), "config"),
]
icon_path = project_root / "packaging" / "hp-simulator.ico"

a = Analysis(
    [str(project_root / "launcher" / "app.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=backend_hiddenimports + launcher_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "playwright", "tkinter.test"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    name="霍格沃兹人生模拟器",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=True,
    exclude_binaries=True,
    version=str(project_root / "packaging" / "version_info.txt"),
    icon=str(icon_path),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="霍格沃兹人生模拟器",
)
