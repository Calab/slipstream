# PyInstaller spec for a single-file Slipstream executable (Linux or Windows).
# Normally run via:  python tools/build_binary.py
# (which generates the assets first).  Output: dist/slipstream[.exe]

import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821 (SPECPATH is set by PyInstaller)

# Panda3D loads its graphics/audio drivers as plugins at runtime, which
# PyInstaller can't discover, so collect the whole package...
datas, binaries, hiddenimports = collect_all("panda3d")
hiddenimports += collect_submodules("direct")

# ...minus the large parts this game never uses.
UNUSED = (
    "libp3assimp",        # 3D model importer
    "libp3ptloader",      # model loader plugin
    "libp3tinydisplay",   # software renderer
    "libpandabullet", "bullet.",   # Bullet physics
    "libpandaode", "ode.",         # ODE physics
)

datas += [
    (os.path.join(ROOT, "slipstream", "fonts"), os.path.join("slipstream", "fonts")),
    (os.path.join(ROOT, "custom"), "custom"),
    # pre-generated art, textures, sounds and music (so the first launch is instant)
    (os.path.join(ROOT, "assets"), "assets"),
]

a = Analysis(  # noqa: F821
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["panda3d.bullet", "panda3d.ode", "tkinter"],
)


def _keep(entry):
    return not any(os.path.basename(entry[0]).startswith(u) for u in UNUSED)


a.binaries = [b for b in a.binaries if _keep(b)]
a.datas = [d for d in a.datas if _keep(d)]

pyz = PYZ(a.pure)  # noqa: F821

# program icon (the clownfish); used for the Windows .exe
ICON = os.path.join(ROOT, "assets", "fx", "icon.ico")

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="slipstream",
    console=False,        # no terminal window on Windows
    upx=False,
    strip=False,
    runtime_tmpdir=None,
    icon=ICON if os.path.exists(ICON) else None,
)
