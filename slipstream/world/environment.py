"""Static surroundings: sea floor, side cliffs, the surface from below,
parallax background silhouettes, fog and light shafts."""

import math
import random

from panda3d.core import (CardMaker, ColorBlendAttrib, Fog, Mat4, TexGenAttrib,
                          TextureStage, TransformState)

from .. import config
from .common import card

FLOOR_LEN = 170.0
FLOOR_BACK = 30.0


def _world_texgen(np_, stage, mat):
    np_.setTexGen(stage, TexGenAttrib.M_world_position)
    np_.setTexTransform(stage, TransformState.makeMat(mat))


def _uv_mat(u_axis, v_axis, su, sv, ou=0.0, ov=0.0):
    """Matrix mapping world xyz -> uv using the given axes (0=x,1=y,2=z)."""
    rows = [[0.0] * 4 for _ in range(4)]
    rows[u_axis][0] = su
    rows[v_axis][1] = sv
    rows[3] = [ou, ov, 0.0, 1.0]
    return Mat4(*[v for r in rows for v in r])


class Environment:
    def __init__(self, base, res, theme):
        self.base = base
        self.theme = theme
        self.root = base.render.attachNewNode("environment")
        W = config.HALF_W
        H = config.WORLD_H

        # --- fog & background colour ----------------------------------
        self.fog = Fog("water")
        self.fog.setColor(*theme.water)
        self.fog.setLinearRange(config.FOG_NEAR, config.FOG_FAR)
        base.render.setFog(self.fog)
        base.setBackgroundColor(*theme.water, 1)

        # --- sea floor ----------------------------------------------------
        self.follow = self.root.attachNewNode("follow")   # moves with the camera's y
        cm = CardMaker("floor")
        cm.setFrame(-W - 6, W + 6, -FLOOR_BACK, FLOOR_LEN)
        self.floor = self.follow.attachNewNode(cm.generate())
        self.floor.setP(-90)
        self.floor.setTexture(res.texture("textures", f"floor_{theme.floor}.png", wrap=True))
        _world_texgen(self.floor, TextureStage.getDefault(), _uv_mat(0, 1, 1 / 9.0, 1 / 9.0))
        self.caustic_stage = TextureStage("caustics")
        self.caustic_stage.setMode(TextureStage.M_add)
        self.floor.setTexture(self.caustic_stage, res.texture("fx", "caustics.png", wrap=True))
        self.floor.setLightOff()

        # --- side cliffs (the ends of every wall are buried in these) --------
        cliff_tex = res.texture("textures", f"cliff_{theme.cliff}.png", wrap=True)
        self.cliffs = []
        for side in (-1, 1):
            cm = CardMaker("cliff")
            cm.setFrame(-FLOOR_BACK, FLOOR_LEN, -0.5, H + 0.5)
            c = self.follow.attachNewNode(cm.generate())
            c.setH(90)
            c.setX(side * (W + 0.6))
            c.setTwoSided(True)
            c.setTexture(cliff_tex)
            _world_texgen(c, TextureStage.getDefault(), _uv_mat(1, 2, 1 / 16.0, 1 / H))
            c.setColorScale(0.85, 0.85, 0.85, 1)
            c.setLightOff()
            self.cliffs.append(c)

        # --- underside of the surface --------------------------------------
        cm = CardMaker("surface")
        cm.setFrame(-W - 6, W + 6, -FLOOR_BACK, FLOOR_LEN)
        self.surface = self.follow.attachNewNode(cm.generate())
        self.surface.setP(90)
        self.surface.setZ(H)
        self.surface.setTwoSided(True)
        self.surface.setTexture(res.texture("textures", "surface.png", wrap=True))
        self.surface.setColorScale(*theme.surface, 1)
        self.surface.setLightOff()

        # --- parallax background silhouettes ---------------------------------
        # Three layers far ahead; nearer layers shift more with the camera.
        self.bg_root = self.root.attachNewNode("bg")
        self.layers = []
        specs = [("far", 0.08, 230, 70, 0), ("mid", 0.2, 215, 42, 1), ("near", 0.38, 200, 26, 2)]
        for i, (name, parallax, dist, height, order) in enumerate(specs):
            tex = res.texture("bg", f"{name}.png", wrap=True)
            width = 700.0
            c = card(self.bg_root, tex, width, height, anchor="bottom", name=f"bg_{name}")
            c.setPos(0, dist, -2)
            c.setColor(*theme.bg_tints[i], 1)
            c.setFogOff()
            c.setBin("background", 10 + order)
            c.setDepthWrite(False)
            c.setDepthTest(False)
            c.setTexScale(TextureStage.getDefault(), width / 260.0, 1)
            self.layers.append((c, parallax, width))

        # --- light shafts ----------------------------------------------------
        ray_tex = res.texture("fx", "light_ray.png")
        self.rays = []
        for i in range(10):
            r = card(self.root, ray_tex, random.uniform(2, 5), H * 1.4, anchor="bottom")
            r.setZ(-H * 0.25)
            r.setDepthWrite(False)
            r.setBin("fixed", 5)
            r.setFogOff()
            r.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_incoming_alpha,
                                              ColorBlendAttrib.O_one))
            r.setColor(*theme.surface, 0.18)
            r.setBillboardAxis()
            self.rays.append([r, random.uniform(-W, W), random.uniform(0, 160), random.uniform(0, 6)])

        # --- floor decorations (scenery only, recycled ahead of the player) ---
        self.decor_tex = [res.texture("decor", f"{n}.png") for n in theme.decor]
        self.decor = []
        for i in range(70):
            np_ = card(self.root, None, 1, 1, anchor="bottom")
            np_.setBillboardAxis()
            np_.setDepthWrite(False)
            item = [np_, 0.0, 0.0]
            self._place_decor(item, random.uniform(-10, 160))
            self.decor.append(item)

    def _place_decor(self, item, y):
        np_ = item[0]
        x = random.uniform(-config.HALF_W + 0.5, config.HALF_W - 0.5)
        s = random.uniform(0.8, 2.2)
        np_.setTexture(random.choice(self.decor_tex), 1)
        np_.setScale(s)
        np_.setPos(x, y, -0.05)
        item[1], item[2] = x, y

    def update(self, cam_x, cam_y, follow_y, t):
        for item in self.decor:
            if item[2] < cam_y - 3:
                self._place_decor(item, item[2] + 165 + random.uniform(0, 10))
        self.follow.setY(follow_y)
        # animated caustics on the floor (texture transform in world space)
        ox = math.sin(t * 0.3) * 0.15
        oy = t * 0.03
        _world_texgen(self.floor, self.caustic_stage, _uv_mat(0, 1, 1 / 13.0, 1 / 13.0, ox, oy))
        _world_texgen(self.surface, TextureStage.getDefault(),
                      _uv_mat(0, 1, 1 / 14.0, 1 / 14.0, t * 0.02, math.sin(t * 0.25) * 0.1))
        # background follows the camera, scrolling in parallax
        self.bg_root.setPos(cam_x, cam_y, 0)
        for c, parallax, width in self.layers:
            c.setTexOffset(TextureStage.getDefault(), (cam_x * parallax) / 260.0, 0)
        # light shafts recycle ahead of the player
        for ray in self.rays:
            np_, x, y, ph = ray
            if y < cam_y - 5:
                ray[2] = y = cam_y + random.uniform(120, 170)
                ray[1] = x = random.uniform(-config.HALF_W, config.HALF_W)
            np_.setPos(x + math.sin(t * 0.4 + ph) * 1.5, y, -config.WORLD_H * 0.25)
            np_.setAlphaScale(0.6 + 0.4 * math.sin(t * 0.7 + ph))

    def destroy(self):
        self.base.render.clearFog()
        self.root.removeNode()
