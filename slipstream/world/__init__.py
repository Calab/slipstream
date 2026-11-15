"""The 3D underwater world: environment, player, course and camera.

:class:`World` is the 3D half of the game.  The app calls
:meth:`World.update` once per frame with the player's input; the world moves
the fish, keeps the course of walls/obstacles filled ahead of it, checks
collisions, places the camera and reports back what happened.  It knows
nothing about health or scoring: that is up to the app.

Package layout:
    player.py       the fish (or sub / mermaid) and its movement
    course.py       creates walls, obstacles and rewards ahead of the player
    walls.py        walls with irregular holes (drawing and collision)
    obstacles.py    obstacles to avoid and rewards to collect
    trench.py       how the side cliffs drift in and out along the course
    terrain.py      3D meshes for the sea floor and side cliffs
    environment.py  floor, cliffs, fog, lights, background, scenery
    effects.py      bubbles
    aim.py          the optional aim helper (ring + dotted trail)
    pace.py         forward speed over time (and how far you can get)
    common.py       small helpers for flat textured "cards" and shadows
"""

import math

from .. import config
from .aim import AimHelper
from .course import Course, DistanceMarker
from .effects import Bubbles
from .environment import Environment
from .player import Player
from .trench import Trench


class World:
    """Everything in the 3D scene for one theme.  Created by the app's
    load_theme(); a new run reuses it via start_run()."""

    def __init__(self, base, res, theme):
        self.base = base
        self.res = res
        self.theme = theme
        # every world object hangs off this node, so removing it removes them all
        self.root = base.render.attachNewNode("world")
        self.env = Environment(base, res, theme)
        self.player = Player(base, res, theme, self.root)
        self.bubbles = Bubbles(self.root, res)
        self.aim = AimHelper(self.root, res)
        self.aim_enabled = True
        self.course = None          # only exists during a run
        self.markers = []           # "Last Run" / "Best" gates
        self.cam_dist = config.CAM_DIST_DEFAULT
        self.cam_x = 0.0            # camera's left/right position
        self.lead = 0.0             # how far the fish is ahead of the camera sideways
        self.pitch = math.radians(-9)   # camera tilt (negative = looking down)
        self.top_cover = 0.17      # fraction of the screen covered by the HUD + wave band
        self.shake = 0.0            # seconds of camera shake left (set on hits)
        self.time = 0.0             # seconds since this world was created (drives animations)

    # -- runs ----------------------------------------------------------------
    def start_run(self, record, seed=None):
        """Reset the fish and build a new course from `seed`.  `record` is the
        theme's saved record, used to place the Last Run / Best markers."""
        if self.course:
            self.course.destroy()
        for m in self.markers:
            m.remove()
        self.markers = []
        self.player.reset()
        self.cam_x = self.lead = 0.0
        # every run gets its own pattern of drifting side cliffs
        self.trench = Trench(seed)
        self.player.set_trench(self.trench)
        self.env.set_trench(self.trench)
        self.course = Course(self.root, self.res, self.theme, seed, self.trench)
        self.course.fill(self.player.y, 0.0)
        # glowing gates at the distances reached last time and in the best run
        # (the best one is skipped if it would sit almost on top of the last one)
        if record["last_distance"] > 20:
            self.markers.append(DistanceMarker(self.root, self.res, record["last_distance"],
                                               "Last Run", (1.0, 0.8, 0.25), "marker_last.png"))
        if record["best_distance"] > 20 and abs(record["best_distance"] - record["last_distance"]) > 4:
            self.markers.append(DistanceMarker(self.root, self.res, record["best_distance"],
                                               "Best", (0.4, 1.0, 0.55), "marker_best.png"))

    def end_run(self):
        """Remove the course (walls etc.); the fish and scenery stay."""
        if self.course:
            self.course.destroy()
            self.course = None
        self.aim.hide()

    # -- per-frame -----------------------------------------------------------
    def update(self, dt, ix, iz, speed, zoom, active=True):
        """Advance the world by dt seconds.

        ix, iz: input directions (-1, 0, +1); speed: forward speed; zoom: camera
        zoom direction.  active=False (menu, game over) moves the fish and
        scenery but skips course generation and collisions.

        Returns (events, hits): events from Player.update ("floor", "side") and
        a list of (kind, object) where kind is "hit", "reward" or "passed".
        """
        self.time += dt
        t = self.time
        p = self.player
        events = p.update(dt, ix, iz, speed)
        hits = []
        if self.course and active:
            # difficulty grows from 0 to 1 over the first DIFFICULTY_DISTANCE units
            difficulty = min(1.0, p.y / config.DIFFICULTY_DISTANCE)
            self.course.fill(p.y, difficulty)
            for o in self.course.objects:
                # Only objects within 4 units of the fish (along the course) can
                # touch it.  Anything else that is now behind the fish, and was
                # never marked, has been safely passed.
                if abs(o.y - p.y) > 4:
                    if not o.passed and o.y < p.y and o.kind != "reward":
                        o.passed = True
                        hits.append(("passed", o))
                    continue
                if o.kind == "reward":
                    if o.collides(p.x, p.y, p.z, config.FISH_RADIUS):
                        o.taken = True
                        hits.append(("reward", o))
                elif not o.hit and o.collides(p.x, p.y, p.z, config.FISH_RADIUS):
                    o.hit = True            # each wall/obstacle can only hurt once
                    hits.append(("hit", o))
            self.course.update(dt, t, p.y)
        for m in self.markers:
            m.update(p.x, p.y, t)

        if "floor" in events:
            self.bubbles.spawn(p.x, p.y, p.z - 0.3, count=10, spread=0.5)
        self.bubbles.update(dt, t, p.y - self.cam_dist)

        # camera zoom (A/Z), kept within the allowed range
        self.cam_dist = max(config.CAM_DIST_MIN, min(config.CAM_DIST_MAX,
                                                     self.cam_dist + zoom * config.CAM_ZOOM_SPEED * dt))
        # The fish leads the camera slightly in the direction it swims (the scene
        # slides the other way).  The lead builds quickly but relaxes slowly once
        # you stop, so the fish never appears to spring back.
        target = max(-config.CAM_LEAD_MAX, min(config.CAM_LEAD_MAX, p.vx * config.CAM_LEAD))
        # "growing" = the lead needs to get bigger, or flip to the other side
        growing = abs(target) > abs(self.lead) or target * self.lead < 0
        rate = 4.0 if growing else config.CAM_LEAD_RELAX
        # move a fraction of the way towards the target each frame (smooth easing;
        # this "x += (target - x) * k" pattern is used all over the game)
        self.lead += (target - self.lead) * min(1.0, rate * dt)
        self.cam_x = p.x - self.lead

        # push the new positions into the scene graph, in a sensible order:
        # fish first, then things placed relative to it, then camera and scenery
        p.sync(t)
        if self.course and active and self.aim_enabled:
            self.aim.update(p, self.course.objects, t)
        else:
            self.aim.hide()
        self._place_camera(dt)
        self.env.update(self.cam_x, p.y - self.cam_dist, p.y, t)
        return events, hits

    def _place_camera(self, dt):
        """Position the camera behind the fish and choose a downward tilt that
        keeps both the fish and its shadow on the sea floor in view (the fish
        takes priority if both cannot fit, e.g. when zoomed right in).

        The maths: an object at height h, distance d in front of the camera,
        appears at an angle atan2(h - cam_z, d) above the horizontal.  A point
        at vertical screen position s (-1 bottom .. +1 top, "NDC") is at angle
        atan(s * tan(vfov/2)) above the camera's centre line.  So the tilt that
        puts the object at screen position s is the difference of the two.
        """
        p = self.player
        d = self.cam_dist
        H = config.WORLD_H
        vf = math.radians(config.CAM_VFOV)
        aspect = self.base.getAspectRatio()
        # keep the *vertical* field of view fixed; wider windows see more sideways
        hf = 2 * math.atan(math.tan(vf / 2) * aspect)
        self.base.camLens.setFov(math.degrees(hf), math.degrees(vf))

        # camera height: follows the fish halfway, a bit higher when zoomed out
        cam_z = max(0.8, min(H - 0.4, p.z * 0.5 + 1.0 + d * 0.15))
        T = math.tan(vf / 2)
        top_ndc = 1 - 2 * self.top_cover - 0.06     # just below the wave band
        bot_ndc = -1 + 0.08                         # just above the bottom edge
        a_fish = math.atan2(p.z + config.FISH_SIZE * 0.5 - cam_z, d)   # top of the fish
        a_shadow = math.atan2(-cam_z, d + 0.6)                         # its shadow on the floor
        lo = a_fish - math.atan(top_ndc * T)        # tilt needed to keep the fish in view
        hi = a_shadow - math.atan(bot_ndc * T)      # tilt needed to keep the shadow in view
        # prefer a gentle -9 degree tilt, within [lo, hi]; if no tilt shows both,
        # use lo (keep the fish)
        target = max(lo, min(math.radians(-9), hi)) if lo <= hi else lo
        self.pitch += (target - self.pitch) * min(1.0, dt * 5)

        # camera shake after a hit: fast, fading wobble
        sx = sz = 0.0
        if self.shake > 0:
            self.shake = max(0.0, self.shake - dt)
            sx = math.sin(self.time * 71) * self.shake * 0.5
            sz = math.cos(self.time * 57) * self.shake * 0.4
        cam = self.base.camera
        cam.setPos(self.cam_x + sx, p.y - d, cam_z + sz)
        cam.setHpr(0, math.degrees(self.pitch), 0)   # heading, pitch, roll in degrees

    def destroy(self):
        """Remove everything this world added to the scene (theme change)."""
        self.end_run()
        for m in self.markers:
            m.remove()
        self.aim.destroy()
        self.bubbles.destroy()
        self.player.destroy()
        self.env.destroy()
        self.root.removeNode()
