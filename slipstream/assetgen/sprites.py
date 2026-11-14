"""Procedurally drawn sprites (Pillow).

Everything is drawn on a 512px canvas and downsampled for anti-aliasing.
The player sprites are drawn from *behind* (the camera follows the player).
"""

import math

import numpy as np
from PIL import Image, ImageDraw

from .common import radial_layer, glow_layer, finish, periodic_noise

S = 512
OUT = 256
OL = (18, 22, 34, 255)        # outline colour
OW = 7                        # outline width (at 512px)


def _canvas(w=S, h=S):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def _rgba(c, a=255):
    return tuple(int(v) for v in c[:3]) + (a,)


def _shade(c, k):
    return tuple(int(max(0, min(255, v * k))) for v in c[:3])


def _ellipse_points(cx, cy, rx, ry, ang, n=40):
    ca, sa = math.cos(ang), math.sin(ang)
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        pts.append((cx + x * ca - y * sa, cy + x * sa + y * ca))
    return pts


# ---------------------------------------------------------------------------
# Player: fish seen from behind
# ---------------------------------------------------------------------------

FISH_STYLES = {
    "fish_clown": dict(body=(255, 125, 25), dark=(190, 60, 5), light=(255, 190, 110),
                       fin=(255, 150, 60), tail=(255, 140, 40), band=(250, 250, 250),
                       edge=(20, 15, 15), bw=210, bh=250),
    "fish_tang": dict(body=(40, 95, 225), dark=(15, 35, 120), light=(120, 180, 255),
                      fin=(30, 60, 160), tail=(255, 215, 30), band=None,
                      edge=(10, 15, 40), bw=170, bh=270),
}


