"""Course generation: spawns walls, obstacles and rewards ahead of the player
and removes them once they are far behind.  Also holds the distance markers
for 'last run' and 'best time'."""

import random

from panda3d.core import ColorBlendAttrib, TextNode, TransparencyAttrib

from .. import config
from .common import card, flat_card
from .obstacles import Obstacle, Reward, obstacle_height
from .walls import WallFactory

REWARD_WEIGHTS = {"pearl": 0.45, "shell": 0.3, "starfish": 0.18, "gem": 0.07}


def lerp(a, b, t):
    return a + (b - a) * t


class Course:
    def __init__(self, parent, res, theme, seed=None):
        self.parent = parent.attachNewNode("course")
        self.res = res
        self.theme = theme
        self.rng = random.Random(seed)
        self.factory = WallFactory(res, theme, seed)
        self.objects = []
        self.next_wall_y = 55.0
        # where the player can be coming from: the start spot, then the
        # previous wall's openings (used to keep every wall reachable)
        self.prev_y = 0.0
        self.anchors = [(0.0, config.WORLD_H * 0.45)]
        self.enabled = True

    def fill(self, player_y, difficulty):
        if not self.enabled:
            return
        while self.next_wall_y < player_y + config.SPAWN_AHEAD:
            self._segment(difficulty)

    def _segment(self, d):
        rng = self.rng
        wall = self.factory.create(self.parent, self.next_wall_y, d, self.anchors, self.prev_y)
        self.prev_y = wall.back
        self.anchors = [(o[0], o[1]) for o in wall.openings]
        self.objects.append(wall)
        gap = rng.uniform(lerp(46, 30, d), lerp(78, 52, d))
        next_y = self.next_wall_y + gap

        # a reward hovering in front of an opening now and then
        if rng.random() < 0.45:
            cx, cz, *_ = rng.choice(wall.openings)
            self._reward(cx, wall.front - 3.0, cz)

        # Obstacles between this wall and the next.  Their number rises slowly
        # with difficulty: rows get closer together, a row is more likely to
        # hold an obstacle, and later rows may hold two side by side.
        y = wall.back + rng.uniform(9, 16)
        while y < next_y - 10:
            if rng.random() < lerp(0.55, 0.95, d):
                xs = [self._obstacle_x(wall)]
                if rng.random() < lerp(0.0, 0.5, d):
                    x2 = self._obstacle_x(wall)
                    if abs(x2 - xs[0]) > 8:
                        xs.append(x2)
                for ox in xs:
                    name = rng.choice(self.theme.obstacles)
                    self.objects.append(Obstacle(self.parent, self.res, name, ox, y,
                                                 obstacle_height(name, rng), rng))
            elif rng.random() < 0.7:
                self._reward(rng.uniform(-config.HALF_W + 3, config.HALF_W - 3), y,
                             rng.uniform(1.5, config.WORLD_H - 2.5))
            y += rng.uniform(lerp(18, 9, d), lerp(30, 16, d))
        self.next_wall_y = next_y

    def _obstacle_x(self, wall):
        rng = self.rng
        if rng.random() < 0.5:
            ox = rng.uniform(-config.HALF_W + 3, config.HALF_W - 3)
        else:  # near where the player is likely to swim
            ox = rng.choice(wall.openings)[0] + rng.uniform(-3, 3)
        return max(-config.HALF_W + 2.5, min(config.HALF_W - 2.5, ox))

    def _reward(self, x, y, z):
        names = list(REWARD_WEIGHTS)
        name = self.rng.choices(names, weights=[REWARD_WEIGHTS[n] for n in names])[0]
        self.objects.append(Reward(self.parent, self.res, name, x, y, z, self.rng))

    def update(self, dt, t, player_y):
        keep = []
        for o in self.objects:
            if o.y < player_y - config.DESPAWN_BEHIND:
                o.remove()
                continue
            if o.y < player_y + config.SPAWN_AHEAD + 10:
                o.update(dt, t, player_y)
            keep.append(o)
        self.objects = keep

    def clear(self):
        for o in self.objects:
            o.remove()
        self.objects = []

    def destroy(self):
        self.clear()
        self.parent.removeNode()


class DistanceMarker:
    """A glowing gate across the corridor at a given distance, with a label."""

    def __init__(self, parent, res, y, label, color, tex_name):
        self.y = y
        self.root = parent.attachNewNode("marker")
        self.root.setPos(0, y, 0)
        tex = res.texture("fx", tex_name)
        add = ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_incoming_alpha,
                                    ColorBlendAttrib.O_one)
        for i in range(17):
            x = -config.HALF_W + 1 + i * (2 * config.HALF_W - 2) / 16
            c = card(self.root, tex, 0.8, config.WORLD_H, anchor="bottom")
            c.setX(x)
            c.setAttrib(add)
            c.setDepthWrite(False)
            c.setBin("fixed", 4)
            c.setColor(1, 1, 1, 0.9)
        stripe = flat_card(self.root, None, 2 * config.HALF_W, 0.5)
        stripe.setZ(0.06)
        stripe.setColor(*color, 0.7)
        stripe.setTransparency(TransparencyAttrib.M_alpha)
        tn = TextNode("label")
        tn.setText(label)
        tn.setAlign(TextNode.ACenter)
        tn.setTextColor(*color, 1)
        tn.setShadow(0.05, 0.05)
        tn.setShadowColor(0, 0, 0, 0.8)
        self.text = self.root.attachNewNode(tn)
        self.text.setScale(1.7)
        self.text.setBillboardPointEye()
        self.text.setLightOff()
        self.text.setFogOff()
        self.text.setDepthWrite(False)
        self.text.setBin("fixed", 6)
        self.label_x = 0.0

    def update(self, player_x, player_y, t):
        self.text.setPos(player_x, 0, config.WORLD_H * 0.62 + 0.2 * (t % 1.0 < 0.5))
        if player_y > self.y:
            self.root.setAlphaScale(max(0.0, 1 - (player_y - self.y) / 6))

    def remove(self):
        self.root.removeNode()
