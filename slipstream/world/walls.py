"""Walls spanning the whole corridor with 1-3 irregular openings.

A wall is a stack of alpha-textured slices (giving it thickness).  The same
boolean mask that cuts the holes in the texture is used for collision, so
what you see is exactly what you can swim through.

Making a wall, step by step (WallFactory.create):

1. Decide how many openings (1-3) and work out how far the fish can move
   sideways/vertically before reaching this wall (pace.reach).
2. make_openings() places lumpy round holes so that every opening of the
   *previous* wall has at least one hole here within reach - so the course
   can never become impossible.
3. opening_mask() turns the holes into a pixel grid: True = solid wall.
4. compose_texture() paints the material image with that mask as its
   transparency, plus shading around the holes.
5. Wall() stacks several copies of the texture to give the wall depth, and
   adds the glow that shines through the holes.

Wall pixel coordinates: column 0 is the left edge of the wall (x = -WALL_W/2),
row 0 is the *top* (the surface, z = WALL_H); PPU pixels per world unit.
"""

import math
import random

import numpy as np
from PIL import Image
from panda3d.core import CardMaker, ColorBlendAttrib, TransparencyAttrib

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
    """Random outline for one opening: (base radius, harmonics, stretch).

    The edge is a circle of radius base_r with a few sine "harmonics" added
    around it - k bumps per lap, amplitude a (fraction of base_r), phase ph -
    which makes it lumpy.  Holes shrink as difficulty rises.
    """
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


def make_openings(n, difficulty, rng, anchors=None, reach_x=1e9, reach_z=1e9, x_range=None):
    """Like _try_openings, retried until every approach is covered.

    Up to 30 attempts; if none covers every approach, the attempt that left
    the fewest uncovered is used.

    x_range is the (min, max) x for opening centres: the open part of the
    trench at this wall, which narrows when the side cliffs drift inwards.
    """
    lo, hi = x_range or (-config.HALF_W + 3.0, config.HALF_W - 3.0)
    # the player can't be inside the rock, so approaches are clamped to the open trench
    anchors = [(max(lo, min(hi, x)), max(CZ_MIN, min(CZ_MAX, z))) for x, z in (anchors or [])]
    best = None
    for _ in range(30):
        openings, pending = _try_openings(n, difficulty, rng, anchors, reach_x, reach_z, lo, hi)
        if not pending:
            return openings
        if best is None or len(pending) < best[1]:
            best = (openings, len(pending))
    return best[0]


def _try_openings(n, difficulty, rng, anchors, reach_x, reach_z, lo, hi):
    """Return a list of irregular openings: (cx, cz, base_r, harmonics, stretch).

    anchors are the (x, z) spots the player may be coming from (the previous
    wall's openings).  Each anchor gets at least one opening within reach,
    adding openings (up to 3) if needed, so no wall is impossible.
    """
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
            cx = rng.uniform(max(lo, ax - reach_x), min(hi, ax + reach_x))
            cz = rng.uniform(max(CZ_MIN, az - reach_z), min(CZ_MAX, az + reach_z))
        else:
            cx = rng.uniform(lo, hi)
            cz = rng.uniform(CZ_MIN, CZ_MAX)
        # keep holes well apart sideways, so they don't merge into one
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
        # the opening's centre in pixels
        px = (cx + WALL_W / 2) * ppu
        pz = (WALL_H - cz) * ppu
        # only look at a square around the hole big enough to hold it (faster)
        R = base_r * 1.45 * max(stretch, 1 / stretch) * ppu
        x0, x1 = int(max(px - R, 0)), int(min(px + R + 1, w))
        y0, y1 = int(max(pz - R, 0)), int(min(pz + R + 1, h))
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        # each pixel's offset from the centre in world units, squashed by
        # `stretch` so the hole comes out wider (stretch > 1) or taller (< 1)
        dx = (xx - px) / (ppu * stretch)
        dz = (yy - pz) / (ppu / stretch)
        # polar coordinates: angle around the centre and distance from it
        theta = np.arctan2(dz, dx)
        r = np.hypot(dx, dz)
        # the lumpy edge radius at each angle; pixels inside it are open water
        edge = np.full_like(theta, base_r)
        for k, a, ph in harm:
            edge += base_r * a * np.sin(k * theta + ph)
        solid[y0:y1, x0:x1] &= r > edge
    return solid


