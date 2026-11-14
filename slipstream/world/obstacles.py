"""Obstacles to avoid and rewards to collect (billboard sprites with shadows)."""

import math
import random

from panda3d.core import ColorBlendAttrib, TransparencyAttrib

from .. import config
from ..themes import OBSTACLE_INFO, REWARD_INFO
from .common import card, flat_card, Shadow
from .terrain import floor_height


class Obstacle:
    kind = "obstacle"

    def __init__(self, parent, res, name, x, y, z, rng: random.Random, bounds=None):
        info = OBSTACLE_INFO[name]
        # the open part of the trench at this distance (moving obstacles stay inside it)
        self.bounds = bounds or (-config.HALF_W, config.HALF_W)
        self.name = name
        self.size = info["size"] * rng.uniform(0.85, 1.1)
        self.frames = res.frames("obstacles", name)
        self.bx, self.y, self.bz = x, y, z
        self.x, self.z = x, z
        self.moves = info["moves"]
        self.floating = info["floating"]
        self.hanging = info.get("hanging", False)      # hangs down from the surface
        self.parent = parent
        self.phase = rng.uniform(0, 6.28)
        mv = info.get("move", dict(ax=(0.8, 2.0), az=(0.4, 1.2), speed=(0.6, 1.2)))
        self.amp_x = rng.uniform(*mv["ax"]) if self.moves else 0.0
        self.amp_z = rng.uniform(*mv["az"]) if self.moves else (0.25 if self.floating else 0.0)
        self.speed = rng.uniform(*mv["speed"])
        self.swing = mv.get("swing", 0.0)              # degrees of pendulum sway (hanging)
        self.hit = False
        self.passed = False
        self.root = parent.attachNewNode(name)
        self.root.setBillboardAxis()
        anchor = "top" if self.hanging else ("center" if self.floating else "bottom")
        # collision: a circle in the x/z plane.  Most sprites fill ~75% of their
        # square; hanging ones say where their dangerous part is (info["hit"])
        hit = info.get("hit")
        self.radius = self.size * (hit[1] if hit else (0.45 if name == "net" else 0.36))
        # hit area can be an oval: rx is the horizontal radius (e.g. a long hull)
        self.stretch = hit[2] if hit and len(hit) > 2 else 1.0
        self.rx = self.radius * self.stretch
        self.sprite = card(self.root, self.frames[0], self.size, self.size, anchor=anchor)
        self.sprite.setDepthWrite(False)
        # pulsing red "danger" glow behind every obstacle, so obstacles stand out
        # from the (non-colliding) scenery on the sea floor
        hs = self.radius * 4.4
        if self.hanging:
            # glow and hit point ride on the sprite so they swing with it
            self.hit_np = self.sprite.attachNewNode("hit")
            self.hit_np.setPos(0, 0, -self.size * hit[0])
            self.halo = card(self.sprite, res.texture("fx", "halo.png"), hs * self.stretch, hs)
            self.halo.setPos(0, 0.08, -self.size * hit[0])
        else:
            self.halo = card(self.root, res.texture("fx", "halo.png"), hs, hs)
            self.halo.setPos(0, 0.08, 0 if self.floating else self.size * 0.45)
        self.halo.setDepthWrite(False)
        self.halo.setColor(1.0, 0.18, 0.08, 1)
        self.ring = None
        if not self.floating and not self.hanging:
            # red danger ring on the sand around things sitting on the floor
            self.ring = flat_card(parent, res.texture("fx", "halo.png"), self.size * 1.5, self.size * 1.1)
            self.ring.setTransparency(TransparencyAttrib.M_alpha)
            self.ring.setDepthWrite(False)
            self.ring.setDepthOffset(3)
            self.ring.setColor(1.0, 0.15, 0.05, 1)
            self.ring.setPos(x, y + self.size * 0.1, float(floor_height(x, y)) + 0.12)
        shadow_size = self.rx * 2.6 if self.hanging else self.size * (0.9 if self.floating else 1.05)
        self.shadow = Shadow(parent, res.texture("fx", "shadow.png"), shadow_size)
        self.tether = None
        if info.get("tether"):
            # mooring chain from the sea floor up to the mine
            self.tether = card(self.root, None, 0.09, 1.0, anchor="bottom")
            self.tether.setColor(0.18, 0.18, 0.2, 1)
        self.anim = rng.uniform(0, 10)
        self.update(0.0, 0.0, 0.0)

    def center(self):
        """(x, z) of the dangerous part, used for collisions and the shadow."""
        if self.hanging:
            p = self.hit_np.getPos(self.parent)
            return p.x, p.z
        return self.x, (self.z if self.floating else self.z + self.size * 0.45)

    @property
    def center_z(self):
        return self.center()[1]

    def update(self, dt, t, player_y):
        if self.hanging:
            # drifts a little, bobs at the surface and sways like a pendulum
            self.x = self.bx + math.sin(t * self.speed + self.phase) * self.amp_x
            self.x = max(self.bounds[0] + self.rx, min(self.bounds[1] - self.rx, self.x))
            self.z = config.WORLD_H + 0.1 + math.sin(t * self.speed * 1.3 + self.phase) * self.amp_z
            self.sprite.setR(math.sin(t * self.speed * 1.6 + self.phase * 2) * self.swing)
        elif self.moves or self.floating:
            # a figure-of-eight style path (different rates side-to-side and up/down)
            sx = math.sin(t * self.speed + self.phase)
            self.x = self.bx + sx * self.amp_x
            self.z = self.bz + math.sin(t * self.speed * 1.3 + self.phase * 2) * self.amp_z
            half = self.size * 0.5
            self.x = max(self.bounds[0] + half, min(self.bounds[1] - half, self.x))
            self.z = max(half, min(config.WORLD_H - half, self.z))
            if self.moves:
                # lean into the direction of travel
                self.sprite.setR(math.cos(t * self.speed + self.phase) * min(10.0, self.amp_x * 2.5))
        # floor objects sit slightly into the sand so they look grounded
        self.root.setPos(self.x, self.y, self.z if (self.floating or self.hanging) else -0.12)
        if self.tether is not None:
            h = max(0.1, self.z - self.size * 0.3)
            self.tether.setScale(1, 1, h)
            self.tether.setZ(-self.z)
        if len(self.frames) > 1:
            self.anim += dt * 7
            self.sprite.setTexture(self.frames[int(self.anim) % len(self.frames)], 1)
        if self.hanging:
            cx, cz = self.center()
            self.shadow.update(cx, self.y, cz)
        elif self.floating:
            self.shadow.update(self.x, self.y, self.center_z)
        else:
            self.shadow.update(self.x, self.y + self.size * 0.12, 0.0)
            self.shadow.np.setColor(0, 0, 0, 0.75)
        # fade the sprite a little once it is behind the player so it does not block the view
        pulse = 0.5 + 0.5 * math.sin(t * 4 + self.phase)
        self.halo.setAlphaScale(0.28 + 0.18 * pulse)
        if self.ring is not None:
            self.ring.setAlphaScale((0.3 + 0.2 * pulse) * (1.0 if player_y <= self.y else 0.0))
        if player_y > self.y:
            self.root.setAlphaScale(max(0.0, 1 - (player_y - self.y) / 3))

    def collides(self, x, y, z, r):
        if abs(y - self.y) > 0.6 + r:
            return False
        cx, cz = self.center()
        # oval (or circle) grown by the fish's radius
        return ((x - cx) / (self.rx + r)) ** 2 + ((z - cz) / (self.radius + r)) ** 2 < 1.0

    def remove(self):
        self.shadow.remove()
        if self.ring is not None:
            self.ring.removeNode()
        self.root.removeNode()


REWARD_GLOW = {
    "pearl": (1.0, 0.9, 1.0),
    "shell": (1.0, 0.75, 0.6),
    "starfish": (1.0, 0.9, 0.4),
    "gem": (0.5, 1.0, 1.0),
}


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
        # soft additive glow behind the reward (brighter than the obstacle glow)
        gs = self.size * 1.8
        self.glow = card(self.root, res.texture("fx", "glow.png"), gs, gs)
        self.glow.setPos(0, 0.05, 0)
        self.glow.setDepthWrite(False)
        self.glow.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_incoming_alpha,
                                                  ColorBlendAttrib.O_one))
        self.glow.setColor(*REWARD_GLOW.get(name, (1, 1, 0.8)), 1)
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
            self.glow.setAlphaScale(0.38 + 0.12 * math.sin(t * 5 + self.phase))
            self.glow.setR(t * 20)
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
    if info.get("hanging"):
        return config.WORLD_H
    if not info["floating"]:
        return 0.0
    s = info["size"]
    return rng.uniform(s * 0.6 + 1.0, config.WORLD_H - s * 0.6 - 1.5)
