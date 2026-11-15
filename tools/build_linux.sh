#!/usr/bin/env bash
# Build a single-file Slipstream executable on Linux:  dist/slipstream
# Needs Python 3.9-3.14 to BUILD (players of the finished binary don't need Python).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -x .venv/bin/python ]; then
    echo "Creating a Python environment in .venv ..."
    python3 -m venv .venv
fi
echo "Installing build requirements ..."
.venv/bin/python -m pip install --upgrade pip >/dev/null
.venv/bin/python -m pip install -r requirements.txt pyinstaller
.venv/bin/python tools/build_binary.py
echo
echo "Done: dist/slipstream"
