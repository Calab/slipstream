"""Obstacles to avoid and rewards to collect (billboard sprites with shadows)."""

import math
import random

from .. import config
from ..themes import OBSTACLE_INFO, REWARD_INFO
from .common import card, Shadow


class Obstacle:
    kind = "obstacle"

    def __init__(self, parent, res, name, x, y, z, rng: random.Random):
        info = OBSTACLE_INFO[name]
        self.name = name
        self.size = info["size"] * rng.uniform(0.85, 1.1)
        self.frames = res.frames("obstacles", name)
        self.bx, self.y, self.bz = x, y, z
        self.x, self.z = x, z
        self.moves = info["moves"]
        self.floating = info["floating"]
        self.phase = rng.uniform(0, 6.28)
        self.amp_x = rng.uniform(0.8, 2.0) if self.moves else 0.0
        self.amp_z = rng.uniform(0.4, 1.2) if self.moves else (0.25 if self.floating else 0.0)
        self.speed = rng.uniform(0.6, 1.2)
        self.hit = False
        self.passed = False
        self.root = parent.attachNewNode(name)
        self.root.setBillboardAxis()
        anchor = "bottom" if not self.floating else "center"
        self.sprite = card(self.root, self.frames[0], self.size, self.size, anchor=anchor)
        self.sprite.setDepthWrite(False)
        self.shadow = Shadow(parent, res.texture("fx", "shadow.png"),
                             self.size * (1.05 if not self.floating else 0.9))
        self.tether = None
        if info.get("tether"):
            # mooring chain from the sea floor up to the mine
            self.tether = card(self.root, None, 0.09, 1.0, anchor="bottom")
            self.tether.setColor(0.18, 0.18, 0.2, 1)
        # collision: a circle in the x/z plane (sprites are drawn to fill ~75%)
        self.radius = self.size * (0.36 if name != "net" else 0.45)
        self.anim = rng.uniform(0, 10)
        self.update(0.0, 0.0, 0.0)

    @property
    def center_z(self):
        return self.z if self.floating else self.z + self.size * 0.45

    def update(self, dt, t, player_y):
        if self.moves or self.floating:
            self.x = self.bx + math.sin(t * self.speed + self.phase) * self.amp_x
            self.z = self.bz + math.sin(t * self.speed * 1.3 + self.phase * 2) * self.amp_z
        # floor objects sit slightly into the sand so they look grounded
        self.root.setPos(self.x, self.y, self.z if self.floating else -0.12)
        if self.tether is not None:
            h = max(0.1, self.z - self.size * 0.3)
            self.tether.setScale(1, 1, h)
            self.tether.setZ(-self.z)
        if len(self.frames) > 1:
            self.anim += dt * 7
            self.sprite.setTexture(self.frames[int(self.anim) % len(self.frames)], 1)
        if self.floating:
            self.shadow.update(self.x, self.y, self.center_z)
        else:
            self.shadow.update(self.x, self.y + self.size * 0.12, 0.0)
            self.shadow.np.setColor(0, 0, 0, 0.75)
        # fade the sprite a little once it is behind the player so it does not block the view
        if player_y > self.y:
            self.root.setAlphaScale(max(0.0, 1 - (player_y - self.y) / 3))

    def collides(self, x, y, z, r):
        if abs(y - self.y) > 0.6 + r:
            return False
        rr = self.radius + r
        return (x - self.x) ** 2 + (z - self.center_z) ** 2 < rr * rr

    def remove(self):
        self.shadow.remove()
        self.root.removeNode()


class Reward:
    kind = "reward"

    def __init__(self, parent, res, name, x, y, z, rng: random.Random):
        self.name = name
        self.health, self.size = REWARD_INFO[name]
        self.level = list(REWARD_INFO).index(name)
        self.x, self.y, self.z = x, y, z
        self.phase = rng.uniform(0, 6.28)
        self.taken = False
        self.passed = False
        self.root = parent.attachNewNode(name)
        self.root.setBillboardPointEye()
        self.sprite = card(self.root, res.texture("rewards", f"{name}.png"), self.size, self.size)
        self.sprite.setDepthWrite(False)
        self.shadow = Shadow(parent, res.texture("fx", "shadow.png"), self.size * 0.7)
        self.pop = 0.0
        self.update(0, 0, 0)

    def update(self, dt, t, player_y):
        z = self.z + math.sin(t * 2 + self.phase) * 0.25
        self.root.setPos(self.x, self.y, z)
        if self.taken:
            self.pop += dt
            s = 1 + self.pop * 4
            self.root.setScale(s)
            self.root.setAlphaScale(max(0.0, 1 - self.pop * 3))
            self.root.setZ(z + self.pop * 2)
        else:
            self.sprite.setR(math.sin(t * 1.5 + self.phase) * 12)
            self.root.setScale(1 + 0.07 * math.sin(t * 5 + self.phase))
        self.shadow.update(self.x, self.y, z)
        if self.taken:
            self.shadow.np.hide()

    def collides(self, x, y, z, r):
        if self.taken or abs(y - self.y) > 0.8:
            return False
        rr = self.size * 0.5 + r
        return (x - self.x) ** 2 + (z - self.z) ** 2 < rr * rr

    def remove(self):
        self.shadow.remove()
        self.root.removeNode()


def obstacle_height(name, rng):
    info = OBSTACLE_INFO[name]
    if not info["floating"]:
        return 0.0
    s = info["size"]
    return rng.uniform(s * 0.6 + 1.0, config.WORLD_H - s * 0.6 - 1.5)