def fish_frame(style_name, phase):
    st = FISH_STYLES[style_name]
    img, d = _canvas()
    cx, cy = S / 2, S / 2 + 6
    bw, bh = st["bw"], st["bh"]
    sway = math.sin(2 * math.pi * phase)
    flap = math.sin(2 * math.pi * phase + 1.3)
    fin, tail = _rgba(st["fin"]), _rgba(st["tail"])

    # dorsal fin (sticks up above the body, sways opposite to the tail)
    top = cy - bh / 2
    dor = [(cx - 16, top + 40), (cx - sway * 16 - 8, top - 78), (cx - sway * 16 + 10, top - 70),
           (cx + 16, top + 40)]
    d.polygon(dor, fill=fin, outline=OL, width=OW)
    # ventral fin
    bot = cy + bh / 2
    ven = [(cx - 12, bot - 30), (cx - sway * 10 - 6, bot + 50), (cx - sway * 10 + 8, bot + 44),
           (cx + 12, bot - 30)]
    d.polygon(ven, fill=fin, outline=OL, width=OW)

    # pectoral fins flapping at the sides
    for side in (-1, 1):
        ax, ay = cx + side * (bw / 2 - 30), cy + 40
        ang = 0.45 + 0.4 * flap
        L = 100
        tip = (ax + side * L * math.cos(ang), ay + L * math.sin(ang))
        tip2 = (ax + side * L * 0.75 * math.cos(ang + 0.5), ay + L * 0.75 * math.sin(ang + 0.5))
        d.polygon([(ax, ay - 26), tip, tip2, (ax, ay + 22)], fill=fin, outline=OL, width=OW)

    # body
    bbox = (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
    img.alpha_composite(radial_layer((S, S), bbox, st["light"], st["dark"], hl=(-0.25, -0.45)))
    d.ellipse(bbox, outline=OL, width=OW)
    if st["band"]:
        k = 0.70
        rb = (cx - bw / 2 * k, cy - bh / 2 * k, cx + bw / 2 * k, cy + bh / 2 * k)
        d.ellipse(rb, outline=OL, width=40)
        d.ellipse(rb, outline=_rgba(st["band"]), width=28)
    else:
        # tang: dark "palette" marking
        k = 0.62
        rb = (cx - bw / 2 * k, cy - bh / 2 * k - 20, cx + bw / 2 * k, cy + bh / 2 * k - 20)
        d.ellipse(rb, outline=_rgba(st["edge"]), width=18)

    # eyes bulge out on the sides of the head
    for side in (-1, 1):
        ex, ey, r = cx + side * (bw / 2 - 4), cy - bh * 0.22, 31
        d.ellipse((ex - r, ey - r, ex + r, ey + r), fill=(255, 255, 255, 255), outline=OL, width=OW)
        px = ex + side * 9
        d.ellipse((px - 16, ey - 16, px + 16, ey + 16), fill=(10, 10, 15, 255))
        d.ellipse((px - 6 - side * 3, ey - 11, px + 2 - side * 3, ey - 3), fill=(255, 255, 255, 255))

    # tail base (peduncle)
    pw, ph = 62, 96
    pb = (cx - pw / 2 + sway * 10, cy - ph / 2, cx + pw / 2 + sway * 10, cy + ph / 2)
    img.alpha_composite(radial_layer((S, S), pb, st["body"], st["dark"], hl=(0, -0.3)))
    d.ellipse(pb, outline=OL, width=OW)

    # tail fin: a vertical fan seen from behind - its apparent width follows the swish
    rx = cx + sway * 10
    tx = cx + sway * 140
    fx = cx + sway * 88
    T = 190
    poly = [(rx - 16, cy - 30), (tx - 14, cy - T), (tx + 16, cy - T + 16), (fx, cy),
            (tx + 16, cy + T - 16), (tx - 14, cy + T), (rx + 16, cy + 30)]
    d.polygon(poly, fill=tail, outline=OL, width=OW)
    ray = _rgba(_shade(st["tail"], 0.7))
    for i in range(1, 8):
        t = i / 8
        ex = tx + (fx - tx) * (1 - abs(2 * t - 1)) * 0.9
        ey = cy - T + 2 * T * t
        d.line([(rx, cy), (ex, ey * 0.97 + cy * 0.03)], fill=ray, width=4)
    return finish(img, OUT)


def mermaid_frame(phase):
    """Mermaid seen from behind: hair, arms sweeping, scaled tail, flapping fluke."""
    img, d = _canvas()
    cx, cy = S / 2, 250
    skin, skin_d, skin_l = (238, 192, 158), (180, 120, 90), (255, 225, 200)
    hair, hair_d = (215, 55, 35), (140, 25, 20)
    tail, tail_d, tail_l = (35, 165, 140), (15, 95, 85), (120, 230, 200)
    fin = (80, 210, 190, 255)
    w = 2 * math.pi * phase
    stroke = math.sin(w)
    flap = math.sin(w + 0.8)

    # arms (behind the torso): breaststroke sweep
    for side in (-1, 1):
        sx, sy = cx + side * 62, cy - 78
        a1 = 0.35 + 0.55 * stroke
        ex, ey = sx + side * 78 * math.cos(a1), sy - 78 * math.sin(a1) + 20
        a2 = a1 - 0.6 - 0.3 * stroke
        hx, hy = ex + side * 66 * math.cos(a2), ey - 66 * math.sin(a2) + 10
        d.line([(sx, sy), (ex, ey), (hx, hy)], fill=OL, width=40, joint="curve")
        d.line([(sx, sy), (ex, ey), (hx, hy)], fill=_rgba(skin), width=28, joint="curve")
        d.ellipse((hx - 18, hy - 18, hx + 18, hy + 18), fill=_rgba(skin), outline=OL, width=5)

    # tail: tapers from the hips down to the fluke
    fy = cy + 168 + flap * 12
    left, right = [], []
    for i in range(13):
        t = i / 12
        y = cy + 25 + (fy - cy - 25) * t
        half = 68 * (1 - t) + 16 * t + 10 * math.sin(math.pi * t)
        x = cx + math.sin(w + t * 2.5) * 8 * t
        left.append((x - half, y))
        right.append((x + half, y))
    poly = left + right[::-1]
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).polygon(poly, fill=255)
    layer = radial_layer((S, S), (cx - 75, cy + 10, cx + 75, fy + 20), tail_l, tail_d, hl=(-0.3, -0.6))
    layer.putalpha(Image.fromarray(np.minimum(np.asarray(layer)[..., 3], np.asarray(mask))))
    img.alpha_composite(layer)
    for row in range(10):
        y = cy + 40 + row * 14
        t = (y - cy - 25) / max(fy - cy - 25, 1)
        if t > 0.92:
            break
        half = 68 * (1 - t) + 16 * t
        for k in range(-4, 5):
            x = cx + k * 20 + (10 if row % 2 else 0)
            if abs(x - cx) < half - 8:
                d.arc((x - 10, y - 8, x + 10, y + 8), 20, 160, fill=_rgba(tail_d), width=3)
    d.polygon(poly, outline=OL, width=OW)

    # fluke: a horizontal fin flapping up and down (seen from behind)
    up = flap * 48
    fluke = [(cx - 16, fy - 10), (cx - 128, fy + up - 22), (cx - 112, fy + up + 20),
             (cx - 40, fy + 10 + up * 0.4), (cx, fy + 18 + up * 0.2), (cx + 40, fy + 10 + up * 0.4),
             (cx + 112, fy + up + 20), (cx + 128, fy + up - 22), (cx + 16, fy - 10)]
    d.polygon(fluke, fill=fin, outline=OL, width=OW)
    for k in (-1, 1):
        for j in range(1, 4):
            d.line([(cx + k * 16, fy), (cx + k * (30 + 28 * j), fy + up * (0.3 + 0.2 * j))],
                   fill=_rgba(tail_d), width=3)

    # back / torso
    tb = (cx - 74, cy - 105, cx + 74, cy + 55)
    img.alpha_composite(radial_layer((S, S), tb, skin_l, skin_d, hl=(-0.3, -0.5)))
    d.ellipse(tb, outline=OL, width=OW)
    # hip band where skin meets scales
    d.chord((cx - 72, cy + 5, cx + 72, cy + 60), 180, 360, fill=_rgba(tail), outline=OL, width=5)
    # shell top strap across the back
    d.line([(cx - 72, cy - 30), (cx + 72, cy - 30)], fill=OL, width=16)
    d.line([(cx - 72, cy - 30), (cx + 72, cy - 30)], fill=(170, 90, 210, 255), width=9)

    # long hair flowing down the back, swaying with the stroke
    sway = math.sin(w - 1.0) * 14
    hx, hy = cx, cy - 140
    hair_poly = [(hx - 58, hy - 10), (hx - 64, hy + 50), (hx - 50 + sway, hy + 88),
                 (hx - 34 + sway * 1.5, hy + 122), (hx - 12 + sway * 1.8, hy + 104),
                 (hx + sway * 2, hy + 134), (hx + 12 + sway * 1.8, hy + 104),
                 (hx + 34 + sway * 1.5, hy + 122), (hx + 50 + sway, hy + 88),
                 (hx + 64, hy + 50), (hx + 58, hy - 10)]
    d.polygon(hair_poly, fill=_rgba(hair), outline=OL, width=OW)
    for k in (-26, -9, 9, 26):
        d.line([(hx + k, hy + 10), (hx + k * 1.15 + sway * 1.4, hy + 108)], fill=_rgba(hair_d), width=4)
    # back of the head
    hb = (hx - 60, hy - 62, hx + 60, hy + 58)
    img.alpha_composite(radial_layer((S, S), hb, (245, 110, 70), hair_d, hl=(-0.3, -0.5)))
    d.ellipse(hb, outline=OL, width=OW)
    # starfish hair clip
    pts = []
    for i in range(10):
        a = -math.pi / 2 + math.pi * i / 5
        r = 20 if i % 2 == 0 else 8
        pts.append((hx + 30 + math.cos(a) * r, hy - 25 + math.sin(a) * r))
    d.polygon(pts, fill=(255, 200, 60, 255), outline=OL, width=3)
    return finish(img, OUT)


