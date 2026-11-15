"""The shape of the trench: how far each side cliff has drifted inwards.

Each cliff wanders in and out independently by up to MAX_INSET units, changing
gradually with distance, so the rock can creep towards a fish that is sitting
still near one side.  With both cliffs fully in, the trench is 60% of its full
width (MAX_INSET is 20% of the width per side).  There are no bends: the trench keeps running straight
ahead, only its edges move.  The first stretch is straight so a run starts
calmly.
"""

import math
import random

import numpy as np

from .. import config

MAX_INSET = 9.6          # furthest a cliff moves in from its home position (per side)
DRIFT_SCALE = 4.16       # how strongly the waves below move the cliff (big swings that
                         # often reach fully in or fully out)
STRAIGHT_UNTIL = 25.0    # distance before the cliffs start to wander
RAMP = 60.0              # distance over which the wandering fades in
# (wavelength, amplitude) of the gentle waves that make up each cliff's drift
WAVES = ((232.0, 1.0), (147.0, 0.7), (88.0, 0.35))   # long, so the rock never outpaces the fish


class Trench:
    """The cliff drift for one run (different seed -> different pattern)."""

    def __init__(self, seed=None):
        rng = random.Random(seed)
        # a random starting phase for every wave on each side, so the two
        # cliffs move independently
        self.phases = {side: [rng.uniform(0, 2 * math.pi) for _ in WAVES] for side in (-1, 1)}

    def inset(self, y, side):
        """How far the cliff on `side` (-1 left, +1 right) has moved inwards at
        distance y.  Works on floats and numpy arrays."""
        # start halfway in, then add the waves; the large DRIFT_SCALE means the
        # sum often goes past 0 or MAX_INSET and is clipped, so the cliff
        # spends stretches fully out or fully in
        d = MAX_INSET / 2
        for (wl, amp), ph in zip(WAVES, self.phases[side]):
            d = d + DRIFT_SCALE * amp * np.sin(2 * math.pi * y / wl + ph)
        d = np.clip(d, 0.0, MAX_INSET)
        # fade the drift in after the straight start: t goes 0 -> 1 over RAMP
        # units, and t*t*(3-2t) ("smoothstep") makes that start and end gently
        t = np.clip((np.asarray(y, dtype=float) - STRAIGHT_UNTIL) / RAMP, 0.0, 1.0)
        out = d * t * t * (3 - 2 * t)
        return float(out) if np.ndim(out) == 0 else out

    def left(self, y):
        """x of the left cliff's home face at distance y."""
        return -(config.HALF_W - self.inset(y, -1))

    def right(self, y):
        """x of the right cliff's home face at distance y."""
        return config.HALF_W - self.inset(y, 1)

    def bounds(self, y, margin=0.0):
        """(min x, max x) of open water at distance y, shrunk by `margin` on
        each side (e.g. the fish's radius).  A negative margin widens it."""
        return self.left(y) + margin, self.right(y) - margin


# A trench whose cliffs never move: used on the title screen and before the
# first run, when there is no run-specific trench yet.
STRAIGHT = Trench(0)
STRAIGHT.inset = lambda y, side: 0.0 if np.ndim(y) == 0 else np.zeros_like(y, dtype=float)
