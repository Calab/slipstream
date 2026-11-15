#!/usr/bin/env bash
# Build Slipstream for macOS:  dist/Slipstream.app  (+ a .zip for sharing)
# Run from Terminal:  ./tools/build_macos.sh
# Needs Python 3.9-3.14 to BUILD (players of the finished app don't need Python).
# The app runs on the same processor type it was built on (Apple silicon or Intel).
#
# Uses the virtual environment .mac_venv (so it can share the project folder
# with a Linux .venv).  To use a different one:  VENV=myvenv ./tools/build_macos.sh
set -euo pipefail
cd "$(dirname "$0")/.."
VENV="${VENV:-.mac_venv}"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 was not found. Install Python 3.13 from https://www.python.org/downloads/macos/"
    echo "(or with Homebrew: brew install python@3.13), then run this again."
    exit 1
fi

if [ ! -x "$VENV/bin/python" ]; then
    echo "Creating a Python environment in $VENV ..."
    python3 -m venv "$VENV"
fi
echo "Installing build requirements into $VENV ..."
"$VENV/bin/python" -m pip install --upgrade pip >/dev/null
"$VENV/bin/python" -m pip install -r requirements.txt pyinstaller
"$VENV/bin/python" tools/build_binary.py
echo
echo "Done: dist/Slipstream.app"
