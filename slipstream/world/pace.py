"""Forward speed over time, and the inverse (time at which a distance is reached).

The course generator uses these to know how long the player has to get from
one wall to the next, so every wall has an opening that can be reached.
"""

import math

from .. import config

S0 = config.FORWARD_SPEED_START
S1 = config.FORWARD_SPEED_MAX
R = config.FORWARD_SPEED_RAMP


def forward_speed(t):
    return S0 + (S1 - S0) * (1 - math.exp(-t / R))


def distance_at(t):
    """Integral of forward_speed from 0 to t."""
    return S0 * t + (S1 - S0) * (t - R * (1 - math.exp(-t / R)))


def time_at(y):
    """Inverse of distance_at (bisection; distance is monotonic in time)."""
    lo, hi = 0.0, max(1.0, y / S0)
    for _ in range(50):
        mid = (lo + hi) / 2
        if distance_at(mid) < y:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def reach(y_from, y_to):
    """How far (x, z) the player can comfortably move between two distances.

    Uses 60% of top swimming speed and allows ~0.6 s to react, so a wall is
    never generated that only a perfect player could get to.
    """
    t = max(0.3, time_at(y_to) - time_at(y_from) - 0.6)
    return config.LATERAL_SPEED * t * 0.6, config.VERTICAL_SPEED * t * 0.6
