# PyInstaller spec for Slipstream.
# Normally run via:  python tools/build_binary.py
# (which generates the assets first).
# Output: Linux dist/slipstream, Windows dist/slipstream.exe (single files),
#         macOS dist/Slipstream.app (an app bundle; single-file programs
#         inside .app bundles are not supported by PyInstaller).

import os
import re
import sys

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

if sys.platform == "darwin":
    # Onedir build wrapped in an app bundle.  PyInstaller turns the PNG icon
    # into the .icns macOS needs (it uses Pillow, which the game needs anyway).
    ICON = os.path.join(ROOT, "assets", "fx", "icon.png")
    with open(os.path.join(ROOT, "slipstream", "__init__.py")) as f:
        VERSION = re.search(r'__version__\s*=\s*"([^"]+)"', f.read()).group(1)
    exe = EXE(  # noqa: F821
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="slipstream",
        console=False,
        upx=False,
        strip=False,
        argv_emulation=False,
    )
    coll = COLLECT(exe, a.binaries, a.datas, name="slipstream", upx=False, strip=False)  # noqa: F821
    app = BUNDLE(  # noqa: F821
        coll,
        name="Slipstream.app",
        icon=ICON if os.path.exists(ICON) else None,
        bundle_identifier="io.github.slipstream-game",
        version=VERSION,
        info_plist={
            "CFBundleDisplayName": "Slipstream",
            "CFBundleShortVersionString": VERSION,
            "LSApplicationCategoryType": "public.app-category.arcade-games",
            "LSMinimumSystemVersion": "11.0",
        },
    )
else:
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
