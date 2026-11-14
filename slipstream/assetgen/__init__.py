"""Procedural asset generation.

All images, textures, sound effects and music are generated on first run
(or by ``python tools/generate_assets.py``) and cached on disk.  Bump
``config.ASSET_VERSION`` to force regeneration after changing a generator.
"""

import json
import shutil
from pathlib import Path

from .. import config
from ..themes import THEMES, OBSTACLE_INFO, REWARD_INFO
from . import sprites, textures, audio

WALL_PX_W = int(2 * (config.HALF_W + config.WALL_EXTRA) * config.PPU)
WALL_PX_H = int(config.WORLD_H * config.PPU)


def default_asset_dir():
    """Project ``assets/`` folder if writable, otherwise a per-user data dir."""
    project = Path(__file__).resolve().parents[2] / "assets"
    try:
        project.mkdir(parents=True, exist_ok=True)
        probe = project / ".write_test"
        probe.write_text("ok")
        probe.unlink()
        return project
    except OSError:
        from ..save import user_data_dir
        p = user_data_dir() / "assets"
        p.mkdir(parents=True, exist_ok=True)
        return p


class AssetBuilder:
    def __init__(self, root=None):
        self.root = Path(root) if root else default_asset_dir()
        stamp = self.root / "version.json"
        version = None
        if stamp.exists():
            try:
                version = json.loads(stamp.read_text()).get("version")
            except (OSError, ValueError):
                version = None
        if version != config.ASSET_VERSION:
            for sub in ("player", "obstacles", "rewards", "boats", "fx", "textures", "band",
                        "bg", "sfx", "music", "decor"):
                shutil.rmtree(self.root / sub, ignore_errors=True)
            self.root.mkdir(parents=True, exist_ok=True)
            stamp.write_text(json.dumps({"version": config.ASSET_VERSION}))

    def path(self, *parts):
        return self.root.joinpath(*parts)

    # -- tasks -----------------------------------------------------------
    def _tasks_common(self):
        t = []
        P = self.path
        for name in ("fish_clown", "fish_tang", "sub", "mermaid"):
            t.append((P("player", f"{name}_0.png"), lambda n=name: self._save_frames("player", n,
                                                                              sprites.player_frames(n))))
        for kind in OBSTACLE_INFO:
            t.append((P("obstacles", f"{kind}_0.png"),
                      lambda k=kind: self._save_frames("obstacles", k, sprites.OBSTACLE_DRAW[k]())))
        for kind in REWARD_INFO:
            t.append((P("rewards", f"{kind}.png"), lambda k=kind: sprites.REWARD_DRAW[k]()))
        for name, fn in sprites.DECOR_DRAW.items():
            t.append((P("decor", f"{name}.png"), fn))
        for boat in sprites.BOAT_DRAW:
            t.append((P("boats", f"{boat}.png"), lambda b=boat: sprites.BOAT_DRAW[b]()))
        t += [
            (P("fx", "bubble.png"), sprites.bubble),
            (P("fx", "shadow.png"), sprites.shadow),
            (P("fx", "arrow.png"), sprites.arrow),
            (P("fx", "aim.png"), sprites.aim_ring),
            (P("fx", "dot.png"), sprites.dot),
            (P("fx", "halo.png"), sprites.halo),
            (P("fx", "glow.png"), sprites.glow),
            (P("fx", "soft.png"), sprites.soft),
            (P("fx", "marker_last.png"), lambda: sprites.marker((255, 200, 60))),
            (P("fx", "marker_best.png"), lambda: sprites.marker((90, 255, 140))),
            (P("fx", "light_ray.png"), textures.light_ray),
            (P("fx", "caustics.png"), textures.caustic_overlay),
            (P("textures", "surface.png"), textures.surface_caustics),
            (P("bg", "far.png"), lambda: sprites.bg_layer(1, kind="far")),
            (P("bg", "mid.png"), lambda: sprites.bg_layer(2, kind="mid")),
            (P("bg", "near.png"), lambda: sprites.bg_layer(3, kind="near")),
        ]
        for name, fn in textures.FLOORS.items():
            t.append((P("textures", f"floor_{name}.png"), fn))
        for i, name in enumerate(("reefrock", "darkrock", "kelprock")):
            t.append((P("textures", f"cliff_{name}.png"), lambda n=name, s=i: textures.cliff_rock(n, seed=10 + s)))
        for i, name in enumerate(textures.WALL_MATERIALS):
            t.append((P("textures", f"wall_{name}.png"),
                      lambda n=name, s=i: textures.wall_material_image(n, WALL_PX_W, WALL_PX_H, 100 + s)))
        for name, fn in audio.SFX.items():
            t.append((P("sfx", f"{name}.wav"), fn))
        return t

    def _tasks_theme(self, theme):
        t = []
        P = self.path
        t.append((P("band", f"{theme.key}_sky.png"),
                  lambda: sprites.sky_gradient(theme.sky_top, theme.sky_bottom)))
        for i, col in enumerate(theme.wave_colors):
            t.append((P("band", f"{theme.key}_wave{i}.png"),
                      lambda c=col, s=i: sprites.wave_layer(c, seed=s + 3, amp=7 + 3 * s)))
        for stage in range(audio.MUSIC_STAGES):
            t.append((P("music", f"{theme.key}_{stage}.wav"),
                      lambda st=stage: audio.render_music(theme.music, st)))
        return t

    def _save_frames(self, folder, name, frames):
        self.path(folder).mkdir(parents=True, exist_ok=True)
        for i, im in enumerate(frames):
            im.save(self.path(folder, f"{name}_{i}.png"))
        return None

    def pending(self, themes=None):
        themes = THEMES if themes is None else themes
        tasks = self._tasks_common()
        for th in themes:
            tasks += self._tasks_theme(th)
        return [(p, fn) for p, fn in tasks if not p.exists()]

    def build(self, themes=None, progress=None):
        """Generate any missing assets.  progress(done, total, label) is optional."""
        todo = self.pending(themes)
        for i, (p, fn) in enumerate(todo):
            if progress:
                progress(i, len(todo), p.name)
            p.parent.mkdir(parents=True, exist_ok=True)
            result = fn()
            if result is None:
                continue
            if p.suffix == ".wav":
                audio.write_wav(p, result)
            else:
                result.save(p)
        if progress:
            progress(len(todo), len(todo), "done")
        return len(todo)

    def frame_count(self, folder, name):
        n = 0
        while self.path(folder, f"{name}_{n}.png").exists():
            n += 1
        return n


def build_all(root=None, progress=None):
    return AssetBuilder(root).build(THEMES, progress)

