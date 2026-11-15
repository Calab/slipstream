"""Bubbles: ambient streams floating up, and bursts from the player."""

import math
import random

from panda3d.core import TransparencyAttrib

from .. import config
from .common import card


class Bubbles:
    """All bubbles in the scene.

    Bubble cards are *pooled*: when a bubble pops it is hidden and kept in
    self.pool for reuse instead of being deleted, which avoids creating and
    destroying scene nodes all the time.
    """
    MAX = 160          # most bubbles alive at once

    def __init__(self, parent, res):
        self.parent = parent
        self.tex = res.texture("fx", "bubble.png")
        self.items = []          # [np, x, y, z, vz, wobble_phase, life]
        self.pool = []           # hidden bubble cards ready for reuse
        self.timer = 2.0         # seconds until the next ambient bubble column

    def _get(self, size):
        """A bubble card of the given size: a pooled one if available, else new."""
        if self.pool:
            np_ = self.pool.pop()
            np_.show()
        else:
            np_ = card(self.parent, self.tex, 1, 1, transparency=TransparencyAttrib.M_alpha)
            np_.setBillboardPointEye()
            np_.setDepthWrite(False)
            np_.setBin("fixed", 10)
        np_.setScale(size)
        return np_

    def spawn(self, x, y, z, count=6, spread=0.4, size=(0.08, 0.22)):
        """Release `count` bubbles scattered up to `spread` units around (x, y, z)."""
        for _ in range(count):
            if len(self.items) >= self.MAX:
                return
            s = random.uniform(*size)
            np_ = self._get(s)
            self.items.append([np_, x + random.uniform(-spread, spread), y + random.uniform(-spread, spread),
                               z + random.uniform(-spread, spread), random.uniform(1.2, 2.6),
                               random.uniform(0, 6.28), 0.0])

    def update(self, dt, t, cam_y, ambient=True):
        """Rise and wobble every bubble; pop those that reach the surface, fall
        behind the camera (cam_y) or are too old."""
        if ambient:
            self.timer -= dt
            if self.timer <= 0:
                # a random column of bubbles rising somewhere ahead
                self.timer = random.uniform(1.2, 3.5)
                x = random.uniform(-config.HALF_W + 2, config.HALF_W - 2)
                y = cam_y + random.uniform(15, 60)
                # spaced out *below* the floor (z < 0, kept invisible until they
                # rise past it) so they emerge one after another as a stream
                for i in range(random.randint(6, 14)):
                    self.spawn(x, y, 0.2 - i * 0.6, count=1, spread=0.25, size=(0.1, 0.3))
        keep = []
        for b in self.items:
            np_, x, y, z, vz, ph, life = b
            life += dt
            z += vz * dt
            b[3], b[6] = z, life
            if z > config.WORLD_H - 0.2 or y < cam_y + 2.5 or life > 14:
                np_.hide()
                self.pool.append(np_)
                continue
            np_.setPos(x + math.sin(t * 3 + ph) * 0.12, y, max(z, 0.05))
            np_.setAlphaScale(min(1.0, life * 4) if z >= 0 else 0.0)   # fade in over 1/4 s
            keep.append(b)
        self.items = keep

    def destroy(self):
        for b in self.items:
            b[0].removeNode()
        for np_ in self.pool:
            np_.removeNode()
        self.items, self.pool = [], []
