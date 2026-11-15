#!/usr/bin/env python3
"""Build a single-file Slipstream executable for the current platform.

    pip install pyinstaller
    python tools/build_binary.py

Produces dist/slipstream (Linux), dist\\slipstream.exe (Windows) or
dist/Slipstream.app (macOS).  Players just run that; no Python install is
needed.  Build on each platform you want to ship for (PyInstaller does not
cross-compile), on Linux on the oldest distribution you want to support, and
on macOS once per processor type (Apple silicon / Intel).
"""

import shutil

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
    if sys.platform == "darwin":
        finish_macos(ROOT / "dist" / "Slipstream.app")
        return
    exe = ROOT / "dist" / ("slipstream.exe" if sys.platform.startswith("win") else "slipstream")
    if exe.exists():
        print(f"\nBuilt {exe}  ({exe.stat().st_size / 1e6:.0f} MB)")


def finish_macos(app):
    """Sign the bundle (ad hoc) and zip it for sharing."""
    if not app.exists():
        sys.exit(f"{app} was not built - see the messages above.")
    # An ad-hoc signature (no Apple developer account) is required for the app
    # to run on Apple silicon at all.  It does not satisfy Gatekeeper on other
    # Macs; see README "Building a standalone executable".
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=False)
    # ditto keeps the bundle's symlinks and signature intact (a plain zip breaks them)
    arch = subprocess.run(["uname", "-m"], capture_output=True, text=True).stdout.strip() or "mac"
    zip_path = app.parent / f"Slipstream-macos-{arch}.zip"
    zip_path.unlink(missing_ok=True)
    subprocess.run(["ditto", "-c", "-k", "--keepParent", str(app), str(zip_path)], check=True)
    size = sum(f.stat().st_size for f in app.rglob("*") if f.is_file() and not f.is_symlink())
    print(f"\nBuilt {app}  ({size / 1e6:.0f} MB)")
    print(f"Zipped for sharing: {zip_path}  ({zip_path.stat().st_size / 1e6:.0f} MB)")
    if shutil.which("open"):
        print(f"Try it:  open {app}")


if __name__ == "__main__":
    main()
