"""Walls spanning the whole corridor with 1-3 irregular openings.

A wall is a stack of alpha-textured slices (giving it thickness).  The same
boolean mask that cuts the holes in the texture is used for collision, so
what you see is exactly what you can swim through.
"""

import math
import random

import numpy as np
from PIL import Image
from panda3d.core import TransparencyAttrib

from .. import config
from ..assetgen import WALL_PX_W, WALL_PX_H
from ..assetgen.common import box_blur
from ..resources import Resources
from .common import card
from .pace import reach

WALL_W = WALL_PX_W / config.PPU          # world units (wider than the corridor)
WALL_H = config.WORLD_H


class MaterialBank:
    """Caches the base material images (float RGB arrays) for a theme."""

    def __init__(self, res, names):
        self.mats = {}
        for n in set(names):
            img = Image.open(res.path("textures", f"wall_{n}.png")).convert("RGB")
            if img.size != (WALL_PX_W, WALL_PX_H):   # custom art of another size
                img = img.resize((WALL_PX_W, WALL_PX_H), Image.LANCZOS)
            self.mats[n] = np.asarray(img, dtype=np.float32) / 255.0

    def get(self, name):
        return self.mats[name]


# Opening centres may sit anywhere the fish can swim: from just above the sea
# floor (the hole then opens onto the sand like an arch) to just under the
# surface.  The fish's own limits are r+0.15 .. H-r-0.6.
CZ_MIN = config.FISH_RADIUS + 0.35
CZ_MAX = WALL_H - config.FISH_RADIUS - 0.75


def _shape(difficulty, rng):
    base_r = (2.9 - 1.35 * difficulty) * rng.uniform(0.85, 1.2)
    # harmonics make the outline lumpy; total amplitude kept <= 0.3 so
    # the narrowest part still fits the fish comfortably
    harm = []
    budget = 0.3
    for k in (2, 3, 5, 7):
        a = rng.uniform(0, min(budget, 0.14))
        budget -= a
        harm.append((k, a, rng.uniform(0, 2 * math.pi)))
    stretch = rng.uniform(0.8, 1.35)   # wider or taller holes
    return base_r, harm, stretch


def _covers(anchor, opening, reach_x, reach_z):
    """Can a player at `anchor` (x, z) get inside `opening` in time?"""
    cx, cz, base_r, _harm, stretch = opening
    slack_x = base_r * stretch * 0.35     # needn't reach the exact centre
    slack_z = base_r / stretch * 0.35
    return (abs(anchor[0] - cx) <= reach_x + slack_x and
            abs(anchor[1] - cz) <= reach_z + slack_z)


def make_openings(n, difficulty, rng, anchors=None, reach_x=1e9, reach_z=1e9):
    """Like _try_openings, retried until every approach is covered."""
    anchors = [(max(-config.HALF_W, min(config.HALF_W, x)), max(CZ_MIN, min(CZ_MAX, z)))
               for x, z in (anchors or [])]
    best = None
    for _ in range(30):
        openings, pending = _try_openings(n, difficulty, rng, anchors, reach_x, reach_z)
        if not pending:
            return openings
        if best is None or len(pending) < best[1]:
            best = (openings, len(pending))
    return best[0]


def _try_openings(n, difficulty, rng, anchors, reach_x, reach_z):
    """Return a list of irregular openings: (cx, cz, base_r, harmonics, stretch).

    anchors are the (x, z) spots the player may be coming from (the previous
    wall's openings).  Each anchor gets at least one opening within reach,
    adding openings (up to 3) if needed, so no wall is impossible.
    """
    lim = config.HALF_W - 3.0
    openings = []
    pending = list(anchors or [])
    rng.shuffle(pending)
    tries = 0
    while (len(openings) < n or pending) and len(openings) < 3 and tries < 400:
        tries += 1
        base_r, harm, stretch = _shape(difficulty, rng)
        if pending:
            # anywhere inside the reachable window around that approach
            ax, az = pending[0]
            cx = rng.uniform(max(-lim, ax - reach_x), min(lim, ax + reach_x))
            cz = rng.uniform(max(CZ_MIN, az - reach_z), min(CZ_MAX, az + reach_z))
        else:
            cx = rng.uniform(-lim, lim)
            cz = rng.uniform(CZ_MIN, CZ_MAX)
        if any(abs(cx - o[0]) < (base_r + o[2]) * 1.5 + 2.5 for o in openings):
            continue
        op = (cx, cz, base_r, harm, stretch)
        openings.append(op)
        pending = [a for a in pending if not _covers(a, op, reach_x, reach_z)]
    return openings, pending


