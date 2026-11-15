"""Procedural material textures: sea floor, cliffs, water surface and walls.

The recipe is nearly always the same: make some smooth noise
(periodic_noise), maybe add patterns built from sine waves (ripples, strata,
planks), colour it with colormap(), then mix in patches of a second colour
where another noise is high (moss, algae, rust - using smoothstep as the
mask).  Working on whole numpy arrays at once keeps it fast.

Floor and cliff textures tile in both directions.  Wall materials tile
horizontally only.
"""

import numpy as np

from .common import periodic_noise, colormap, box_blur, smoothstep, to_image


# ---------------------------------------------------------------------------
# Sea floor (tileable)
# ---------------------------------------------------------------------------

def floor_sand(size=512, seed=1):
    """Pale sand with wind ripples and a scattering of pebbles."""
    n = periodic_noise(size, size, beta=2.4, seed=seed)
    fine = periodic_noise(size, size, beta=0.6, seed=seed + 1)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / size
    # wind ripples, distorted by noise; integer frequencies keep it tileable
    ripple = 0.5 + 0.5 * np.sin(2 * np.pi * (yy * 14 + xx * 2) + n * 9.0)
    v = 0.45 * n + 0.25 * ripple + 0.30 * fine
    rgb = colormap(v, [(0.0, (0.62, 0.52, 0.36)), (0.5, (0.83, 0.74, 0.55)),
                       (1.0, (0.96, 0.90, 0.72))])
    rgb = _scatter_pebbles(rgb, seed + 5, count=70, rmin=1.5, rmax=4,
                           palette=[(0.55, 0.47, 0.40), (0.9, 0.85, 0.8), (0.75, 0.55, 0.45)])
    return to_image(rgb)


def floor_gravel(size=512, seed=2):
    """Dark grey sea bed covered in pebbles (Shipwreck theme)."""
    n = periodic_noise(size, size, beta=2.0, seed=seed)
    rgb = colormap(n, [(0.0, (0.22, 0.22, 0.24)), (1.0, (0.42, 0.40, 0.38))])
    rgb = _scatter_pebbles(rgb, seed + 3, count=900, rmin=3, rmax=9,
                           palette=[(0.45, 0.44, 0.42), (0.55, 0.50, 0.45), (0.33, 0.33, 0.36),
                                    (0.62, 0.60, 0.55), (0.40, 0.33, 0.28)])
    return to_image(rgb)


def floor_mud(size=512, seed=3):
    """Brown mud with patches of green algae (Kelp theme)."""
    n = periodic_noise(size, size, beta=2.6, seed=seed)
    f = periodic_noise(size, size, beta=1.0, seed=seed + 1)
    v = 0.7 * n + 0.3 * f
    rgb = colormap(v, [(0.0, (0.17, 0.13, 0.08)), (0.55, (0.33, 0.27, 0.17)),
                       (1.0, (0.46, 0.42, 0.28))])
    # green algae patches
    a = periodic_noise(size, size, beta=3.0, seed=seed + 2)
    m = smoothstep(0.62, 0.75, a)[..., None]
    rgb = rgb * (1 - m * 0.6) + np.array([0.2, 0.33, 0.12]) * m * 0.6
    rgb = _scatter_pebbles(rgb, seed + 4, count=60, rmin=2, rmax=6,
                           palette=[(0.35, 0.32, 0.28), (0.5, 0.47, 0.4)])
    return to_image(rgb)


def _scatter_pebbles(rgb, seed, count, rmin, rmax, palette):
    """Paint `count` little shaded pebbles (radius rmin..rmax pixels, colours
    from palette) onto an image, wrapping around its edges so it still tiles."""
    h, w, _ = rgb.shape
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    out = rgb.copy()
    for _ in range(count):
        cx, cy = rng.uniform(0, w), rng.uniform(0, h)
        r = rng.uniform(rmin, rmax)
        col = np.array(palette[rng.integers(len(palette))], dtype=np.float32)
        col *= rng.uniform(0.85, 1.1)
        # wrap-around distance -> tileable
        dx = np.minimum(abs(xx - cx), w - abs(xx - cx))
        dy = np.minimum(abs(yy - cy), h - abs(yy - cy))
        d = np.sqrt(dx * dx + dy * dy * 1.3) / r
        m = d < 1
        if not m.any():
            continue
        shade = (1.15 - 0.45 * d[m])[:, None]
        out[m] = col * shade
        # tiny dark shadow under the pebble
        sm = (d > 1) & (d < 1.35)
        out[sm] *= 0.82
    return np.clip(out, 0, 1)


