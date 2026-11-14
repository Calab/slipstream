"""On-screen buttons for tablets and phones (also usable with a mouse)."""

from direct.gui.DirectGui import DirectButton, DGG, OnscreenImage
from panda3d.core import TextNode, TransparencyAttrib


class TouchControls:
    """Hold-to-press buttons that feed the same key-state dict as the keyboard."""

    def __init__(self, base, res, keys, on_pause):
        self.keys = keys
        self.arrow = res.texture("fx", "arrow.png")
        self.buttons = []
        bl, br, tr = base.a2dBottomLeft, base.a2dBottomRight, base.a2dTopRight
        s = 0.11
        pad = [("arrow_up", 0, (0.33, 0, 0.5)), ("arrow_down", 180, (0.33, 0, 0.16)),
               ("arrow_left", -90, (0.16, 0, 0.33)), ("arrow_right", 90, (0.50, 0, 0.33))]
        for key, roll, pos in pad:
            b = self._hold(bl, key, "", pos, s)
            img = OnscreenImage(parent=b, image=self.arrow, scale=0.9, pos=(0, 0, 0.2))
            img.setR(roll)
            img.setTransparency(TransparencyAttrib.M_alpha)
        self._hold(br, "a", "A", (-0.40, 0, 0.18), s * 0.95)
        self._hold(br, "z", "Z", (-0.16, 0, 0.18), s * 0.95)
        b = DirectButton(parent=tr, text="II", scale=0.06, pos=(-0.08, 0, -0.33), command=on_pause,
                         frameColor=(0.1, 0.3, 0.45, 0.6), relief=DGG.FLAT, text_fg=(1, 1, 1, 0.9),
                         frameSize=(-0.9, 0.9, -0.6, 1.1))
        self.buttons.append(b)
        self.hide()

    def _hold(self, parent, key, label, pos, size):
        b = DirectButton(parent=parent, text=label, pos=pos, scale=size * 0.42, text_scale=1.6,
                         text_fg=(1, 1, 1, 0.95), text_align=TextNode.ACenter,
                         frameColor=(0.1, 0.35, 0.5, 0.55), relief=DGG.FLAT,
                         frameSize=(-1.9, 1.9, -1.6, 2.0), rolloverSound=None, clickSound=None)
        b.bind(DGG.B1PRESS, lambda _e, k=key: self.keys.__setitem__(k, True))
        b.bind(DGG.B1RELEASE, lambda _e, k=key: self.keys.__setitem__(k, False))
        self.buttons.append(b)
        return b

    def show(self):
        for b in self.buttons:
            b.show()

    def hide(self):
        for b in self.buttons:
            b.hide()