def sub_frame(phase):
    img, d = _canvas()
    cx, cy = S / 2, S / 2 + 20
    yellow, ydark, ylight = (250, 200, 30), (170, 110, 10), (255, 240, 150)

    # conning tower + periscope (behind the hull)
    d.line([(cx + 18, cy - 250), (cx + 18, cy - 150)], fill=(90, 90, 100, 255), width=12)
    d.line([(cx + 18, cy - 250), (cx + 42, cy - 250)], fill=(90, 90, 100, 255), width=12)
    d.rounded_rectangle((cx - 48, cy - 215, cx + 48, cy - 100), radius=26,
                        fill=_rgba(_shade(yellow, 0.9)), outline=OL, width=OW)
    # hull
    R = 150
    bbox = (cx - R, cy - R, cx + R, cy + R)
    img.alpha_composite(radial_layer((S, S), bbox, ylight, ydark, hl=(-0.35, -0.45)))
    d.ellipse(bbox, outline=OL, width=OW)
    # weld seams
    for k in (0.82, 0.62):
        r = R * k
        d.arc((cx - r, cy - r, cx + r, cy + r), 200, 340, fill=_rgba(_shade(yellow, 0.7)), width=4)
    # stern cone
    r = 100
    img.alpha_composite(radial_layer((S, S), (cx - r, cy - r, cx + r, cy + r), yellow, ydark,
                                     hl=(-0.2, -0.3)))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=OL, width=5)
    # cross fins (dive planes + rudders)
    fin_c = _rgba((70, 80, 95))
    for ang in (0, 90, 180, 270):
        a = math.radians(ang)
        ca, sa = math.cos(a), math.sin(a)
        pts = [(60, -15), (232, -9), (232, 9), (60, 15)]
        p = [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]
        d.polygon(p, fill=fin_c, outline=OL, width=5)
    # nav lights
    d.ellipse((cx - 246, cy - 12, cx - 222, cy + 12), fill=(255, 40, 40, 255), outline=OL, width=3)
    d.ellipse((cx + 222, cy - 12, cx + 246, cy + 12), fill=(40, 255, 80, 255), outline=OL, width=3)
    # duct + propeller
    d.ellipse((cx - 82, cy - 82, cx + 82, cy + 82), outline=(60, 65, 75, 255), width=18)
    base = phase * 2 * math.pi / 3
    for k in range(3):
        a = base + k * 2 * math.pi / 3
        bx, by = cx + math.cos(a) * 38, cy + math.sin(a) * 38
        d.polygon(_ellipse_points(bx, by, 40, 15, a), fill=(200, 160, 60, 255), outline=OL, width=4)
    d.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), fill=(120, 120, 130, 255), outline=OL, width=4)
    return finish(img, OUT)


# ---------------------------------------------------------------------------
# Obstacles
# ---------------------------------------------------------------------------

def chest():
    img, d = _canvas()
    wood, wdark, gold = (140, 82, 35), (85, 45, 18), (240, 195, 50)
    x0, x1, yb, yt = 86, 426, 440, 250
    # gold glow and coins spilling from the open lid
    img.alpha_composite(glow_layer((S, S), (256, 250), 200, (255, 220, 90), 0.8))
    d.polygon([(x0 + 10, yt), (x0 + 40, 150), (x1 - 40, 150), (x1 - 10, yt)],
              fill=_rgba(wdark), outline=OL, width=OW)  # lid interior
    for i in range(14):
        cxp = x0 + 50 + (i * 37) % 250
        cyp = yt - 10 - (i * 13) % 50
        d.ellipse((cxp - 20, cyp - 12, cxp + 20, cyp + 12), fill=_rgba(gold), outline=OL, width=4)
    d.rectangle((x0, yt, x1, yb), fill=_rgba(wood), outline=OL, width=OW)
    for y in range(yt + 45, yb, 45):
        d.line([(x0 + 4, y), (x1 - 4, y)], fill=_rgba(wdark), width=5)
    for x in (x0 + 30, x1 - 30, 256):
        d.rectangle((x - 13, yt, x + 13, yb), fill=_rgba(gold), outline=OL, width=4)
    d.rounded_rectangle((226, yt + 20, 286, yt + 90), radius=10, fill=_rgba(gold), outline=OL, width=5)
    d.ellipse((248, yt + 42, 264, yt + 60), fill=OL)
    return finish(img, OUT)


