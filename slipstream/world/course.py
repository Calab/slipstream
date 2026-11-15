"""Course generation: spawns walls, obstacles and rewards ahead of the player
and removes them once they are far behind.  Also holds the distance markers
for 'last run' and 'best time'.

The course is endless and random, but generated in order from one seed:
it is built one *segment* at a time, each segment being a wall followed by
rows of obstacles (or the odd reward) up to where the next wall goes.  New
segments are added whenever the next wall position comes within
SPAWN_AHEAD of the player, so there is always about that much course ahead.

Every object in Course.objects has the same small interface used by
World.update: ``kind`` ("wall" / "obstacle" / "reward"), ``y``,
``collides(x, y, z, r)``, ``update(dt, t, player_y)``, ``remove()`` and the
flags ``hit`` / ``passed``.
"""

import random

from panda3d.core import ColorBlendAttrib, TextNode, TransparencyAttrib

from .. import config
from .common import card, flat_card
from .obstacles import Obstacle, Reward, obstacle_height
from .trench import STRAIGHT
from .walls import WallFactory

# how often each reward appears (relative chances): small ones are common,
# the big health gem is rare
REWARD_WEIGHTS = {"pearl": 0.45, "shell": 0.3, "starfish": 0.18, "gem": 0.07}


def lerp(a, b, t):
    """Blend from a (t=0) to b (t=1).  Used with t = difficulty below, e.g.
    lerp(46, 30, d) is 46 at the start and 30 at full difficulty."""
    return a + (b - a) * t


class Course:
    """The walls, obstacles and rewards of one run."""

    def __init__(self, parent, res, theme, seed=None, trench=None):
        self.parent = parent.attachNewNode("course")
        self.trench = trench or STRAIGHT
        self.res = res
        self.theme = theme
        self.rng = random.Random(seed)
        self.factory = WallFactory(res, theme, seed)
        self.objects = []
        self.next_wall_y = 55.0         # where the first wall goes (a calm start)
        # where the player can be coming from: the start spot, then the
        # previous wall's openings (used to keep every wall reachable)
        self.prev_y = 0.0
        self.anchors = [(0.0, config.WORLD_H * 0.45)]
        self.enabled = True

    def fill(self, player_y, difficulty):
        """Generate segments until the course reaches SPAWN_AHEAD past the player."""
        if not self.enabled:
            return
        while self.next_wall_y < player_y + config.SPAWN_AHEAD:
            self._segment(difficulty)

    def _segment(self, d):
        """Add one wall plus whatever comes between it and the next wall.
        d is the difficulty, 0 (start) .. 1 (hardest)."""
        rng = self.rng
        wall = self.factory.create(self.parent, self.next_wall_y, d, self.anchors, self.prev_y,
                                   x_range=self.trench.bounds(self.next_wall_y, 3.0))
        # the next wall must be reachable from one of this wall's openings
        self.prev_y = wall.back
        self.anchors = [(o[0], o[1]) for o in wall.openings]
        self.objects.append(wall)
        # distance to the next wall: shorter as difficulty rises
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
                xs = [self._obstacle_x(wall, y)]
                if rng.random() < lerp(0.0, 0.5, d):
                    x2 = self._obstacle_x(wall, y)
                    if abs(x2 - xs[0]) > 8:
                        xs.append(x2)
                for ox in xs:
                    name = rng.choice(self.theme.obstacles)
                    self.objects.append(Obstacle(self.parent, self.res, name, ox, y,
                                                 obstacle_height(name, rng), rng,
                                                 bounds=self.trench.bounds(y)))
            elif rng.random() < 0.7:
                self._reward(rng.uniform(*self.trench.bounds(y, 3.0)), y,
                             rng.uniform(1.5, config.WORLD_H - 2.5))
            y += rng.uniform(lerp(18, 9, d), lerp(30, 16, d))
        self.next_wall_y = next_y

    def _obstacle_x(self, wall, y):
        """Pick an x for an obstacle at distance y: anywhere half the time,
        otherwise in line with one of the wall's openings (where the fish is
        probably heading)."""
        rng = self.rng
        lo, hi = self.trench.bounds(y, 2.5)
        if rng.random() < 0.5:
            ox = rng.uniform(lo, hi)
        else:  # near where the player is likely to swim
            ox = rng.choice(wall.openings)[0] + rng.uniform(-3, 3)
        return max(lo, min(hi, ox))

    def _reward(self, x, y, z):
        """Add a random reward (chosen by REWARD_WEIGHTS) at (x, y, z)."""
        names = list(REWARD_WEIGHTS)
        name = self.rng.choices(names, weights=[REWARD_WEIGHTS[n] for n in names])[0]
        self.objects.append(Reward(self.parent, self.res, name, x, y, z, self.rng))

    def update(self, dt, t, player_y):
        """Animate the objects and delete those left far behind the player."""
        keep = []
        for o in self.objects:
            if o.y < player_y - config.DESPAWN_BEHIND:
                o.remove()
                continue
            if o.y < player_y + config.SPAWN_AHEAD + 10:     # objects far ahead can wait
                o.update(dt, t, player_y)
            keep.append(o)
        self.objects = keep

    def clear(self):
        """Remove every object."""
        for o in self.objects:
            o.remove()
        self.objects = []

    def destroy(self):
        """Remove every object and the course's scene node."""
        self.clear()
        self.parent.removeNode()


class DistanceMarker:
    """A glowing gate across the corridor at a given distance, with a label."""

    def __init__(self, parent, res, y, label, color, tex_name):
        self.y = y
        self.root = parent.attachNewNode("marker")
        self.root.setPos(0, y, 0)
        tex = res.texture("fx", tex_name)
        # "additive" blending: the card's colour is added to what's behind it,
        # so it glows (brightens) rather than covering things up
        add = ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_incoming_alpha,
                                    ColorBlendAttrib.O_one)
        # a row of 17 glowing posts across the corridor, plus a stripe on the floor
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
        """Keep the label in front of the fish (hopping up and down once a
        second) and fade the gate out once the fish has gone through it."""
        self.text.setPos(player_x, 0, config.WORLD_H * 0.62 + 0.2 * (t % 1.0 < 0.5))
        if player_y > self.y:
            self.root.setAlphaScale(max(0.0, 1 - (player_y - self.y) / 6))

    def remove(self):
        """Remove the gate from the scene."""
        self.root.removeNode()