# ---------------------------------------------------------------------------
# Cliffs (tileable) and the water surface seen from below
# ---------------------------------------------------------------------------

def cliff_rock(kind, w=512, h=256, seed=10):
    """Layered rock for the side cliffs, with dark cracks and patches of moss.
    kind picks the colours: "reefrock", "kelprock" or "darkrock"."""
    n = periodic_noise(w, h, beta=2.2, seed=seed)
    f = periodic_noise(w, h, beta=1.0, seed=seed + 1)
    yy = np.mgrid[0:h, 0:w][0].astype(np.float32) / h
    strata = 0.5 + 0.5 * np.sin(2 * np.pi * (yy * 9) + n * 6)
    v = 0.5 * n + 0.25 * f + 0.25 * strata
    if kind == "reefrock":
        stops = [(0, (0.30, 0.25, 0.22)), (0.5, (0.55, 0.45, 0.38)), (1, (0.78, 0.66, 0.55))]
        moss = (0.65, 0.35, 0.45)
    elif kind == "kelprock":
        stops = [(0, (0.15, 0.17, 0.12)), (0.5, (0.32, 0.34, 0.26)), (1, (0.52, 0.52, 0.40))]
        moss = (0.20, 0.42, 0.15)
    else:
        stops = [(0, (0.10, 0.11, 0.14)), (0.5, (0.24, 0.25, 0.29)), (1, (0.42, 0.42, 0.45))]
        moss = (0.25, 0.32, 0.25)
    rgb = colormap(v, stops)
    # "ridge" trick: 1 - |2n - 1| is 1 along the lines where noise n passes
    # 0.5, giving thin wandering lines - used here as cracks
    ridge = 1 - np.abs(periodic_noise(w, h, beta=1.8, seed=seed + 2) * 2 - 1)
    rgb *= (1 - 0.5 * smoothstep(0.93, 0.99, ridge))[..., None]
    m = smoothstep(0.6, 0.72, periodic_noise(w, h, beta=2.6, seed=seed + 3))[..., None]
    rgb = rgb * (1 - m * 0.55) + np.array(moss) * m * 0.55
    return to_image(rgb)


def surface_caustics(size=256, seed=20):
    """The underside of the water surface: light blue with bright ripple lines."""
    n = periodic_noise(size, size, beta=2.2, seed=seed)
    ridge = 1 - np.abs(n * 2 - 1)
    n2 = periodic_noise(size, size, beta=2.0, seed=seed + 1)
    ridge2 = 1 - np.abs(n2 * 2 - 1)
    v = np.maximum(ridge ** 6, ridge2 ** 8)
    rgb = np.dstack([0.55 + 0.45 * v, 0.75 + 0.25 * v, 0.85 + 0.15 * v])
    return to_image(rgb)


def caustic_overlay(size=256, seed=30):
    """White caustic network with alpha, projected softly on the floor."""
    n = periodic_noise(size, size, beta=2.0, seed=seed)
    ridge = (1 - np.abs(n * 2 - 1)) ** 10
    # used with additive blending, so the brightness lives in RGB
    rgb = np.repeat((ridge * 0.38)[..., None], 3, axis=2)
    return to_image(rgb)


