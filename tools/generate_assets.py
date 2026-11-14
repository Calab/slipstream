#!/usr/bin/env python3
"""Pre-generate all procedural assets (images, textures, sounds, music).

The game does this automatically on first launch; run this to inspect the
generated files in ./assets or to rebuild them after changing a generator.
Use --force to wipe and regenerate everything.
"""

import argparse
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from slipstream.assetgen import AssetBuilder, default_asset_dir  # noqa: E402
from slipstream.themes import THEMES  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="delete and rebuild everything")
    ap.add_argument("--out", help="output directory (default: ./assets)")
    args = ap.parse_args()
    root = Path(args.out) if args.out else default_asset_dir()
    if args.force and root.exists():
        shutil.rmtree(root)
    t0 = time.time()

    def progress(i, n, label):
        if n:
            print(f"\r[{i:3d}/{n}] {label:<32}", end="", flush=True)

    n = AssetBuilder(root).build(THEMES, progress)
    print(f"\nGenerated {n} assets in {time.time() - t0:.1f}s -> {root}")


if __name__ == "__main__":
    main()