def opening_mask(openings, w=WALL_PX_W, h=WALL_PX_H):
    """Boolean array, True where the wall is solid (row 0 = top)."""
    solid = np.ones((h, w), dtype=bool)
    ppu = config.PPU
    for cx, cz, base_r, harm, stretch in openings:
        px = (cx + WALL_W / 2) * ppu
        pz = (WALL_H - cz) * ppu
        R = base_r * 1.45 * max(stretch, 1 / stretch) * ppu
        x0, x1 = int(max(px - R, 0)), int(min(px + R + 1, w))
        y0, y1 = int(max(pz - R, 0)), int(min(pz + R + 1, h))
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        dx = (xx - px) / (ppu * stretch)
        dz = (yy - pz) / (ppu / stretch)
        theta = np.arctan2(dz, dx)
        r = np.hypot(dx, dz)
        edge = np.full_like(theta, base_r)
        for k, a, ph in harm:
            edge += base_r * a * np.sin(k * theta + ph)
        solid[y0:y1, x0:x1] &= r > edge
    return solid


def compose_texture(material, solid, rng):
    """Combine a base material with the hole mask: shading + rim + alpha."""
    h, w = solid.shape
    mat = np.roll(material, rng.integers(0, w), axis=1)
    if rng.random() < 0.5:
        mat = mat[:, ::-1]
    s = solid.astype(np.float32)
    blur = box_blur(s, 7)
    # darken towards the holes (gives a sense of depth), brighten the very lip
    shade = 0.45 + 0.55 * np.clip((blur - 0.5) * 2.0, 0, 1)
    lip = box_blur(s, 1)
    rim = (lip < 0.97) & solid
    # sunlight from above
    vert = np.linspace(1.08, 0.62, h)[:, None]
    rgb = mat * (shade * vert)[..., None]
    rgb[rim] = np.minimum(rgb[rim] * 1.6 + 0.08, 1.0)
    alpha = np.clip((lip - 0.3) * 2.5, 0, 1)
    rgba = np.dstack([np.clip(rgb, 0, 1), alpha])
    return (rgba * 255).astype(np.uint8)


class Wall:
    kind = "wall"

    def __init__(self, parent, bank, material, y, thickness, openings, rng):
        self.y = y
        self.thickness = thickness
        self.openings = openings
        self.solid = opening_mask(openings)
        self.hit = False
        self.passed = False
        rgba = compose_texture(bank.get(material), self.solid, rng)
        self.tex = Resources.texture_from_array(rgba, "wall")
        self.root = parent.attachNewNode("wall")
        self.root.setPos(0, y, 0)
        n = max(3, int(thickness / 0.3))
        for i in range(n):
            t = i / (n - 1)
            c = card(self.root, self.tex, WALL_W, WALL_H, anchor="bottom",
                     transparency=TransparencyAttrib.M_dual)
            c.setPos(0, -thickness / 2 + thickness * t, 0)
            k = 1.0 - 0.45 * math.sin(math.pi * t) - 0.15 * t   # inner slices darker
            c.setColorScale(k, k, k, 1)
        self.alpha = 1.0

    # -- geometry ------------------------------------------------------------
    @property
    def front(self):
        return self.y - self.thickness / 2

    @property
    def back(self):
        return self.y + self.thickness / 2

    def solid_at(self, x, z):
        col = int((x + WALL_W / 2) * config.PPU)
        row = int((WALL_H - z) * config.PPU)
        h, w = self.solid.shape
        if col < 0 or col >= w or row < 0 or row >= h:
            return True
        return bool(self.solid[row, col])

    def collides(self, x, y, z, r):
        if y + r * 0.5 < self.front or y - r * 0.5 > self.back:
            return False
        if self.solid_at(x, z):
            return True
        for k in range(8):
            a = k * math.pi / 4
            if self.solid_at(x + math.cos(a) * r, z + math.sin(a) * r):
                return True
        return False

    def update(self, dt, t, player_y):
        # fade out as the player passes through so the next obstacles show
        a = (self.back + 0.5 - player_y) / (self.thickness + 2.5)
        a = max(0.0, min(1.0, a))
        if abs(a - self.alpha) > 0.01:
            self.alpha = a
            self.root.setAlphaScale(a)
            if a <= 0.0:
                self.root.hide()

    def remove(self):
        self.root.removeNode()
        self.tex = None


class WallFactory:
    def __init__(self, res, theme, seed=None):
        self.theme = theme
        self.bank = MaterialBank(res, theme.wall_materials)
        self.rng = np.random.default_rng(seed)
        self.pyrng = random.Random(seed)

    def create(self, parent, y, difficulty, anchors=None, prev_y=0.0):
        """anchors: (x, z) openings of the previous wall (or the start spot)."""
        n = self.pyrng.choices([1, 2, 3], weights=[0.35, 0.4, 0.25])[0]
        if difficulty > 0.6 and n == 3 and self.pyrng.random() < 0.5:
            n = 2
        rx, rz = reach(prev_y, y)
        openings = make_openings(n, difficulty, self.pyrng, anchors, rx, rz)
        material = self.pyrng.choice(self.theme.wall_materials)
        thickness = self.pyrng.uniform(0.6, 3.2)
        return Wall(parent, self.bank, material, y, thickness, openings, self.rng)
