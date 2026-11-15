"""Aim helper: shows where the fish will arrive on the next wall if it keeps
its current height and side position.

A ring is drawn on the face of the next wall, green if that spot is an
opening the fish fits through and red if it will splat.  If an obstacle is in
the way first, the ring sits on the obstacle in red.  A trail of dots joins
the fish to the target; the dots crowd together as the wall gets closer, which
also helps judge distance.
"""

import math

from .. import config
from .common import card

GREEN = (0.35, 1.0, 0.45, 0.9)
RED = (1.0, 0.3, 0.25, 0.95)
DOTS = 7                # dots in the trail between the fish and the ring


class AimHelper:
    """The ring and dots.  Turned on/off with the Aim Helper menu option."""

    def __init__(self, parent, res):
        self.root = parent.attachNewNode("aim")
        self.ring = card(self.root, res.texture("fx", "aim.png"), 1, 1)
        self.dots = [card(self.root, res.texture("fx", "dot.png"), 1, 1) for _ in range(DOTS)]
        for i, np_ in enumerate([self.ring] + self.dots):
            np_.setBillboardPointEye()
            np_.setDepthTest(False)
            np_.setDepthWrite(False)
            np_.setFogOff()
            # the hollow ring is drawn over the fish so it is never hidden behind it
            np_.setBin("fixed", 25 if np_ is self.ring else 14)
        self.root.hide()

    def update(self, player, objects, t):
        """Move the ring/dots for this frame (objects = the course's objects)."""
        p = player
        r = config.FISH_RADIUS
        # the nearest wall the fish hasn't fully passed yet
        wall = None
        for o in objects:
            if o.kind == "wall" and o.back > p.y and (wall is None or o.y < wall.y):
                wall = o
        limit = wall.front if wall else p.y + 60
        target_y, color = None, GREEN
        # first obstacle that lies across the path before the wall
        blockers = [o for o in objects if o.kind == "obstacle" and p.y + 0.5 < o.y < limit
                    and o.collides(p.x, o.y, p.z, r)]
        if blockers:
            target_y, color = min(o.y for o in blockers) - 0.4, RED
        elif wall is not None:
            target_y = max(wall.front - 0.05, p.y + 0.3)
            # ask the wall: would the fish hit it at its current x and z?
            color = RED if wall.collides(p.x, wall.y, p.z, r) else GREEN
        if target_y is None:
            self.root.hide()
            return
        self.root.show()
        pulse = 1 + 0.08 * math.sin(t * 8)
        self.ring.setPos(p.x, target_y, p.z)
        self.ring.setScale(2.4 * pulse)
        self.ring.setColor(*color)
        start = p.y + 1.2
        span = target_y - start
        # dots evenly spaced from just ahead of the fish to the ring, fading out
        for i, d in enumerate(self.dots):
            if span <= 0.5:
                d.hide()
                continue
            d.show()
            f = (i + 1) / (DOTS + 1)
            d.setPos(p.x, start + span * f, p.z)
            d.setScale(0.2)
            d.setColor(color[0], color[1], color[2], 0.75 * (1 - f * 0.5))

    def hide(self):
        self.root.hide()

    def destroy(self):
        self.root.removeNode()