def boulder(seed=4):
    img, _ = _canvas()
    rng = np.random.default_rng(seed)
    pts = []
    for i in range(14):
        a = 2 * math.pi * i / 14
        r = 190 * rng.uniform(0.8, 1.05)
        pts.append((256 + r * math.cos(a), 280 + r * 0.82 * math.sin(a)))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    shade = radial_layer((S, S), (40, 90, 470, 470), (170, 165, 155), (60, 58, 60), hl=(-0.4, -0.5))
    n = periodic_noise(S, S, beta=1.6, seed=seed)
    arr = np.array(shade).astype(np.float32)
    arr[..., :3] *= (0.8 + 0.4 * n)[..., None]
    moss = n > 0.68
    arr[moss, :3] = arr[moss, :3] * 0.5 + np.array([40, 90, 35]) * 0.5
    arr[..., 3] = np.array(mask)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
    d = ImageDraw.Draw(img)
    d.polygon(pts, outline=OL, width=OW)
    d.line([(200, 200), (240, 260), (225, 320)], fill=(40, 38, 40, 255), width=6)
    d.line([(330, 240), (300, 300)], fill=(40, 38, 40, 255), width=5)
    return finish(img, OUT)


def anchor():
    img, d = _canvas()
    iron = (95, 100, 110, 255)
    d.ellipse((216, 40, 296, 120), outline=OL, width=34)
    d.ellipse((216, 40, 296, 120), outline=iron, width=22)
    d.rectangle((236, 110, 276, 430), fill=iron, outline=OL, width=OW)
    d.rounded_rectangle((150, 150, 362, 186), radius=14, fill=iron, outline=OL, width=OW)
    d.arc((86, 230, 426, 470), 20, 160, fill=OL, width=46)
    d.arc((86, 230, 426, 470), 20, 160, fill=iron, width=32)
    for sx in (-1, 1):
        x = 256 + sx * 160
        d.polygon([(x - sx * 10, 400), (x + sx * 40, 330), (x + sx * 30, 420)], fill=iron, outline=OL, width=5)
    # rust + chain links
    for i in range(4):
        y = 30 - i * 26
        d.ellipse((240, y - 28, 272, y + 4), outline=(80, 70, 60, 255), width=8)
    return finish(img, OUT)


def barrel():
    img, d = _canvas()
    wood, dark = (150, 95, 45), (95, 55, 25)
    img.alpha_composite(radial_layer((S, S), (110, 60, 402, 460), (190, 130, 70), dark, hl=(-0.2, 0)))
    d.ellipse((110, 60, 402, 460), outline=OL, width=OW)
    for x in range(160, 380, 46):
        d.line([(x, 75), (x, 445)], fill=_rgba(dark), width=4)
    for y in (130, 390):
        d.arc((110, y - 40, 402, y + 40), 0, 180, fill=(60, 60, 65, 255), width=16)
    d.ellipse((150, 64, 362, 110), fill=_rgba(wood), outline=OL, width=5)
    return finish(img, OUT)


def mine():
    img, d = _canvas()
    cx, cy, R = 256, 236, 130
    for k in range(12):
        a = 2 * math.pi * k / 12
        x1, y1 = cx + math.cos(a) * (R + 45), cy + math.sin(a) * (R + 45)
        d.line([(cx, cy), (x1, y1)], fill=(50, 52, 58, 255), width=16)
        d.ellipse((x1 - 15, y1 - 15, x1 + 15, y1 + 15), fill=(200, 60, 40, 255), outline=OL, width=4)
    img.alpha_composite(radial_layer((S, S), (cx - R, cy - R, cx + R, cy + R), (120, 125, 135),
                                     (25, 27, 32), hl=(-0.4, -0.4)))
    d.ellipse((cx - R, cy - R, cx + R, cy + R), outline=OL, width=OW)
    d.arc((cx - R, cy - 20, cx + R, cy + 20), 0, 180, fill=(30, 30, 35, 255), width=6)
    return finish(img, OUT)


def octopus_frame(phase):
    img, d = _canvas()
    body, dark, light = (170, 60, 160), (95, 25, 95), (235, 140, 225)
    cx, cy = 256, 190
    for k in range(8):
        base_a = math.pi * (0.1 + 0.8 * k / 7)
        pts = []
        for i in range(14):
            t = i / 13
            wig = math.sin(2 * math.pi * (phase + t * 0.8 + k * 0.13)) * 40 * t
            r = 70 + 230 * t
            a = base_a + wig / 300
            pts.append((cx + math.cos(a) * r * 0.85 + wig, cy + 30 + math.sin(a) * r))
        for i in range(len(pts) - 1):
            w = int(44 * (1 - i / 14) + 8)
            d.line([pts[i], pts[i + 1]], fill=OL, width=w + 8)
        for i in range(len(pts) - 1):
            w = int(44 * (1 - i / 14) + 8)
            d.line([pts[i], pts[i + 1]], fill=_rgba(body), width=w)
        for i in range(2, 12, 2):
            x, y = pts[i]
            d.ellipse((x - 6, y - 6, x + 6, y + 6), fill=_rgba(light))
    bbox = (cx - 120, cy - 150, cx + 120, cy + 110)
    img.alpha_composite(radial_layer((S, S), bbox, light, dark, hl=(-0.3, -0.5)))
    d.ellipse(bbox, outline=OL, width=OW)
    for side in (-1, 1):
        ex, ey = cx + side * 50, cy + 30
        d.ellipse((ex - 30, ey - 26, ex + 30, ey + 26), fill=(255, 255, 230, 255), outline=OL, width=5)
        d.rectangle((ex - 18, ey - 6, ex + 18, ey + 6), fill=(10, 10, 10, 255))
    return finish(img, OUT)


