"""The 3D underwater world: environment, player, course and camera."""

import math

from .. import config
from .aim import AimHelper
from .course import Course, DistanceMarker
from .effects import Bubbles
from .environment import Environment
from .player import Player
from .trench import Trench


class World:
    def __init__(self, base, res, theme):
        self.base = base
        self.res = res
        self.theme = theme
        self.root = base.render.attachNewNode("world")
        self.env = Environment(base, res, theme)
        self.player = Player(base, res, theme, self.root)
        self.bubbles = Bubbles(self.root, res)
        self.aim = AimHelper(self.root, res)
        self.aim_enabled = True
        self.course = None
        self.markers = []
        self.cam_dist = config.CAM_DIST_DEFAULT
        self.cam_x = 0.0
        self.lead = 0.0
        self.pitch = math.radians(-9)
        self.top_cover = 0.17      # fraction of the screen covered by the HUD + wave band
        self.shake = 0.0
        self.time = 0.0

    # -- runs ----------------------------------------------------------------
    def start_run(self, record, seed=None):
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
        if record["last_distance"] > 20:
            self.markers.append(DistanceMarker(self.root, self.res, record["last_distance"],
                                               "Last Run", (1.0, 0.8, 0.25), "marker_last.png"))
        if record["best_distance"] > 20 and abs(record["best_distance"] - record["last_distance"]) > 4:
            self.markers.append(DistanceMarker(self.root, self.res, record["best_distance"],
                                               "Best", (0.4, 1.0, 0.55), "marker_best.png"))

    def end_run(self):
        if self.course:
            self.course.destroy()
            self.course = None
        self.aim.hide()

    # -- per-frame -----------------------------------------------------------
    def update(self, dt, ix, iz, speed, zoom, active=True):
        """Advance the world.  Returns player events and collisions."""
        self.time += dt
        t = self.time
        p = self.player
        events = p.update(dt, ix, iz, speed)
        hits = []
        if self.course and active:
            difficulty = min(1.0, p.y / config.DIFFICULTY_DISTANCE)
            self.course.fill(p.y, difficulty)
            for o in self.course.objects:
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
                    o.hit = True
                    hits.append(("hit", o))
            self.course.update(dt, t, p.y)
        for m in self.markers:
            m.update(p.x, p.y, t)

        if "floor" in events:
            self.bubbles.spawn(p.x, p.y, p.z - 0.3, count=10, spread=0.5)
        self.bubbles.update(dt, t, p.y - self.cam_dist)

        # camera zoom (A/Z)
        self.cam_dist = max(config.CAM_DIST_MIN, min(config.CAM_DIST_MAX,
                                                     self.cam_dist + zoom * config.CAM_ZOOM_SPEED * dt))
        # The fish leads the camera slightly in the direction it swims (the scene
        # slides the other way).  The lead builds quickly but relaxes slowly once
        # you stop, so the fish never appears to spring back.
        target = max(-config.CAM_LEAD_MAX, min(config.CAM_LEAD_MAX, p.vx * config.CAM_LEAD))
        growing = abs(target) > abs(self.lead) or target * self.lead < 0
        rate = 4.0 if growing else config.CAM_LEAD_RELAX
        self.lead += (target - self.lead) * min(1.0, rate * dt)
        self.cam_x = p.x - self.lead

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
        takes priority if both cannot fit, e.g. when zoomed right in)."""
        p = self.player
        d = self.cam_dist
        H = config.WORLD_H
        vf = math.radians(config.CAM_VFOV)
        aspect = self.base.getAspectRatio()
        hf = 2 * math.atan(math.tan(vf / 2) * aspect)
        self.base.camLens.setFov(math.degrees(hf), math.degrees(vf))

        cam_z = max(0.8, min(H - 0.4, p.z * 0.5 + 1.0 + d * 0.15))
        T = math.tan(vf / 2)
        top_ndc = 1 - 2 * self.top_cover - 0.06     # just below the wave band
        bot_ndc = -1 + 0.08                         # just above the bottom edge
        a_fish = math.atan2(p.z + config.FISH_SIZE * 0.5 - cam_z, d)
        a_shadow = math.atan2(-cam_z, d + 0.6)
        lo = a_fish - math.atan(top_ndc * T)        # tilt needed to keep the fish in view
        hi = a_shadow - math.atan(bot_ndc * T)      # tilt needed to keep the shadow in view
        target = max(lo, min(math.radians(-9), hi)) if lo <= hi else lo
        self.pitch += (target - self.pitch) * min(1.0, dt * 5)

        sx = sz = 0.0
        if self.shake > 0:
            self.shake = max(0.0, self.shake - dt)
            sx = math.sin(self.time * 71) * self.shake * 0.5
            sz = math.cos(self.time * 57) * self.shake * 0.4
        cam = self.base.camera
        cam.setPos(self.cam_x + sx, p.y - d, cam_z + sz)
        cam.setHpr(0, math.degrees(self.pitch), 0)

    def destroy(self):
        self.end_run()
        for m in self.markers:
            m.remove()
        self.aim.destroy()
        self.bubbles.destroy()
        self.player.destroy()
        self.env.destroy()
        self.root.removeNode()
