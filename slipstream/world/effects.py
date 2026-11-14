"""Bubbles: ambient streams floating up, and bursts from the player."""

import math
import random

from panda3d.core import TransparencyAttrib

from .. import config
from .common import card


class Bubbles:
    MAX = 160

    def __init__(self, parent, res):
        self.parent = parent
        self.tex = res.texture("fx", "bubble.png")
        self.items = []          # [np, x, y, z, vz, wobble_phase, life]
        self.pool = []
        self.timer = 2.0

    def _get(self, size):
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
        for _ in range(count):
            if len(self.items) >= self.MAX:
                return
            s = random.uniform(*size)
            np_ = self._get(s)
            self.items.append([np_, x + random.uniform(-spread, spread), y + random.uniform(-spread, spread),
                               z + random.uniform(-spread, spread), random.uniform(1.2, 2.6),
                               random.uniform(0, 6.28), 0.0])

    def update(self, dt, t, cam_y, ambient=True):
        if ambient:
            self.timer -= dt
            if self.timer <= 0:
                # a random column of bubbles rising somewhere ahead
                self.timer = random.uniform(1.2, 3.5)
                x = random.uniform(-config.HALF_W + 2, config.HALF_W - 2)
                y = cam_y + random.uniform(15, 60)
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
            np_.setAlphaScale(min(1.0, life * 4) if z >= 0 else 0.0)
            keep.append(b)
        self.items = keep

    def destroy(self):
        for b in self.items:
            b[0].removeNode()
        for np_ in self.pool:
            np_.removeNode()
        self.items, self.pool = [], []