def compose_texture(material, solid, rng):
    """Combine a base material with the hole mask: shading + rim + alpha."""
    h, w = solid.shape
    # every wall uses one of only a few material images, so shift it sideways
    # by a random amount and maybe mirror it, so neighbouring walls differ
    mat = np.roll(material, rng.integers(0, w), axis=1)
    if rng.random() < 0.5:
        mat = mat[:, ::-1]
    s = solid.astype(np.float32)
    # blurring the 0/1 mask gives values between 0 and 1 near hole edges;
    # that's used to shade the edges (blur) and find a thin rim (lip)
    blur = box_blur(s, 7)
    # darken towards the holes (gives a sense of depth), brighten the very lip
    shade = 0.45 + 0.55 * np.clip((blur - 0.5) * 2.0, 0, 1)
    lip = box_blur(s, 1)
    rim = (lip < 0.97) & solid
    # sunlight from above
    vert = np.linspace(1.08, 0.62, h)[:, None]
    rgb = mat * (shade * vert)[..., None]
    rgb[rim] = np.minimum(rgb[rim] * 1.6 + 0.08, 1.0)
    # transparency: opaque where solid, with a soft 1-2 pixel edge (anti-aliasing)
    alpha = np.clip((lip - 0.3) * 2.5, 0, 1)
    rgba = np.dstack([np.clip(rgb, 0, 1), alpha])
    return (rgba * 255).astype(np.uint8)


