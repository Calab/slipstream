"""Static surroundings: sea floor, side cliffs, parallax background
silhouettes, fog and light shafts."""

import math
import random

from panda3d.core import (AmbientLight, ColorBlendAttrib, DirectionalLight, Fog, Mat4,
                          TexGenAttrib, TextureStage, TransformState)

from .. import config
from .common import card
from .terrain import PERIOD, cliff_mesh, floor_height, floor_mesh
from .trench import STRAIGHT

FLOOR_LEN = 215.0     # floor/cliff meshes reach this far ahead of the player...
FLOOR_BACK = 30.0     # ...and this far behind
DECOR_COUNT = 190     # number of scenery plants kept in the scene at once

# decor name prefix -> (min, max) height in world units
DECOR_SIZE = {
    "weed": (1.4, 3.4), "coral": (1.3, 3.2), "fan": (1.6, 3.4), "brain": (0.9, 1.9),
    "sponge": (1.3, 2.8), "anemone": (0.9, 1.9), "kelp": (3.5, 6.5), "grass": (0.9, 1.8),
}


def _world_texgen(np_, stage, mat):
    """Texture `np_` by world position instead of the mesh's own texture
    coordinates.  The floor and cliff meshes move along with the player, but
    with this their textures stay fixed in the world (no sliding)."""
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
    """The scenery: everything that is just there to look at."""

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

        # --- lighting for the relief of the floor and cliffs -------------------
        amb = AmbientLight("ambient")
        amb.setColor((0.6, 0.6, 0.6, 1))
        self.amb = self.root.attachNewNode(amb)
        sun = DirectionalLight("sun")
        sun.setColor((0.62, 0.62, 0.6, 1))
        self.sun = self.root.attachNewNode(sun)
        self.sun.setHpr(25, -50, 0)     # from above, slightly from one side

        # --- sea floor (dunes and ripples) ----------------------------------
        # The follow node jumps forward in whole terrain periods so the relief
        # stays put in the world while the meshes travel with the player.
        self.follow = self.root.attachNewNode("follow")
        self.floor = self.follow.attachNewNode(floor_mesh(-FLOOR_BACK, FLOOR_LEN))
        self.floor.setTexture(res.texture("textures", f"floor_{theme.floor}.png", wrap=True))
        # sand texture repeats every 9 units
        _world_texgen(self.floor, TextureStage.getDefault(), _uv_mat(0, 1, 1 / 9.0, 1 / 9.0))
        # a second texture layer: rippling light patterns ("caustics"), added
        # on top of the sand and slowly scrolled in update()
        self.caustic_stage = TextureStage("caustics")
        self.caustic_stage.setMode(TextureStage.M_add)
        self.floor.setTexture(self.caustic_stage, res.texture("fx", "caustics.png", wrap=True))
        self.floor.setLight(self.amb)
        self.floor.setLight(self.sun)

        # --- side cliffs (the ends of every wall are buried in these) --------
        cliff_tex = res.texture("textures", f"cliff_{theme.cliff}.png", wrap=True)
        self.cliffs = []
        for side in (-1, 1):
            # holder carries texture/lighting; its mesh is rebuilt as the trench drifts
            c = self.follow.attachNewNode(f"cliff{side}")
            c.setPythonTag("side", side)
            c.setTexture(cliff_tex)
            _world_texgen(c, TextureStage.getDefault(), _uv_mat(1, 2, 1 / 16.0, 1 / H))
            c.setColorScale(0.9, 0.9, 0.9, 1)
            c.setLight(self.amb)
            c.setLight(self.sun)
            self.cliffs.append(c)
        self.trench = STRAIGHT
        self.snap_y = None

        # --- parallax background silhouettes ---------------------------------
        # Three layers far ahead; nearer layers shift more with the camera.
        self.bg_root = self.root.attachNewNode("bg")
        self.layers = []
        # (layer, parallax factor, distance ahead, height, draw order)
        specs = [("far", 0.08, 275, 84, 0), ("mid", 0.2, 258, 50, 1), ("near", 0.38, 240, 31, 2)]
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
            # [node, x, y, phase]
            self.rays.append([r, random.uniform(-W, W), random.uniform(0, 205), random.uniform(0, 6)])

        # --- floor decorations (scenery only, recycled ahead of the player) ---
        self.decor_tex = [res.texture("decor", f"{n}.png") for n in theme.decor]
        self.decor = []
        self.decor_names = list(theme.decor)
        # scenery is tinted towards the water colour so it recedes into the
        # background and can't be mistaken for an obstacle
        wmax = max(theme.water)
        self.decor_tint = tuple(0.72 * (0.35 + 0.65 * c / wmax) for c in theme.water) + (1.0,)
        for i in range(DECOR_COUNT):
            np_ = card(self.root, None, 1, 1, anchor="bottom")
            np_.setBillboardAxis()
            np_.setDepthWrite(False)
            item = [np_, 0.0, 0.0]          # [node, x, y]
            self._place_decor(item, random.uniform(-10, 200))
            self.decor.append(item)

    def _place_decor(self, item, y):
        """Give a scenery item a random plant picture, size and x at distance y."""
        np_ = item[0]
        i = random.randrange(len(self.decor_tex))
        name = self.decor_names[i]
        lo, hi = next((v for k, v in DECOR_SIZE.items() if name.startswith(k)), (1.2, 2.6))
        s = random.uniform(lo, hi)
        if s > 3.0 and random.random() < 0.7:
            # tall plants mostly grow towards the sides, keeping the middle clearer
            side = random.choice((-1, 1))
            x = side * random.uniform(8, config.HALF_W + 0.5 - self.trench.inset(y, side))
        else:
            lo, hi = self.trench.bounds(y, -0.5)
            x = random.uniform(lo, hi)
        np_.setTexture(self.decor_tex[i], 1)
        np_.setColorScale(*self.decor_tint)
        np_.setScale(s * random.choice((-1, 1)), 1, s)    # random mirror for variety
        np_.setPos(x, y, float(floor_height(x, y)) - 0.08)
        item[1], item[2] = x, y

    def update(self, cam_x, cam_y, follow_y, t):
        """Per-frame scenery update.  cam_x/cam_y: camera position;
        follow_y: the player's distance (the floor/cliffs follow it)."""
        # plants that drop behind the camera are recycled ~210 units ahead
        for item in self.decor:
            if item[2] < cam_y - 3:
                self._place_decor(item, item[2] + 210 + random.uniform(0, 10))
        # The floor and cliffs move forward in whole PERIODs (the relief repeats
        # every PERIOD, so the jump is invisible).  The cliff meshes are rebuilt
        # at each jump because the trench's drift does not repeat.
        snap = math.floor(follow_y / PERIOD) * PERIOD
        if snap != self.snap_y:
            self.snap_y = snap
            self.follow.setY(snap)
            self._build_cliffs()
        # animated caustics on the floor (texture transform in world space)
        ox = math.sin(t * 0.3) * 0.15
        oy = t * 0.03
        _world_texgen(self.floor, self.caustic_stage, _uv_mat(0, 1, 1 / 13.0, 1 / 13.0, ox, oy))
        # background follows the camera, scrolling in parallax
        self.bg_root.setPos(cam_x, cam_y, 0)
        for c, parallax, width in self.layers:
            c.setTexOffset(TextureStage.getDefault(), (cam_x * parallax) / 260.0, 0)
        # light shafts recycle ahead of the player
        for ray in self.rays:
            np_, x, y, ph = ray
            if y < cam_y - 5:
                ray[2] = y = cam_y + random.uniform(160, 210)
                ray[1] = x = random.uniform(-config.HALF_W, config.HALF_W)
            np_.setPos(x + math.sin(t * 0.4 + ph) * 1.5, y, -config.WORLD_H * 0.25)
            np_.setAlphaScale(0.6 + 0.4 * math.sin(t * 0.7 + ph))

    def set_trench(self, trench):
        """Use a new trench shape (each run gets its own)."""
        self.trench = trench
        self.snap_y = None          # forces the cliffs to be rebuilt next update
        for item in self.decor:
            self._place_decor(item, item[2])

    def _build_cliffs(self):
        """Replace both cliff meshes with new ones for the current snap_y."""
        for holder in self.cliffs:
            holder.getChildren().detach()
            side = holder.getPythonTag("side")
            holder.attachNewNode(cliff_mesh(side, -FLOOR_BACK, FLOOR_LEN, self.trench, self.snap_y))

    def destroy(self):
        """Remove all scenery and the fog."""
        self.base.render.clearFog()
        self.root.removeNode()
