"""Shared helpers for procedural asset generation (numpy + Pillow)."""

import numpy as np
from PIL import Image


def periodic_noise(w, h, beta=2.0, seed=0, lowcut=0.0):
    """Seamlessly tileable fractal noise in [0, 1] (FFT-filtered white noise).

    beta controls smoothness (higher = smoother); lowcut removes the very
    lowest frequencies (useful to avoid one huge dark/bright blotch).

    Method: start with random static, convert it to frequencies with an FFT,
    turn down the high (fine-detail) frequencies, and convert back.  Because
    the FFT treats the image as repeating, the result tiles seamlessly.
    """
    rng = np.random.default_rng(seed)
    white = rng.standard_normal((h, w))
    spec = np.fft.fft2(white)
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.fftfreq(w)[None, :]
    f = np.sqrt(fx * fx + fy * fy)        # how fine each frequency's detail is
    f[0, 0] = 1.0                         # (avoid dividing by zero below)
    spec = spec / f ** (beta / 2.0)       # weaken fine detail more than coarse
    spec[0, 0] = 0.0                      # remove the overall average brightness
    if lowcut > 0:
        spec[f < lowcut] = 0.0
    n = np.real(np.fft.ifft2(spec))
    n -= n.min()                          # rescale to exactly 0..1
    n /= max(n.max(), 1e-9)
    return n.astype(np.float32)


def colormap(values, stops):
    """Map an array of values in [0,1] through colour stops [(t, (r,g,b)), ...].

    E.g. [(0, dark), (1, light)] turns 0 into dark, 1 into light and values in
    between into blends.  This is how grey noise becomes sand, rock, coral...
    """
    ts = np.array([s[0] for s in stops], dtype=np.float32)
    cols = np.array([s[1] for s in stops], dtype=np.float32)
    out = np.empty(values.shape + (3,), dtype=np.float32)
    for c in range(3):
        out[..., c] = np.interp(values, ts, cols[:, c])
    return out


def box_blur(a, r):
    """Separable box blur of a 2D float array with edge padding.

    Each pixel becomes the average of the (2r+1) x (2r+1) square around it.
    Done as a vertical then a horizontal pass, using running sums
    (cumsum) so it is fast whatever the radius.
    """
    if r <= 0:
        return a
    k = 2 * r + 1
    p = np.pad(a, ((r + 1, r), (0, 0)), mode="edge")
    c = np.cumsum(p, axis=0)
    a = (c[k:] - c[:-k]) / k
    p = np.pad(a, ((0, 0), (r + 1, r)), mode="edge")
    c = np.cumsum(p, axis=1)
    return (c[:, k:] - c[:, :-k]) / k


def smoothstep(e0, e1, x):
    """0 below e0, 1 above e1, with a smooth S-shaped blend in between.
    (If e0 > e1 it is reversed: 1 below e1, 0 above e0.)"""
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def to_image(rgb, alpha=None):
    """float RGB [0,1] (+ optional alpha [0,1]) -> PIL RGBA image."""
    rgb8 = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
    if alpha is None:
        a8 = np.full(rgb8.shape[:2], 255, dtype=np.uint8)
    else:
        a8 = (np.clip(alpha, 0, 1) * 255).astype(np.uint8)
    return Image.fromarray(np.dstack([rgb8, a8]), "RGBA")


def radial_layer(size, bbox, inner, outer, hl=(-0.3, -0.35), power=1.2, alpha=255):
    """An RGBA layer containing an ellipse filled with a shaded gradient.

    hl is the highlight position in normalised ellipse coordinates
    ((0, 0) = centre, (-1, -1) = top-left of the bounding box).  It gives
    flat shapes a rounded, lit-from-one-side look: `inner` colour at the
    highlight, fading to `outer` at the far edge.
    """
    w, h = size
    x0, y0, x1, y1 = bbox
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rx, ry = max((x1 - x0) / 2, 1), max((y1 - y0) / 2, 1)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx, ny = (xx - cx) / rx, (yy - cy) / ry
    r = np.sqrt(nx * nx + ny * ny)
    d = np.sqrt((nx - hl[0]) ** 2 + (ny - hl[1]) ** 2) / (1.0 + np.hypot(*hl))
    t = np.clip(d, 0, 1) ** power
    inner = np.array(inner, dtype=np.float32)
    outer = np.array(outer, dtype=np.float32)
    col = inner * (1 - t)[..., None] + outer * t[..., None]
    # opaque inside the ellipse, with a ~1 pixel soft edge
    a = np.clip((1.0 - r) * min(rx, ry), 0, 1) * alpha
    arr = np.dstack([np.clip(col, 0, 255), a]).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def glow_layer(size, center, radius, color, strength=1.0):
    """Soft radial glow (additive-looking halo) as an RGBA layer."""
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.hypot(xx - center[0], yy - center[1]) / radius
    a = np.clip(1 - d, 0, 1) ** 2 * 255 * strength
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = color
    arr[..., 3] = np.clip(a, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def finish(img, out_size):
    """Downsample a supersampled drawing for anti-aliasing.

    Pillow draws hard pixel edges; drawing at 2x size and shrinking smooths them.
    """
    if isinstance(out_size, int):
        out_size = (out_size, out_size)
    return img.resize(out_size, Image.LANCZOS)