class Wall:
    """One wall across the whole trench.  Its ends are hidden inside the
    side cliffs.  Costs WALL_DAMAGE health if the fish hits a solid part."""
    kind = "wall"

    def __init__(self, parent, bank, material, y, thickness, openings, rng, light=None):
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
        # one slice every ~0.3 units through the thickness (at least 3); seen at
        # an angle, the stack of slices looks like a solid slab with deep holes
        n = max(3, int(thickness / 0.3))
        for i in range(n):
            t = i / (n - 1)
            c = card(self.root, self.tex, WALL_W, WALL_H, anchor="bottom",
                     transparency=TransparencyAttrib.M_dual)
            c.setPos(0, -thickness / 2 + thickness * t, 0)
            k = 1.0 - 0.45 * math.sin(math.pi * t) - 0.15 * t   # inner slices darker
            c.setColorScale(k, k, k, 1)
        self.rim = self.rim_tex = None
        # light = (soft glow texture, theme's surface colour)
        if light is not None:
            self._add_hole_lights(*light)
            self._add_rim_glow(light[1])
        self.alpha = 1.0

    def _add_rim_glow(self, color):
        """A soft, gently pulsing glow tracing the edge of every opening, on the
        front face of the wall.  It ignores the fog so holes stand out early."""
        solid = self.solid.astype(np.float32)
        # light spilling out of the holes: a wide, soft falloff (~1 unit)
        spread = box_blur(box_blur(1.0 - solid, 8), 6)
        a = np.clip(spread * solid * 1.6, 0.0, 1.0)
        h, w = a.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[..., 0] = int(255 * min(1.0, 0.55 + 0.45 * color[0]))
        rgba[..., 1] = int(255 * min(1.0, 0.55 + 0.45 * color[1]))
        rgba[..., 2] = int(255 * min(1.0, 0.55 + 0.45 * color[2]))
        rgba[..., 3] = (a * 255).astype(np.uint8)
        # textures made at runtime from numpy arrays (not files)
        self.rim_tex = Resources.texture_from_array(rgba, "rim")
        self.rim = card(self.root, self.rim_tex, WALL_W, WALL_H, anchor="bottom")
        self.rim.setY(-self.thickness / 2 - 0.03)
        self.rim.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_incoming_alpha,
                                                 ColorBlendAttrib.O_one))
        self.rim.setDepthWrite(False)
        self.rim.setFogOff()

    def _add_hole_lights(self, tex, color):
        """Bright water glowing through each opening, so holes read as lit
        windows in the wall even far away (the glow ignores the fog).  The
        glow sits just behind the wall, so the wall itself hides all but the
        part showing through the hole."""
        add = ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_incoming_alpha,
                                    ColorBlendAttrib.O_one)
        for cx, cz, base_r, _harm, stretch in self.openings:
            w = base_r * stretch * 1.45 * 2.4
            h = base_r / stretch * 1.45 * 2.4
            # trim the glow to the wall's height so it never spills over the top
            z0, z1 = max(0.0, cz - h / 2), min(WALL_H, cz + h / 2)
            cm = CardMaker("hole-light")
            cm.setFrame(cx - w / 2, cx + w / 2, z0, z1)
            cm.setUvRange((0, (z0 - (cz - h / 2)) / h), (1, (z1 - (cz - h / 2)) / h))
            g = self.root.attachNewNode(cm.generate())
            g.setTexture(tex)
            g.setTwoSided(True)
            g.setLightOff()
            g.setY(self.thickness / 2 + 0.4)
            g.setAttrib(add)
            g.setDepthWrite(False)
            g.setFogOff()
            g.setColor(color[0], color[1], color[2], 0.55)

    # -- geometry ------------------------------------------------------------
    @property
    def front(self):
        """y of the face the fish approaches."""
        return self.y - self.thickness / 2

    @property
    def back(self):
        """y of the far face."""
        return self.y + self.thickness / 2

    def solid_at(self, x, z):
        """Is the wall solid at world position (x, z)?  Outside the mask counts
        as solid."""
        col = int((x + WALL_W / 2) * config.PPU)
        row = int((WALL_H - z) * config.PPU)
        h, w = self.solid.shape
        if col < 0 or col >= w or row < 0 or row >= h:
            return True
        return bool(self.solid[row, col])

    def collides(self, x, y, z, r):
        """Does a fish of radius r at (x, y, z) touch solid wall?

        Checks the centre point and 8 points around the edge of the fish's
        circle against the hole mask.
        """
        if y + r * 0.5 < self.front or y - r * 0.5 > self.back:   # not inside the wall's thickness
            return False
        if self.solid_at(x, z):
            return True
        for k in range(8):
            a = k * math.pi / 4
            if self.solid_at(x + math.cos(a) * r, z + math.sin(a) * r):
                return True
        return False

    def update(self, dt, t, player_y):
        """Pulse the rim glow; fade the wall out as the fish goes through."""
        if self.rim is not None:
            self.rim.setAlphaScale(0.3 + 0.1 * math.sin(t * 3.0 + self.y * 0.1))
        # fade out as the player passes through so the next obstacles show
        a = (self.back + 0.5 - player_y) / (self.thickness + 2.5)
        a = max(0.0, min(1.0, a))
        if abs(a - self.alpha) > 0.01:          # skip tiny changes (saves work)
            self.alpha = a
            self.root.setAlphaScale(a)
            if a <= 0.0:
                self.root.hide()

    def remove(self):
        """Remove the wall and let go of its textures (frees their memory)."""
        self.root.removeNode()
        self.tex = self.rim_tex = None


class WallFactory:
    """Makes the walls for one run: random but repeatable from the seed."""

    def __init__(self, res, theme, seed=None):
        self.theme = theme
        self.bank = MaterialBank(res, theme.wall_materials)
        self.light = (res.texture("fx", "soft.png"), theme.surface)
        # two random generators from the same seed: numpy's for the texture
        # work, Python's for the layout choices
        self.rng = np.random.default_rng(seed)
        self.pyrng = random.Random(seed)

    def create(self, parent, y, difficulty, anchors=None, prev_y=0.0, x_range=None):
        """anchors: (x, z) openings of the previous wall (or the start spot);
        x_range: where opening centres may go (the open trench at this wall)."""
        # how many openings: usually 1 or 2; fewer 3s later in the run
        n = self.pyrng.choices([1, 2, 3], weights=[0.35, 0.4, 0.25])[0]
        if difficulty > 0.6 and n == 3 and self.pyrng.random() < 0.5:
            n = 2
        rx, rz = reach(prev_y, y)
        openings = make_openings(n, difficulty, self.pyrng, anchors, rx, rz, x_range)
        material = self.pyrng.choice(self.theme.wall_materials)
        thickness = self.pyrng.uniform(0.6, 3.2)
        return Wall(parent, self.bank, material, y, thickness, openings, self.rng, self.light)
