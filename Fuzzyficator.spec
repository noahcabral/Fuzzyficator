# -*- mode: python ; coding: utf-8 -*-


datas = [
    ("Fuzzyficator.py", "."),
    ("Fuzzyficator_paintOn.py", "."),
    ("Fuzzyficator_pattern.py", "."),
    ("README.md", "."),
    ("LICENSE", "."),
]

hiddenimports = [
    "numpy",
    "PIL",
    "PIL.Image",
]

a = Analysis(
    ["Fuzzyficator_gui.py", "Fuzzyficator_worker.py"],
    pathex=[],
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
runtime_scripts = [script for script in a.scripts if script[0].startswith("pyi_rth_")]
gui_scripts = runtime_scripts + [script for script in a.scripts if script[0] == "Fuzzyficator_gui"]
worker_scripts = runtime_scripts + [script for script in a.scripts if script[0] == "Fuzzyficator_worker"]

gui = EXE(
    pyz,
    gui_scripts,
    [],
    exclude_binaries=True,
    name="Fuzzyficator",
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

worker = EXE(
    pyz,
    worker_scripts,
    [],
    exclude_binaries=True,
    name="FuzzyficatorWorker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    gui,
    worker,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Fuzzyficator",
)
