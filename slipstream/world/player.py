"""The player's fish (or submarine), seen from behind."""

import math

from panda3d.core import TransparencyAttrib

from .. import config
from .common import card, Shadow
from .trench import STRAIGHT


class Player:
    def __init__(self, base, res, theme, parent):
        self.root = parent.attachNewNode("player")
        self.frames = res.frames("player", theme.player)
        self.holder = self.root.attachNewNode("holder")      # billboarded
        self.holder.setBillboardPointEye()
        size = config.FISH_SIZE * (1.15 if theme.player == "sub" else 1.0)
        self.sprite = card(self.holder, self.frames[0], size, size,
                           transparency=TransparencyAttrib.M_alpha)
        self.sprite.setBin("fixed", 20)   # always drawn over the scenery it is inside of
        self.sprite.setDepthWrite(False)
        self.sprite.setDepthTest(False)
        self.sprite.setFogOff()
        self.shadow = Shadow(parent, res.texture("fx", "shadow.png"), 2.1)
        self.trench = STRAIGHT
        self.reset()

    def set_trench(self, trench):
        self.trench = trench

    def reset(self):
        self.x, self.y, self.z = 0.0, 0.0, config.WORLD_H * 0.45
        self.vx = self.vz = 0.0
        self.anim = 0.0
        self.frame = 0
        self.flash = 0.0
        self.moving = False

    def update(self, dt, ix, iz, forward_speed):
        """ix, iz in {-1, 0, 1}.  Returns a list of event names."""
        events = []
        self.moving = ix != 0 or iz != 0
        tx = ix * config.LATERAL_SPEED
        tz = iz * config.VERTICAL_SPEED if iz else -config.SINK_SPEED
        k = min(1.0, config.ACCEL * dt)
        self.vx += (tx - self.vx) * k
        # active swimming responds quickly; on release the fish stops climbing
        # promptly, then the slow sink eases in (no overshoot or rebound)
        if iz:
            self.vz += (tz - self.vz) * k
        elif self.vz > 0:
            self.vz = max(0.0, self.vz - self.vz * min(1.0, k * 1.8) - 2.0 * dt)
        else:
            self.vz += (tz - self.vz) * k * 0.35
        self.x += self.vx * dt
        self.z += self.vz * dt
        self.y += forward_speed * dt

        r = config.FISH_RADIUS
        # side cliffs (they drift, so they can also push a fish that's not moving)
        lo, hi = self.trench.bounds(self.y, r + 0.4)
        for side, limit in ((1, hi), (-1, lo)):
            if (self.x - limit) * side > 0:
                self.x = limit
                if self.vx * side > -1.0:
                    self.vx = -side * (abs(self.vx) * config.SIDE_BOUNCE + 1.5)
                    events.append("side")
        floor = r + 0.15
        if self.z < floor:
            self.z = floor
            if self.vz < -0.4:
                self.vz = config.FLOOR_BOUNCE
                events.append("floor")
            else:
                self.vz = max(self.vz, 0.0)
        top = config.WORLD_H - r - 0.6
        if self.z > top:
            self.z = top
            self.vz = min(self.vz, 0.0)

        # swim animation: fast while moving, lazy while drifting
        rate = 14.0 if self.moving else 4.0
        self.anim += dt * rate
        self.frame = int(self.anim) % len(self.frames)
        self.flash = max(0.0, self.flash - dt)
        return events

    def sync(self, t):
        self.root.setPos(self.x, self.y, self.z + math.sin(t * 2.2) * 0.05)
        self.sprite.setTexture(self.frames[self.frame], 1)
        self.sprite.setR(self.vx * 2.6)
        # slight squash so diving/climbing reads visually
        self.sprite.setScale(1.0, 1.0, 1.0 - max(-0.08, min(0.08, self.vz * 0.012)))
        if self.flash > 0:
            on = int(self.flash * 16) % 2 == 0
            self.sprite.setColorScale(1, 0.45 if on else 1, 0.45 if on else 1, 0.55 if on else 1)
        else:
            self.sprite.setColorScale(1, 1, 1, 1)
        self.shadow.update(self.x, self.y, self.z)

    def destroy(self):
        self.shadow.remove()
        self.root.removeNode()