def jellyfish_frame(phase):
    img, d = _canvas()
    cx, cy = 256, 170
    pulse = 1 + 0.08 * math.sin(2 * math.pi * phase)
    for k in range(9):
        x0 = cx - 110 + k * 27
        pts = []
        for i in range(16):
            t = i / 15
            pts.append((x0 + math.sin(2 * math.pi * (phase + t + k * 0.2)) * 22 * t, cy + 40 + t * 280))
        d.line(pts, fill=(255, 170, 220, 170), width=6)
    for k in range(4):
        x0 = cx - 50 + k * 33
        pts = [(x0 + math.sin(2 * math.pi * (phase * 0.7 + t / 10)) * 14, cy + 40 + t * 18)
               for t in range(12)]
        d.line(pts, fill=(255, 120, 200, 210), width=16)
    rx, ry = 150 * pulse, 115 / pulse
    bbox = (cx - rx, cy - ry, cx + rx, cy + ry * 0.75)
    img.alpha_composite(radial_layer((S, S), bbox, (255, 220, 245), (220, 90, 180),
                                     hl=(-0.2, -0.5), alpha=215))
    d.chord((cx - rx, cy - ry, cx + rx, cy + ry), 180, 360, outline=(120, 30, 100, 255), width=5)
    d.ellipse((cx - 60, cy - 60, cx + 60, cy + 20), outline=(255, 255, 255, 120), width=6)
    return finish(img, OUT)


def neptune():
    img, d = _canvas()
    skin, skind = (120, 190, 185), (60, 120, 120)
    gold = (245, 200, 50, 255)
    # trident
    d.rectangle((400, 60, 416, 500), fill=gold, outline=OL, width=4)
    for x in (366, 408, 450):
        d.polygon([(x - 10, 140), (x, 40), (x + 10, 140)], fill=gold, outline=OL, width=4)
    d.rounded_rectangle((360, 130, 456, 150), radius=6, fill=gold, outline=OL, width=4)
    # shoulders
    img.alpha_composite(radial_layer((S, S), (70, 330, 440, 620), skin, skind, hl=(-0.2, -0.6)))
    # head
    img.alpha_composite(radial_layer((S, S), (156, 120, 356, 330), (170, 225, 215), skind, hl=(-0.2, -0.4)))
    d.ellipse((156, 120, 356, 330), outline=OL, width=OW)
    # beard
    beard = [(150, 240), (180, 300), (190, 420), (230, 480), (256, 500), (282, 480), (322, 420),
             (332, 300), (362, 240), (330, 290), (256, 310), (182, 290)]
    d.polygon(beard, fill=(235, 240, 250, 255), outline=OL, width=OW)
    for x in range(200, 320, 22):
        d.line([(x, 320), (x + 8, 440)], fill=(190, 200, 215, 255), width=4)
    d.arc((210, 255, 300, 300), 200, 340, fill=(240, 245, 255, 255), width=14)  # moustache
    # eyes and brows
    for side in (-1, 1):
        ex = 256 + side * 40
        d.ellipse((ex - 16, 200, ex + 16, 226), fill=(255, 255, 255, 255), outline=OL, width=4)
        d.ellipse((ex - 7, 206, ex + 7, 222), fill=(20, 40, 80, 255))
        d.line([(ex - 24, 190 - side * 0), (ex + 22, 186)], fill=(235, 240, 250, 255), width=10)
    # crown
    crown = [(170, 150), (180, 70), (215, 120), (256, 50), (297, 120), (332, 70), (342, 150)]
    d.polygon(crown, fill=gold, outline=OL, width=OW)
    for x, c in ((215, (220, 30, 60)), (256, (40, 120, 230)), (297, (220, 30, 60))):
        d.ellipse((x - 10, 125, x + 10, 145), fill=c + (255,), outline=OL, width=3)
    return finish(img, OUT)


def net():
    img, d = _canvas()
    rope = (215, 200, 160, 255)
    x0, x1, y0, y1 = 40, 472, 70, 470
    rows, cols = 9, 11
    def p(i, j):
        x = x0 + (x1 - x0) * j / cols
        y = y0 + (y1 - y0) * i / rows + math.sin(math.pi * j / cols) * 30 * i / rows
        return x, y
    for i in range(rows + 1):
        pts = [p(i, j) for j in range(cols + 1)]
        d.line(pts, fill=OL, width=9)
        d.line(pts, fill=rope, width=5)
    for j in range(cols + 1):
        pts = [p(i, j) for i in range(rows + 1)]
        d.line(pts, fill=OL, width=9)
        d.line(pts, fill=rope, width=5)
    for j in range(0, cols + 1, 2):
        x, y = p(0, j)
        d.ellipse((x - 20, y - 20, x + 20, y + 20), fill=(250, 120, 30, 255), outline=OL, width=5)
        x, y = p(rows, j)
        d.rectangle((x - 10, y - 8, x + 10, y + 12), fill=(80, 80, 90, 255), outline=OL, width=3)
    return finish(img, OUT)


# ---------------------------------------------------------------------------
# Rewards (glowing pickups)
# ---------------------------------------------------------------------------

