"""The strip of sky and rolling waves at the top of the screen, with a bobbing
boat that depends on the theme."""

import math

from panda3d.core import CardMaker, SamplerState, TextureStage, TransparencyAttrib

from .hud import BAR_H

BAND_H = 0.21
HALF = 3.0       # half width in aspect2d units (covers ultra-wide windows)


class SurfaceBand:
    def __init__(self, base, res):
        self.base = base
        self.res = res
        self.root = base.a2dTopCenter.attachNewNode("band")
        self.root.setZ(-BAR_H)
        self.root.setBin("fixed", -20)
        self.root.setDepthWrite(False)
        self.root.setDepthTest(False)
        self.root.setTransparency(TransparencyAttrib.M_alpha)
        self.parts = []

    def _card(self, tex, x0, x1, z0, z1, sort, tile=None):
        cm = CardMaker("bandcard")
        cm.setFrame(x0, x1, z0, z1)
        c = self.root.attachNewNode(cm.generate())
        c.setTexture(tex)
        c.setBin("fixed", sort)
        if tile:
            c.setTexScale(TextureStage.getDefault(), tile, 1)
        self.parts.append(c)
        return c

    def set_theme(self, theme):
        for p in self.parts:
            p.removeNode()
        self.parts = []
        self.theme = theme
        r = self.res
        self.sky = self._card(r.texture("band", f"{theme.key}_sky.png"), -HALF, HALF, -BAND_H, 0, -20)
        waves = [r.texture("band", f"{theme.key}_wave{i}.png", wrap=True) for i in range(3)]
        for w in waves:
            w.setWrapV(SamplerState.WM_clamp)
        # back wave, boat, two front waves
        self.w_back = self._card(waves[0], -HALF, HALF, -BAND_H, -BAND_H + 0.12, -19, tile=4.5)
        self.boat = self._card(r.texture("boats", f"{theme.boat}.png"), -0.13, 0.13, -0.05, 0.11, -18)
        self.boat_holder_z = -BAND_H + 0.085
        self.w_mid = self._card(waves[1], -HALF, HALF, -BAND_H, -BAND_H + 0.09, -17, tile=6)
        self.w_front = self._card(waves[2], -HALF, HALF, -BAND_H - 0.005, -BAND_H + 0.06, -16, tile=8)

    def update(self, t, cam_x):
        ts = TextureStage.getDefault()
        self.w_back.setTexOffset(ts, cam_x * 0.004 + t * 0.010, 0)
        self.w_mid.setTexOffset(ts, cam_x * 0.007 - t * 0.016, 0)
        self.w_front.setTexOffset(ts, cam_x * 0.011 + t * 0.024, 0)
        # boat bobs and rocks; it drifts slowly against the player's moves
        bx = 0.55 * math.sin(t * 0.03) - cam_x * 0.012
        bx = (bx + 1.2) % 2.4 - 1.2
        self.boat.setPos(bx, 0, self.boat_holder_z + 0.012 * math.sin(t * 1.6))
        self.boat.setR(4.0 * math.sin(t * 1.1))

    def show(self):
        self.root.show()

    def hide(self):
        self.root.hide()
