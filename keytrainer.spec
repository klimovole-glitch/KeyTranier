# -*- mode: python ; coding: utf-8 -*-
# PyInstaller build file: `pyinstaller keytrainer.spec`
# Result: dist/KeyTrainer.exe (one file, no console window).
# The database, the log and settings.json are created next to the .exe.

a = Analysis(
    ["keytrainer/__main__.py"],
    pathex=["."],
    datas=[
        ("keytrainer/resources", "keytrainer/resources"),
        ("keytrainer/data/schema.sql", "keytrainer/data"),
    ],
    hiddenimports=["matplotlib.backends.backend_tkagg"],
    excludes=["pytest"],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="KeyTrainer",
    console=False,
    upx=False,
)