def pearl():
    img, d = _canvas()
    img.alpha_composite(glow_layer((S, S), (256, 256), 250, (255, 240, 255), 0.9))
    img.alpha_composite(radial_layer((S, S), (126, 126, 386, 386), (255, 255, 255), (200, 170, 210),
                                     hl=(-0.35, -0.4)))
    d.ellipse((126, 126, 386, 386), outline=(120, 90, 140, 255), width=6)
    d.ellipse((180, 170, 230, 215), fill=(255, 255, 255, 230))
    return finish(img, OUT)


def shell():
    img, d = _canvas()
    img.alpha_composite(glow_layer((S, S), (256, 256), 250, (255, 220, 200), 0.85))
    pts = [(256, 420)]
    for i in range(13):
        a = math.pi * (1.05 + 0.9 * i / 12)
        r = 190 + (14 if i % 2 else 0)
        pts.append((256 + math.cos(a) * r, 330 + math.sin(a) * r))
    d.polygon(pts, fill=(255, 175, 140, 255), outline=OL, width=OW)
    for i in range(1, 12):
        x, y = pts[i + 1]
        d.line([(256, 415), (x, y)], fill=(215, 110, 90, 255), width=6)
    d.polygon([(206, 420), (256, 380), (306, 420), (256, 450)], fill=(240, 150, 120, 255), outline=OL, width=5)
    return finish(img, OUT)


def starfish():
    img, d = _canvas()
    img.alpha_composite(glow_layer((S, S), (256, 256), 250, (255, 250, 170), 0.85))
    pts = []
    for i in range(10):
        a = -math.pi / 2 + math.pi * i / 5
        r = 210 if i % 2 == 0 else 90
        pts.append((256 + math.cos(a) * r, 266 + math.sin(a) * r))
    d.polygon(pts, fill=(255, 185, 40, 255), outline=OL, width=OW)
    for i in range(0, 10, 2):
        a = -math.pi / 2 + math.pi * i / 5
        for t in (0.35, 0.55, 0.75):
            x, y = 256 + math.cos(a) * 210 * t, 266 + math.sin(a) * 210 * t
            d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=(255, 235, 160, 255))
    return finish(img, OUT)


def gem():
    img, d = _canvas()
    img.alpha_composite(glow_layer((S, S), (256, 256), 255, (160, 255, 255), 1.0))
    top = [(146, 210), (196, 130), (316, 130), (366, 210)]
    d.polygon(top + [(256, 420)], fill=(60, 220, 230, 255), outline=OL, width=OW)
    d.polygon([(196, 130), (256, 210), (316, 130)], fill=(180, 255, 255, 255))
    d.polygon([(146, 210), (256, 420), (256, 210)], fill=(30, 170, 200, 255))
    d.line([(146, 210), (366, 210)], fill=OL, width=5)
    d.polygon(top + [(256, 420)], outline=OL, width=OW)
    return finish(img, OUT)


# ---------------------------------------------------------------------------
# Effects
# ---------------------------------------------------------------------------

def bubble():
    img, d = _canvas(128, 128)
    d.ellipse((8, 8, 120, 120), fill=(200, 240, 255, 50), outline=(235, 250, 255, 230), width=7)
    d.ellipse((34, 28, 58, 50), fill=(255, 255, 255, 230))
    return img.resize((64, 64), Image.LANCZOS)


def arrow():
    img, d = _canvas(128, 128)
    d.polygon([(64, 14), (118, 104), (10, 104)], fill=(255, 255, 255, 235), outline=(0, 0, 0, 160), width=5)
    return img.resize((64, 64), Image.LANCZOS)


def aim_ring():
    """Crosshair ring for the aim helper (white; tinted green/red at runtime)."""
    img, d = _canvas(256, 256)
    d.ellipse((24, 24, 232, 232), outline=(0, 0, 0, 150), width=22)
    d.ellipse((28, 28, 228, 228), outline=(255, 255, 255, 255), width=12)
    for a in range(4):
        ang = a * math.pi / 2
        c, s = math.cos(ang), math.sin(ang)
        d.line([(128 + c * 70, 128 + s * 70), (128 + c * 118, 128 + s * 118)], fill=(255, 255, 255, 255), width=10)
    d.ellipse((116, 116, 140, 140), fill=(255, 255, 255, 255))
    return img.resize((128, 128), Image.LANCZOS)


def dot():
    img, d = _canvas(64, 64)
    d.ellipse((6, 6, 58, 58), fill=(255, 255, 255, 255), outline=(0, 0, 0, 140), width=5)
    return img.resize((32, 32), Image.LANCZOS)


def ground(img):
    """Shift the artwork down so its lowest opaque pixel touches the bottom edge
    (used for objects that sit on the sea floor)."""
    a = np.asarray(img)[..., 3]
    rows = np.where(a.max(axis=1) > 40)[0]
    if not len(rows):
        return img
    shift = img.height - 1 - rows[-1]
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, shift))
    return out