def light_ray(w=64, h=256):
    """A soft vertical shaft of light (for god rays)."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    x = (xx / (w - 1)) * 2 - 1
    y = yy / (h - 1)
    a = (1 - np.abs(x)) ** 2 * (1 - y) ** 1.5 * 0.5
    return to_image(np.ones((h, w, 3)), a)


# ---------------------------------------------------------------------------
# Wall materials (tileable horizontally so they can be rolled for variety)
# ---------------------------------------------------------------------------

# Each wall material function returns a float RGB array (h, w, 3) in 0..1;
# wall_material_image() adds relief shading and turns it into an image.

def wall_coral(w, h, seed):
    """Pink/orange coral with purple and yellow patches and dotted polyps."""
    n = periodic_noise(w, h, beta=2.3, seed=seed)
    f = periodic_noise(w, h, beta=1.0, seed=seed + 1)
    rgb = colormap(n, [(0.0, (0.45, 0.10, 0.30)), (0.35, (0.85, 0.30, 0.35)),
                       (0.65, (1.00, 0.55, 0.30)), (1.0, (1.00, 0.78, 0.62))])
    # patches of other coral species
    p = periodic_noise(w, h, beta=3.0, seed=seed + 2)
    m1 = smoothstep(0.62, 0.70, p)[..., None]
    rgb = rgb * (1 - m1) + colormap(f, [(0, (0.35, 0.18, 0.55)), (1, (0.75, 0.55, 0.95))]) * m1
    m2 = smoothstep(0.30, 0.22, p)[..., None]
    rgb = rgb * (1 - m2) + colormap(f, [(0, (0.70, 0.55, 0.10)), (1, (1.0, 0.92, 0.45))]) * m2
    # polyps: bright dots on a distorted grid
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    g = np.sin((xx + 6 * f * 6) * 2 * np.pi / 9) * np.sin((yy + 6 * n * 6) * 2 * np.pi / 9)
    dots = smoothstep(0.75, 0.95, g)[..., None]
    rgb = rgb * (1 - dots * 0.5) + dots * 0.5 * np.array([1.0, 0.95, 0.85])
    crev = smoothstep(0.35, 0.15, f)[..., None]
    rgb *= 1 - 0.45 * crev
    return rgb


def wall_seaweed(w, h, seed):
    """Three layers of wavy vertical kelp strands, with round air bladders."""
    rng = np.random.default_rng(seed)
    n = periodic_noise(w, h, beta=2.5, seed=seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    rgb = np.zeros((h, w, 3), dtype=np.float32) + np.array([0.04, 0.16, 0.07])
    for layer, (period, amp, bright) in enumerate([(13, 9, 0.6), (9, 6, 0.85), (7, 4, 1.0)]):
        phase = rng.uniform(0, 6.28)
        u = xx + amp * np.sin(yy / (18 + layer * 5) + phase) + n * 14
        s = 0.5 + 0.5 * np.sin(u * 2 * np.pi / period)
        strand = smoothstep(0.55, 0.9, s)
        hue = periodic_noise(w, h, beta=3.0, seed=seed + 10 + layer)
        col = colormap(hue, [(0, (0.10, 0.40, 0.12)), (0.5, (0.30, 0.62, 0.18)),
                             (0.8, (0.50, 0.55, 0.15)), (1, (0.55, 0.42, 0.12))]) * bright
        rgb = rgb * (1 - strand[..., None]) + col * strand[..., None]
    # midrib highlights
    hl = smoothstep(0.96, 1.0, 0.5 + 0.5 * np.sin((xx + n * 14) * 2 * np.pi / 7))
    rgb += hl[..., None] * np.array([0.12, 0.2, 0.05])
    # air bladders (kelp floats)
    for _ in range(int(w * h / 1400)):
        cx, cy, r = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(2.0, 3.8)
        x0, x1 = int(max(cx - r - 1, 0)), int(min(cx + r + 2, w))
        y0, y1 = int(max(cy - r - 1, 0)), int(min(cy + r + 2, h))
        d = np.hypot(xx[y0:y1, x0:x1] - cx, yy[y0:y1, x0:x1] - cy) / r
        m = d < 1
        rgb[y0:y1, x0:x1][m] = np.array([0.60, 0.55, 0.18]) * (1.2 - 0.5 * d[m])[:, None]
    return np.clip(rgb, 0, 1)


def wall_ship(w, h, seed):
    """Wooden hull planks with seams, ribs, nails, algae, rust and portholes."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    plank_h = 18
    row = (yy // plank_h).astype(int)
    grain = periodic_noise(w // 8, h, beta=1.4, seed=seed)
    grain = np.repeat(grain, 8, axis=1)[:, :w]
    if grain.shape[1] < w:
        grain = np.pad(grain, ((0, 0), (0, w - grain.shape[1])), mode="wrap")
    tone = rng.uniform(0.75, 1.1, size=row.max() + 1)[row]
    rgb = colormap(grain, [(0, (0.25, 0.15, 0.08)), (0.5, (0.42, 0.27, 0.14)),
                           (1, (0.55, 0.38, 0.20))]) * tone[..., None]
    # plank seams and butt joints
    seam = (yy % plank_h) < 2
    rgb[seam] *= 0.35
    offs = rng.integers(0, 140, size=row.max() + 1)[row]
    joint = ((xx + offs) % 140) < 2
    rgb[joint] *= 0.4
    # ribs
    rib = (xx % 104) < 7
    rgb[rib] = rgb[rib] * 0.55 + np.array([0.12, 0.08, 0.05])
    # nails
    nail = (((xx + offs) % 140) - 8) ** 2 + ((yy % plank_h) - 9) ** 2 < 4
    rgb[nail] = np.array([0.55, 0.50, 0.42])
    # rust / algae / barnacles
    n = periodic_noise(w, h, beta=2.6, seed=seed + 1)
    m = smoothstep(0.58, 0.72, n)[..., None]
    rgb = rgb * (1 - m * 0.7) + np.array([0.22, 0.32, 0.18]) * m * 0.7
    m2 = smoothstep(0.3, 0.18, n)[..., None]
    rgb = rgb * (1 - m2 * 0.6) + np.array([0.55, 0.30, 0.12]) * m2 * 0.6
    barn = periodic_noise(w, h, beta=0.3, seed=seed + 2)
    rgb[barn > 0.82] = np.array([0.80, 0.78, 0.70])
    # decorative portholes (brass rings, dark glass) - purely visual
    for cx in range(60, w, 160):
        cy = h * rng.uniform(0.25, 0.4)
        d = np.hypot(xx - cx, yy - cy)
        rgb[(d < 15) & (d > 11)] = np.array([0.75, 0.6, 0.25])
        rgb[d <= 11] = np.array([0.04, 0.10, 0.14])
    return np.clip(rgb, 0, 1)


def wall_rock(w, h, seed):
    """Grey rock with cracks, moss and colourful sponges."""
    n = periodic_noise(w, h, beta=2.3, seed=seed)
    f = periodic_noise(w, h, beta=1.0, seed=seed + 1)
    rgb = colormap(0.65 * n + 0.35 * f, [(0, (0.15, 0.15, 0.17)), (0.5, (0.36, 0.34, 0.33)),
                                         (1, (0.62, 0.58, 0.52))])
    ridge = 1 - np.abs(periodic_noise(w, h, beta=1.9, seed=seed + 2) * 2 - 1)
    rgb *= (1 - 0.6 * smoothstep(0.92, 0.99, ridge))[..., None]
    m = smoothstep(0.6, 0.7, periodic_noise(w, h, beta=2.8, seed=seed + 3))[..., None]
    rgb = rgb * (1 - m * 0.6) + np.array([0.22, 0.40, 0.18]) * m * 0.6
    # sponges / anemones
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    for _ in range(int(w * h / 3000)):
        cx, cy, r = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(3, 7)
        col = np.array([(0.9, 0.5, 0.2), (0.9, 0.3, 0.5), (0.95, 0.85, 0.3)][rng.integers(3)])
        x0, x1 = int(max(cx - r - 1, 0)), int(min(cx + r + 2, w))
        y0, y1 = int(max(cy - r - 1, 0)), int(min(cy + r + 2, h))
        d = np.hypot(xx[y0:y1, x0:x1] - cx, yy[y0:y1, x0:x1] - cy) / r
        m = d < 1
        rgb[y0:y1, x0:x1][m] = col * (1.1 - 0.5 * d[m])[:, None]
    return np.clip(rgb, 0, 1)


# name used in themes.py -> generator
WALL_MATERIALS = {
    "coral": wall_coral,
    "seaweed": wall_seaweed,
    "ship": wall_ship,
    "rock": wall_rock,
}

FLOORS = {"sand": floor_sand, "gravel": floor_gravel, "mud": floor_mud}


def emboss(rgb, strength=3.5, radius=2):
    """Fake relief lighting (light from the upper left) using luminance as height."""
    hgt = box_blur(rgb.mean(axis=2), radius)
    dy = np.roll(hgt, 2, axis=0) - np.roll(hgt, -2, axis=0)
    dx = np.roll(hgt, 2, axis=1) - np.roll(hgt, -2, axis=1)
    shade = np.clip(1.0 - (dy * 0.8 + dx * 0.5) * strength, 0.55, 1.5)
    return np.clip(rgb * shade[..., None], 0, 1)


def wall_material_image(name, w, h, seed=100):
    """The finished wall material `name` as an image (relief shading added)."""
    rgb = WALL_MATERIALS[name](w, h, seed)
    rgb = emboss(rgb, strength={"ship": 2.0, "seaweed": 2.5}.get(name, 4.0))
    return to_image(rgb)
