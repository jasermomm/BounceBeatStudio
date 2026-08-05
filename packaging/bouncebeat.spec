
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

root = Path(SPEC).resolve().parents[1]
source = root / "src"
assets = source / "bouncebeat" / "assets"
icon = assets / "icons" / "app.ico"

datas = [(str(assets), "assets")]
vendor = root / "vendor"
binaries = []
for executable in ("ffmpeg.exe", "ffprobe.exe"):
    candidate = vendor / executable
    if candidate.is_file():
        binaries.append((str(candidate), "."))
hiddenimports = collect_submodules("pymunk") + collect_submodules("mido")

a = Analysis(
    [str(root / "run.py")],
    pathex=[str(source)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "notebook"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BounceBeat Studio",
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
    icon=str(icon) if icon.is_file() else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="BounceBeat Studio",
)
