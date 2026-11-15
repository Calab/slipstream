#!/usr/bin/env python3
"""Build a single-file Slipstream executable for the current platform.

    pip install pyinstaller
    python tools/build_binary.py

Produces dist/slipstream (Linux) or dist\\slipstream.exe (Windows).  Players
just run that one file; no Python install is needed.  Build on each platform
you want to ship for (PyInstaller does not cross-compile), and on Linux build
on the oldest distribution you want to support.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    try:
        import PyInstaller.__main__
    except ImportError:
        sys.exit("PyInstaller is not installed:  pip install pyinstaller")

    # 1. make sure every asset exists and is current, so it can be bundled
    subprocess.run([sys.executable, str(ROOT / "tools" / "generate_assets.py"),
                    "--out", str(ROOT / "assets")], check=True)

    # 2. build the single-file executable
    PyInstaller.__main__.run([
        str(ROOT / "tools" / "slipstream.spec"),
        "--noconfirm",
        "--distpath", str(ROOT / "dist"),
        # separate working folder per system, so Linux and Windows builds
        # sharing one project folder don't mix their cached files
        "--workpath", str(ROOT / "build" / sys.platform),
    ])
    exe = ROOT / "dist" / ("slipstream.exe" if sys.platform.startswith("win") else "slipstream")
    if exe.exists():
        print(f"\nBuilt {exe}  ({exe.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
