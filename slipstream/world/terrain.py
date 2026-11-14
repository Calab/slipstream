"""Relief meshes for the sea floor and the side cliffs.

The surface shape repeats every PERIOD units along the course (y), so a mesh
can follow the player by jumping in whole periods without anything visibly
shifting.  Textures are mapped in world space (see environment.py), so they
don't repeat with the shape.
"""

import math

import numpy as np
from panda3d.core import (Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat)

from .. import config

PERIOD = 32.0
K = 2 * math.pi / PERIOD
W = config.HALF_W


def floor_height(x, y):
    """Height of the sea floor (works on floats or numpy arrays).

    Gentle dunes and ripples between 0 and ~0.27, rising into sand banks
    beyond the swimmable area where the floor meets the cliffs.
    """
    h = (0.12 + 0.07 * np.sin(3 * K * y + 0.35 * x)
         + 0.05 * np.sin(2 * K * y - 0.22 * x + 1.3)
         + 0.025 * np.sin(11 * K * y + 0.9 * x))
    t = np.clip((np.abs(x) - (W - 1.0)) / 5.0, 0.0, 1.0)
    h = h + 1.3 * t * t * (3 - 2 * t)
    return np.maximum(h, 0.0)


def cliff_offset(y, z):
    """How far the cliff face bulges out (+) or in (-) from its base plane."""
    d = (0.45 + 0.42 * np.sin(2 * K * y + 0.8 * z)
         + 0.26 * np.sin(5 * K * y - 1.4 * z + 0.7)
         + 0.12 * np.sin(13 * K * y + 3.1 * z))
    return np.clip(d, -0.35, 1.2)


def grid_mesh(name, P, facing):
    """Build a lit triangle mesh from a (rows, cols, 3) grid of positions.

    facing is a vector the normals should point towards (e.g. up for the
    floor), used to orient the triangles and normals consistently.
    """
    rows, cols, _ = P.shape
    du = np.gradient(P, axis=1)
    dv = np.gradient(P, axis=0)
    N = np.cross(du, dv)
    N /= np.linalg.norm(N, axis=2, keepdims=True) + 1e-9
    flip = np.sum(N * np.asarray(facing, dtype=np.float64), axis=2).mean() < 0
    if flip:
        N = -N
    verts = np.concatenate([P, N], axis=2).reshape(-1, 6).astype(np.float32)

    vdata = GeomVertexData(name, GeomVertexFormat.getV3n3(), Geom.UH_static)
    vdata.uncleanSetNumRows(len(verts))
    memoryview(vdata.modifyArray(0)).cast("B")[:] = verts.tobytes()

    r, c = np.mgrid[0:rows - 1, 0:cols - 1]
    i0 = (r * cols + c).ravel()
    i1, i2, i3 = i0 + 1, i0 + cols, i0 + cols + 1
    # counter-clockwise when seen from the side the normals point to
    if flip:
        tri = np.stack([i0, i2, i1, i1, i2, i3], axis=1)
    else:
        tri = np.stack([i0, i1, i2, i1, i3, i2], axis=1)
    tris = GeomTriangles(Geom.UH_static)
    tris.setIndexType(Geom.NT_uint32)
    arr = tris.modifyVertices()
    arr.uncleanSetNumRows(tri.size)
    memoryview(arr).cast("B")[:] = tri.astype(np.uint32).tobytes()

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode(name)
    node.addGeom(geom)
    return node


def floor_mesh(y0, y1, step=0.6):
    xs = np.arange(-W - 6, W + 6 + step / 2, step)
    ys = np.arange(y0, y1 + step / 2, step)
    X, Y = np.meshgrid(xs, ys)
    Z = floor_height(X, Y)
    return grid_mesh("floor", np.dstack([X, Y, Z]), facing=(0, 0, 1))


def cliff_mesh(side, y0, y1, trench=None, y_offset=0.0, step=0.6):
    """Cliff face for local y in [y0, y1]; the trench drift is looked up at
    world distance y + y_offset (the mesh's parent sits at y_offset)."""
    ys = np.arange(y0, y1 + step / 2, step)
    zs = np.arange(-0.5, config.WORLD_H + 0.75, 0.5)
    Y, Zg = np.meshgrid(ys, zs)
    inset = trench.inset(Y + y_offset, side) if trench is not None else 0.0
    # rocky bulges out and in around the (drifting) cliff line
    X = side * (W + 0.6 + cliff_offset(Y, Zg) - inset)
    return grid_mesh("cliff", np.dstack([X, Y, Zg]), facing=(-side, 0, 0))
