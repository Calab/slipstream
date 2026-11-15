"""Small scene-graph helpers shared by world objects."""

from panda3d.core import CardMaker, TransparencyAttrib, NodePath

from .. import config
from .terrain import floor_height


def card(parent, tex, w, h, anchor="center", name="card", transparency=TransparencyAttrib.M_alpha):
    """A vertical textured card in the XZ plane facing -Y (towards the camera).

    Nearly everything in the game - fish, obstacles, walls, bubbles - is one
    of these flat picture rectangles ("cards") rather than a 3D model.
    anchor says where the card's origin is: its centre, bottom edge (things
    standing on the floor) or top edge (things hanging from the surface).
    Cards are unlit (setLightOff) so their colours show exactly as drawn.
    """
    cm = CardMaker(name)
    if anchor == "bottom":
        cm.setFrame(-w / 2, w / 2, 0, h)
    elif anchor == "top":            # hangs down from its origin
        cm.setFrame(-w / 2, w / 2, -h, 0)
    else:
        cm.setFrame(-w / 2, w / 2, -h / 2, h / 2)
    np_ = parent.attachNewNode(cm.generate())
    if tex is not None:
        np_.setTexture(tex)
    np_.setTransparency(transparency)
    np_.setTwoSided(True)
    np_.setLightOff()
    return np_


def flat_card(parent, tex, w, h, name="flat"):
    """A horizontal card lying in the XY plane (for shadows)."""
    cm = CardMaker(name)
    cm.setFrame(-w / 2, w / 2, -h / 2, h / 2)
    np_ = parent.attachNewNode(cm.generate())
    np_.setP(-90)
    if tex is not None:
        np_.setTexture(tex)
    np_.setTwoSided(True)
    np_.setLightOff()
    return np_


class Shadow:
    """Dark blob on the sea floor beneath an object; smaller and fainter when high."""

    def __init__(self, parent, tex, base_size):
        self.np = flat_card(parent, tex, 1, 1, "shadow")
        self.np.setTransparency(TransparencyAttrib.M_alpha)
        self.np.setDepthWrite(False)
        self.np.setDepthOffset(2)      # drawn as if nearer, so it doesn't flicker into the sand
        self.np.setBin("fixed", 0)
        self.base_size = base_size

    def update(self, x, y, z):
        """Place the shadow under an object at (x, y, z)."""
        h = max(0.0, min(1.0, z / config.WORLD_H))     # 0 at the floor, 1 at the surface
        s = self.base_size * (1.25 - 0.85 * h)
        self.np.setPos(x, y, float(floor_height(x, y)) + 0.08)   # rests on the dunes
        self.np.setScale(s, s * 0.75, 1)
        self.np.setColor(0, 0, 0, 0.8 * (1.0 - 0.5 * h))

    def remove(self):
        self.np.removeNode()


def remove(np_: NodePath):
    """Remove a node from the scene, if it is still there."""
    if np_ is not None and not np_.isEmpty():
        np_.removeNode()