def shadow():
    size = 128
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    r = np.hypot(xx - size / 2 + 0.5, yy - size / 2 + 0.5) / (size / 2)
    a = np.clip(1 - r, 0, 1) ** 1.4
    arr = np.zeros((size, size, 4), dtype=np.uint8)
    arr[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def marker(color):
    """Vertical glowing banner used for 'last run' / 'best' lines."""
    w, h = 32, 256
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    x = np.abs(xx / (w - 1) * 2 - 1)
    a = (1 - x) ** 1.5 * (0.35 + 0.65 * (0.5 + 0.5 * np.sin(yy / 10)))
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = color
    arr[..., 3] = (np.clip(a, 0, 1) * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


# ---------------------------------------------------------------------------
# Boats (side view, for the surface band)
# ---------------------------------------------------------------------------

def sailboat():
    img, d = _canvas(S, 320)
    d.line([(250, 30), (250, 240)], fill=(90, 60, 30, 255), width=10)
    d.polygon([(258, 40), (258, 225), (420, 225)], fill=(250, 250, 245, 255), outline=OL, width=6)
    d.polygon([(242, 70), (242, 225), (120, 225)], fill=(240, 90, 70, 255), outline=OL, width=6)
    d.polygon([(250, 30), (290, 42), (250, 54)], fill=(255, 220, 40, 255), outline=OL, width=3)
    hull = [(70, 230), (450, 230), (400, 300), (120, 300)]
    d.polygon(hull, fill=(255, 255, 255, 255), outline=OL, width=6)
    d.line([(90, 255), (432, 255)], fill=(30, 90, 170, 255), width=10)
    return img.resize((256, 160), Image.LANCZOS)


def warship():
    img, d = _canvas(S, 320)
    grey, dark = (130, 138, 150, 255), (80, 86, 96, 255)
    d.polygon([(20, 220), (492, 220), (440, 300), (70, 300)], fill=grey, outline=OL, width=6)
    d.rectangle((190, 140, 330, 222), fill=grey, outline=OL, width=6)
    d.rectangle((225, 90, 300, 142), fill=grey, outline=OL, width=6)
    d.rectangle((340, 120, 375, 222), fill=dark, outline=OL, width=5)
    d.line([(262, 20), (262, 92)], fill=OL, width=6)
    d.line([(235, 45), (290, 45)], fill=OL, width=5)
    d.rectangle((90, 190, 150, 222), fill=dark, outline=OL, width=4)
    d.line([(150, 200), (195, 192)], fill=OL, width=8)
    for x in range(205, 320, 28):
        d.ellipse((x, 160, x + 14, 174), fill=(255, 240, 160, 255))
    d.line([(60, 262), (452, 262)], fill=(180, 40, 40, 255), width=8)
    return img.resize((256, 160), Image.LANCZOS)


def trawler():
    img, d = _canvas(S, 320)
    red, white = (200, 50, 40, 255), (240, 240, 235, 255)
    d.line([(150, 40), (150, 225)], fill=(60, 60, 60, 255), width=9)
    d.line([(150, 50), (60, 200)], fill=(60, 60, 60, 255), width=5)
    d.line([(150, 50), (240, 160)], fill=(60, 60, 60, 255), width=5)
    d.rectangle((280, 120, 420, 225), fill=white, outline=OL, width=6)
    d.rectangle((300, 140, 330, 170), fill=(80, 150, 200, 255), outline=OL, width=3)
    d.rectangle((350, 140, 380, 170), fill=(80, 150, 200, 255), outline=OL, width=3)
    d.rectangle((390, 85, 412, 122), fill=(40, 40, 40, 255), outline=OL, width=4)
    d.polygon([(30, 205), (480, 220), (440, 300), (80, 300)], fill=red, outline=OL, width=6)
    d.line([(50, 240), (465, 245)], fill=white, width=8)
    for i in range(6):
        x = 60 + i * 14
        d.line([(x, 200), (x + 8, 240)], fill=(220, 200, 150, 255), width=3)
    return img.resize((256, 160), Image.LANCZOS)


# ---------------------------------------------------------------------------
# Surface band and parallax background layers (horizontally tileable)
# ---------------------------------------------------------------------------

def wave_layer(color, seed, amp=10, w=512, h=64):
    """Rolling wave strip: water colour below a periodic crest line, foam on top."""
    rng = np.random.default_rng(seed)
    x = np.arange(w) / w
    crest = np.zeros(w)
    for k in (3, 5, 8, 13):
        crest += np.sin(2 * np.pi * (k * x + rng.uniform())) / k
    crest = h * 0.35 + crest * amp
    yy = np.arange(h)[:, None]
    below = yy >= crest[None, :]
    a = below.astype(np.float32)
    rgb = np.zeros((h, w, 3), dtype=np.float32) + np.array(color) / 255.0
    depth = (yy - crest[None, :]) / h
    rgb *= (1 - 0.35 * np.clip(depth, 0, 1))[..., None]
    foam = below & (yy < crest[None, :] + 3)
    rgb[foam] = 1.0
    return _rgba_image(rgb, a)


def sky_gradient(top, bottom, h=64):
    t = np.linspace(0, 1, h)[:, None]
    rgb = (np.array(top) * (1 - t) + np.array(bottom) * t) / 255.0
    rgb = np.repeat(rgb[:, None, :], 4, axis=1)
    return _rgba_image(rgb, np.ones((h, 4)))


def bg_layer(seed, w=1024, h=256, kind="far"):
    """White silhouettes (tinted at runtime) for the parallax background."""
    rng = np.random.default_rng(seed)
    x = np.arange(w) / w
    prof = np.zeros(w)
    if kind == "far":
        for k in (2, 3, 5, 7, 11):
            prof += np.sin(2 * np.pi * (k * x + rng.uniform())) / k ** 0.8
        prof = 0.45 + prof * 0.12
    elif kind == "mid":
        for k in (3, 4, 7, 9, 15, 23):
            prof += np.abs(np.sin(np.pi * (k * x + rng.uniform()))) ** 3 / k ** 0.6
        prof = 0.25 + prof * 0.22
    else:
        for k in (5, 8, 13, 21, 34):
            prof += np.sin(2 * np.pi * (k * x + rng.uniform())) / k ** 0.5
        prof = 0.22 + prof * 0.06
    yy = np.arange(h)[:, None] / h
    height = 1 - yy  # 0 at bottom, 1 at top
    solid = height <= prof[None, :]
    a = solid.astype(np.float32)
    shade = 0.75 + 0.25 * (height / np.maximum(prof[None, :], 1e-3))
    if kind != "far":
        # kelp strands rising from the silhouette
        n = max(6, int(w / (40 if kind == "near" else 70)))
        for _ in range(n):
            x0 = rng.uniform(0, w)
            top = rng.uniform(0.45, 0.95) if kind == "near" else rng.uniform(0.4, 0.8)
            width = rng.uniform(3, 7)
            phase = rng.uniform(0, 6.28)
            ys = np.arange(h)
            xs = x0 + np.sin(ys / 22 + phase) * 10
            for yv, xv in zip(ys, xs):
                if 1 - yv / h > top:
                    continue
                xi0 = int(xv - width) % w
                for xi in range(xi0, xi0 + int(2 * width)):
                    a[yv, xi % w] = 1.0
    rgb = np.repeat(np.clip(shade, 0, 1)[..., None], 3, axis=2) * np.ones((h, w, 3))
    return _rgba_image(rgb, a)


def _rgba_image(rgb, a):
    rgb8 = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
    a8 = (np.clip(a, 0, 1) * 255).astype(np.uint8)
    return Image.fromarray(np.dstack([rgb8, a8]), "RGBA")


# ---------------------------------------------------------------------------
# Floor decorations (non-colliding scenery)
# ---------------------------------------------------------------------------

def weed_tuft(seed=0, palette=((40, 140, 50), (70, 170, 60), (30, 110, 60))):
    img, d = _canvas()
    rng = np.random.default_rng(seed)
    for _ in range(9):
        x0 = 256 + rng.uniform(-90, 90)
        h = rng.uniform(250, 470)
        bend = rng.uniform(-60, 60)
        col = palette[rng.integers(len(palette))]
        pts = []
        for i in range(12):
            t = i / 11
            pts.append((x0 + bend * t * t + math.sin(t * 5 + seed) * 12, 512 - h * t))
        for i in range(len(pts) - 1):
            w = int(26 * (1 - i / 12) + 6)
            d.line([pts[i], pts[i + 1]], fill=OL, width=w + 6)
        for i in range(len(pts) - 1):
            w = int(26 * (1 - i / 12) + 6)
            d.line([pts[i], pts[i + 1]], fill=_rgba(col), width=w)
    return finish(img, 128)


def coral_tuft(seed=0, color=(240, 110, 120)):
    img, d = _canvas()
    rng = np.random.default_rng(seed)

    def branch(x, y, ang, length, width, depth):
        x2 = x + math.cos(ang) * length
        y2 = y - math.sin(ang) * length
        d.line([(x, y), (x2, y2)], fill=OL, width=int(width + 8))
        d.line([(x, y), (x2, y2)], fill=_rgba(color), width=int(width))
        d.ellipse((x2 - width / 2, y2 - width / 2, x2 + width / 2, y2 + width / 2), fill=_rgba(color))
        if depth > 0:
            for da in (-0.45, 0.4):
                branch(x2, y2, ang + da + rng.uniform(-0.2, 0.2), length * 0.72, width * 0.72, depth - 1)
    branch(256, 512, math.pi / 2 + rng.uniform(-0.2, 0.2), 150, 44, 4)
    return finish(img, 128)


def rock_small(seed=0):
    return boulder(seed).resize((128, 128), Image.LANCZOS)


DECOR_DRAW = {
    "weed0": lambda: weed_tuft(1),
    "weed1": lambda: weed_tuft(2, ((150, 120, 40), (120, 140, 40), (90, 120, 30))),
    "coral0": lambda: coral_tuft(3, (240, 110, 120)),
    "coral1": lambda: coral_tuft(4, (170, 120, 230)),
    "coral2": lambda: coral_tuft(5, (250, 190, 60)),
    "rock0": lambda: rock_small(7),
    "rock1": lambda: rock_small(9),
}


OBSTACLE_DRAW = {
    "chest": lambda: [ground(chest())],
    "boulder": lambda: [ground(boulder())],
    "anchor": lambda: [ground(anchor())],
    "barrel": lambda: [ground(barrel())],
    "mine": lambda: [mine()],
    "neptune": lambda: [neptune()],
    "net": lambda: [net()],
    "octopus": lambda: [octopus_frame(i / 6) for i in range(6)],
    "jellyfish": lambda: [jellyfish_frame(i / 6) for i in range(6)],
}

REWARD_DRAW = {"pearl": pearl, "shell": shell, "starfish": starfish, "gem": gem}

BOAT_DRAW = {"sailboat": sailboat, "warship": warship, "trawler": trawler}

PLAYER_FRAMES = 8


def player_frames(name):
    if name == "sub":
        return [sub_frame(i / PLAYER_FRAMES) for i in range(PLAYER_FRAMES)]
    if name == "mermaid":
        return [mermaid_frame(i / PLAYER_FRAMES) for i in range(PLAYER_FRAMES)]
    return [fish_frame(name, i / PLAYER_FRAMES) for i in range(PLAYER_FRAMES)]
