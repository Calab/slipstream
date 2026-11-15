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
    """A closed, barnacle-crusted sea chest (no treasure showing, so it does
    not look like a reward)."""
    img, d = _canvas()
    wood, wdark, iron = (120, 74, 38), (70, 40, 18), (70, 74, 80)
    x0, x1, yb, yt = 80, 432, 448, 268
    # domed lid
    d.chord((x0, yt - 120, x1, yt + 110), 180, 360, fill=_rgba(_shade(wood, 0.9)), outline=OL, width=OW)
    d.line([(x0 + 4, yt - 4), (x1 - 4, yt - 4)], fill=OL, width=10)
    # body
    d.rectangle((x0, yt, x1, yb), fill=_rgba(wood), outline=OL, width=OW)
    for y in range(yt + 45, yb, 45):
        d.line([(x0 + 4, y), (x1 - 4, y)], fill=_rgba(wdark), width=5)
    for k in range(1, 4):  # lid planks
        d.arc((x0 + k * 22, yt - 120 + k * 16, x1 - k * 22, yt + 110), 195, 345, fill=_rgba(wdark), width=4)
    # iron bands over lid and body
    for x in (x0 + 34, x1 - 34):
        d.rectangle((x - 14, yt, x + 14, yb), fill=_rgba(iron), outline=OL, width=4)
        d.line([(x, yt - 2), (x, yt - 98 + abs(x - 256) * 0.35)], fill=OL, width=32)
        d.line([(x, yt - 2), (x, yt - 98 + abs(x - 256) * 0.35)], fill=_rgba(iron), width=22)
        for yy in range(yt + 25, yb - 10, 40):
            d.ellipse((x - 5, yy - 5, x + 5, yy + 5), fill=(150, 150, 155, 255))
    # lock plate
    d.rounded_rectangle((224, yt - 24, 288, yt + 50), radius=8, fill=(110, 95, 60, 255), outline=OL, width=5)
    d.ellipse((248, yt + 2, 264, yt + 20), fill=OL)
    d.rectangle((253, yt + 14, 259, yt + 34), fill=OL)
    # algae and barnacles from years on the sea bed
    rng = np.random.default_rng(12)
    for _ in range(40):
        bx, by = rng.uniform(x0 + 10, x1 - 10), rng.uniform(yt - 70, yb - 10)
        if by < yt and abs(bx - 256) > 150 - (yt - by) * 0.9:
            continue
        r = rng.uniform(5, 12)
        if rng.random() < 0.5:
            d.ellipse((bx - r, by - r, bx + r, by + r), fill=(210, 205, 185, 255), outline=(90, 85, 75, 255), width=3)
            d.ellipse((bx - r / 3, by - r / 3, bx + r / 3, by + r / 3), fill=(60, 55, 50, 255))
        else:
            d.ellipse((bx - r * 1.6, by - r, bx + r * 1.6, by + r), fill=(60, 110, 50, 200))
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


def _shaded_poly(img, pts, light, dark, hl=(-0.3, -0.4)):
    """Fill a polygon with a soft radial gradient (for rounded-looking shapes)."""
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    bbox = (min(xs) - 10, min(ys) - 10, max(xs) + 10, max(ys) + 10)
    layer = radial_layer((S, S), bbox, light, dark, hl=hl, power=1.0)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    layer.putalpha(Image.fromarray(np.minimum(np.asarray(layer)[..., 3], np.asarray(mask))))
    img.alpha_composite(layer)


def _limb(d, pts, width, color):
    d.line(pts, fill=OL, width=width + 10, joint="curve")
    d.line(pts, fill=_rgba(color), width=width, joint="curve")
    for x, y in pts:
        r = width / 2
        d.ellipse((x - r, y - r, x + r, y + r), fill=_rgba(color))


def neptune():
    """Neptune / Poseidon as a full merman: crowned, bearded, trident in hand,
    with a scaled fish tail curling beneath him."""
    img, d = _canvas()
    skin, skin_d, skin_l = (110, 185, 180), (45, 110, 115), (175, 230, 220)
    tail_d, tail_l = (15, 60, 85), (110, 190, 210)
    fin = (90, 200, 200, 255)
    gold = (245, 200, 50, 255)

    # --- fish tail: a tapered curve from the hips down and round to the right
    def bez(t):
        p0, p1, p2, p3 = (232, 300), (215, 420), (300, 470), (395, 430)
        u = 1 - t
        x = u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0]
        y = u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]
        return x, y
    left, right, centre = [], [], []
    n = 24
    for i in range(n + 1):
        t = i / n
        x, y = bez(t)
        x2, y2 = bez(min(1, t + 0.01)) if t < 1 else bez(t)
        x1, y1 = bez(max(0, t - 0.01))
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L, dx / L
        w = 52 * (1 - t) + 14 * t
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
        centre.append((x, y))
    tail_poly = left + right[::-1]
    # tail fin (fluke) at the end
    ex, ey = centre[-1]
    fluke = [(ex - 6, ey - 8), (ex + 60, ey - 75), (ex + 45, ey - 20), (ex + 80, ey + 25),
             (ex + 20, ey + 12), (ex - 6, ey + 8)]
    d.polygon(fluke, fill=fin, outline=OL, width=OW)
    for k in range(1, 4):
        d.line([(ex, ey), (ex + 18 * k, ey - 60 + 26 * k)], fill=_rgba(tail_d), width=3)
    _shaded_poly(img, tail_poly, tail_l, tail_d, hl=(-0.4, -0.6))
    for i in range(2, n - 2, 2):              # scale rows along the tail
        x, y = centre[i]
        w = (52 * (1 - i / n) + 14 * i / n) * 0.75
        for k in (-1, 0, 1):
            d.arc((x - 12 + k * w * 0.6, y - 9, x + 12 + k * w * 0.6, y + 9), 20, 160,
                  fill=_rgba(tail_d), width=3)
    d.polygon(tail_poly, outline=OL, width=OW)

    # --- trident (behind the raised arm)
    d.line([(392, 22), (372, 492)], fill=OL, width=20)
    d.line([(392, 22), (372, 492)], fill=gold, width=11)
    for dx in (-30, 0, 30):
        x = 392 + dx
        d.polygon([(x - 9, 72), (x, 12), (x + 9, 72)], fill=gold, outline=OL, width=4)
    d.rounded_rectangle((356, 66, 428, 84), radius=6, fill=gold, outline=OL, width=4)

    # --- arms
    _limb(d, [(170, 192), (122, 250), (165, 300)], 34, skin)            # hand on hip
    _limb(d, [(298, 192), (352, 165), (388, 120)], 34, skin)            # gripping trident
    d.ellipse((370, 100, 406, 136), fill=_rgba(skin), outline=OL, width=5)

    # --- torso
    torso = [(150, 200), (158, 186), (175, 178), (291, 178), (308, 186), (316, 200),
             (300, 228), (282, 300), (186, 300), (166, 228)]
    _shaded_poly(img, torso, skin_l, skin_d, hl=(-0.3, -0.5))
    d.polygon(torso, outline=OL, width=OW)
    d.arc((180, 195, 235, 245), 20, 160, fill=_rgba(skin_d), width=4)     # chest
    d.arc((230, 195, 285, 245), 20, 160, fill=_rgba(skin_d), width=4)
    for y in (258, 278):                                                   # abs
        d.line([(214, y), (252, y)], fill=_rgba(skin_d), width=3)
    d.line([(233, 250), (233, 292)], fill=_rgba(skin_d), width=3)
    # belt of shells where skin meets scales
    d.rounded_rectangle((180, 290, 290, 314), radius=10, fill=(200, 160, 90, 255), outline=OL, width=5)
    for x in (200, 235, 270):
        d.pieslice((x - 13, 288, x + 13, 314), 180, 360, fill=(255, 190, 170, 255), outline=OL, width=3)

    # --- head, beard and crown
    d.ellipse((193, 72, 273, 172), fill=_rgba(skin_l), outline=OL, width=OW)
    beard = [(190, 128), (198, 175), (214, 225), (233, 250), (252, 225), (268, 175), (276, 128),
             (260, 150), (233, 158), (206, 150)]
    d.polygon(beard, fill=(235, 240, 250, 255), outline=OL, width=OW)
    for x in (214, 226, 240, 252):
        d.line([(x, 165), (x + 4, 220)], fill=(185, 195, 210, 255), width=3)
    d.arc((205, 132, 261, 160), 200, 340, fill=(240, 245, 255, 255), width=10)   # moustache
    for side in (-1, 1):
        ex = 233 + side * 18
        d.ellipse((ex - 9, 112, ex + 9, 128), fill=(255, 255, 255, 255), outline=OL, width=3)
        d.ellipse((ex - 4, 115, ex + 4, 125), fill=(20, 40, 80, 255))
        d.line([(ex - 13, 104), (ex + 12, 101 + side * 2)], fill=(235, 240, 250, 255), width=7)
    d.line([(190, 100), (186, 150)], fill=(235, 240, 250, 255), width=10)          # hair at the sides
    d.line([(276, 100), (280, 150)], fill=(235, 240, 250, 255), width=10)
    crown = [(196, 92), (200, 40), (217, 72), (233, 28), (249, 72), (266, 40), (270, 92)]
    d.polygon(crown, fill=gold, outline=OL, width=OW)
    for x, c in ((217, (220, 30, 60)), (233, (40, 120, 230)), (249, (220, 30, 60))):
        d.ellipse((x - 7, 76, x + 7, 90), fill=c + (255,), outline=OL, width=3)
    return finish(img, OUT)


# ---------------------------------------------------------------------------
# Obstacles that hang down from the surface
# ---------------------------------------------------------------------------

def _vgrad_poly(img, pts, top, bottom, mid=None):
    """Fill a polygon with a top-to-bottom gradient (top, [mid], bottom)."""
    ys = [p[1] for p in pts]
    y0, y1 = min(ys), max(ys)
    t = np.clip((np.arange(S, dtype=np.float32) - y0) / max(y1 - y0, 1), 0, 1)[:, None, None]
    top, bottom = np.array(top, np.float32), np.array(bottom, np.float32)
    if mid is not None:
        mid = np.array(mid, np.float32)
        col = np.where(t < 0.5, top + (mid - top) * (t * 2), mid + (bottom - mid) * (t * 2 - 1))
    else:
        col = top + (bottom - top) * t
    col = np.broadcast_to(col, (S, S, 3))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    arr = np.dstack([np.clip(col, 0, 255), np.asarray(mask, dtype=np.float32)]).astype(np.uint8)
    img.alpha_composite(Image.fromarray(arr, "RGBA"))


def ceiling(img):
    """Shift the artwork up so its highest opaque pixel touches the top edge
    (used for things hanging from the surface)."""
    a = np.asarray(img)[..., 3]
    rows = np.where(a.max(axis=1) > 40)[0]
    if not len(rows):
        return img
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, -rows[0]))
    return out


def iceberg(seed=31):
    """The underwater part of an iceberg: flat at the waterline, jagged below."""
    img, d = _canvas()
    rng = np.random.default_rng(seed)
    left = [(26, 0), (18, 60)]
    right = [(486, 0), (494, 70)]
    for i in range(1, 7):                       # jagged sides narrowing downwards
        t = i / 7
        y = 60 + t * 330
        left.append((18 + 170 * t ** 1.3 + rng.uniform(-22, 22), y + rng.uniform(-15, 15)))
        right.append((494 - 150 * t ** 1.2 + rng.uniform(-22, 22), y + rng.uniform(-15, 15)))
    tip = [(300 + rng.uniform(-30, 30), 470), (250, 430), (220, 500), (190, 440)]
    poly = left + tip[::-1] + right[::-1]
    _vgrad_poly(img, poly, (250, 254, 255), (60, 120, 180), mid=(185, 220, 240))
    # facets: lighter and darker planes, blended on (drawing translucent
    # shapes directly would punch see-through holes instead)
    facets = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    fd = ImageDraw.Draw(facets)
    for _ in range(14):
        x0, y0 = rng.uniform(60, 450), rng.uniform(20, 340)
        pts = [(x0, y0), (x0 + rng.uniform(-70, 70), y0 + rng.uniform(40, 110)),
               (x0 + rng.uniform(-70, 70), y0 + rng.uniform(40, 110))]
        shade = (255, 255, 255, 70) if rng.random() < 0.5 else (40, 90, 150, 55)
        fd.polygon(pts, fill=shade)
    img.alpha_composite(facets)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).polygon(poly, fill=255)
    img.putalpha(Image.fromarray(np.minimum(np.asarray(img)[..., 3], np.asarray(mask))))
    d = ImageDraw.Draw(img)
    d.rectangle((26, 0, 486, 10), fill=(255, 255, 255, 230))       # bright waterline
    d.polygon(poly, outline=(30, 70, 110, 255), width=OW)
    return ceiling(finish(img, OUT))


def hook():
    """A fishing hook on a line, hanging from a bobber at the surface."""
    img, d = _canvas()
    cx = 256
    # bobber at the surface
    d.ellipse((cx - 26, 0, cx + 26, 52), fill=(230, 40, 40, 255), outline=OL, width=5)
    d.chord((cx - 26, 0, cx + 26, 52), 0, 180, fill=(250, 250, 250, 255), outline=OL, width=5)
    # line
    d.line([(cx, 52), (cx, 352)], fill=(30, 30, 30, 255), width=7)
    d.line([(cx, 52), (cx, 352)], fill=(220, 225, 230, 255), width=3)
    # eye, shank and bend
    steel, dark = (205, 212, 222, 255), (110, 118, 130, 255)
    d.ellipse((cx - 16, 340, cx + 16, 372), outline=OL, width=14)
    d.ellipse((cx - 16, 340, cx + 16, 372), outline=steel, width=7)
    d.line([(cx, 372), (cx, 452)], fill=OL, width=22)
    d.line([(cx, 372), (cx, 452)], fill=steel, width=12)
    d.arc((cx - 92, 392, cx + 8, 492), 0, 180, fill=OL, width=22)
    d.arc((cx - 92, 392, cx + 8, 492), 0, 180, fill=steel, width=12)
    # point and barb
    d.line([(cx - 88, 442), (cx - 88, 400)], fill=OL, width=20)
    d.line([(cx - 88, 442), (cx - 88, 400)], fill=steel, width=10)
    d.polygon([(cx - 98, 404), (cx - 88, 372), (cx - 78, 404)], fill=steel, outline=OL, width=4)
    d.polygon([(cx - 88, 418), (cx - 64, 432), (cx - 86, 432)], fill=dark, outline=OL, width=3)
    d.line([(cx - 4, 380), (cx - 4, 448)], fill=(250, 252, 255, 255), width=3)   # highlight
    return ceiling(finish(img, OUT))


def galleon():
    """An old galleon's hull from the side, as seen from under the water: the
    waterline along the top, the bow sweeping down on the left to a long keel,
    and the stern post and rudder on the right."""
    img, _ = _canvas()
    rng = np.random.default_rng(41)
    wdark = (55, 32, 15)
    copper, copper_d = (75, 155, 128), (28, 82, 72)
    keel_y = 232
    # hull outline: bow curve (left), keel, stern post (right)
    bow = []
    for i in range(13):
        t = i / 12
        bow.append((12 + 120 * (1 - math.cos(t * math.pi / 2)), keel_y * math.sin(t * math.pi / 2)))
    hull = bow + [(440, keel_y), (462, 150), (474, 0)]
    _vgrad_poly(img, hull, (150, 96, 52), (90, 52, 24))
    # copper sheathing below the old waterline
    copper_poly = [(14 + 120 * (1 - math.cos(math.asin(105 / keel_y))), 105)] + \
                  [p for p in hull if p[1] > 105] + [(466, 105)]
    _vgrad_poly(img, copper_poly, copper, copper_d)
    d = ImageDraw.Draw(img)
    # planks running along the hull (clipped to the hull afterwards)
    planks = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    pd = ImageDraw.Draw(planks)
    for y in range(26, keel_y, 26):
        pd.line([(0, y), (S, y + 4)], fill=(60, 35, 15, 150) if y < 105 else (20, 60, 52, 150), width=3)
        for x in range(int(rng.uniform(20, 90)), S, 110):       # butt joints
            pd.line([(x, y - 26), (x, y)], fill=(60, 35, 15, 90), width=2)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).polygon(hull, fill=255)
    planks.putalpha(Image.fromarray(np.minimum(np.asarray(planks)[..., 3], np.asarray(mask))))
    img.alpha_composite(planks)
    # brass rubbing strake at the waterline edge of the copper
    d.line([(20, 105), (468, 105)], fill=(205, 170, 80, 255), width=7)
    # keel along the bottom, stern post and rudder
    d.rectangle((126, keel_y - 6, 446, keel_y + 12), fill=_rgba(wdark), outline=OL, width=4)
    d.line([(456, 0), (444, keel_y + 6)], fill=OL, width=16)
    d.line([(456, 0), (444, keel_y + 6)], fill=_rgba(wdark), width=9)
    rudder = [(462, 20), (500, 34), (494, keel_y), (446, keel_y + 8), (452, 20)]
    d.polygon(rudder, fill=(80, 48, 22, 255), outline=OL, width=5)
    for y in (70, 130, 190):                                     # rudder hinges
        d.line([(446, y), (480, y + 4)], fill=(200, 165, 80, 255), width=6)
    # barnacles and trailing weed
    for _ in range(28):
        x, y = rng.uniform(110, 430), rng.uniform(118, keel_y - 12)
        r = rng.uniform(3, 7)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(215, 210, 190, 255), outline=(90, 85, 75, 255), width=2)
    for _ in range(10):
        x = rng.uniform(110, 420)
        y0 = keel_y + 10
        pts = [(x + math.sin(k * 0.8 + x) * 6, y0 + k * 9) for k in range(int(rng.uniform(4, 9)))]
        d.line(pts, fill=(50, 120, 50, 235), width=6)
    d.polygon(hull, outline=OL, width=OW)
    return ceiling(finish(img, OUT))


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


def glow():
    """Soft, bright radial glow with a few rays (white; tinted per reward)."""
    size = 256
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    dx, dy = xx - size / 2 + 0.5, yy - size / 2 + 0.5
    r = np.hypot(dx, dy) / (size / 2)
    ang = np.arctan2(dy, dx)
    core = np.clip(1 - r, 0, 1) ** 2.2
    rays = np.clip(1 - r, 0, 1) ** 1.5 * (0.5 + 0.5 * np.cos(ang * 8)) ** 6 * 0.6
    a = np.clip(core + rays, 0, 1)
    arr = np.zeros((size, size, 4), dtype=np.uint8)
    arr[..., :3] = 255
    arr[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def soft():
    """Plain soft white disc (light showing through wall openings)."""
    size = 128
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    r = np.hypot(xx - size / 2 + 0.5, yy - size / 2 + 0.5) / (size / 2)
    a = np.clip(1 - r, 0, 1) ** 0.7
    arr = np.zeros((size, size, 4), dtype=np.uint8)
    arr[..., :3] = 255
    arr[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def halo():
    """Soft glow ring (white; tinted red at runtime) behind obstacles."""
    size = 128
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    r = np.hypot(xx - size / 2 + 0.5, yy - size / 2 + 0.5) / (size / 2)
    a = np.clip(1 - r, 0, 1) ** 1.2 * np.clip(r * 2.2, 0, 1)
    arr = np.zeros((size, size, 4), dtype=np.uint8)
    arr[..., :3] = 255
    arr[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def app_icon():
    """Program icon: the clownfish on a round sea-blue badge."""
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.alpha_composite(radial_layer((S, S), (8, 8, S - 8, S - 8), (90, 200, 235), (15, 70, 130),
                                     hl=(-0.3, -0.4)))
    ImageDraw.Draw(img).ellipse((8, 8, S - 8, S - 8), outline=(255, 255, 255, 255), width=14)
    fish = fish_frame("fish_clown", 0.18).resize((400, 400), Image.LANCZOS)
    img.alpha_composite(fish, (56, 62))
    return img.resize((256, 256), Image.LANCZOS)


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

DECOR_OUT = 256


def weed_tuft(seed=0, palette=((40, 140, 50), (70, 170, 60), (30, 110, 60)), blades=9, width=26):
    img, d = _canvas()
    rng = np.random.default_rng(seed)
    for _ in range(blades):
        x0 = 256 + rng.uniform(-100, 100)
        h = rng.uniform(220, 480)
        bend = rng.uniform(-80, 80)
        col = palette[rng.integers(len(palette))]
        pts = []
        for i in range(12):
            t = i / 11
            pts.append((x0 + bend * t * t + math.sin(t * 5 + seed) * 12, 512 - h * t))
        for i in range(len(pts) - 1):
            w = int(width * (1 - i / 12) + 6)
            d.line([pts[i], pts[i + 1]], fill=OL, width=w + 6)
        for i in range(len(pts) - 1):
            w = int(width * (1 - i / 12) + 6)
            d.line([pts[i], pts[i + 1]], fill=_rgba(col), width=w)
    return finish(ground(img), DECOR_OUT)


def sea_grass(seed=0, palette=((90, 170, 70), (60, 140, 60), (120, 180, 80))):
    return weed_tuft(seed, palette, blades=26, width=9)


def coral_tuft(seed=0, color=(240, 110, 120), depth=4, spread=0.45):
    img, d = _canvas()
    rng = np.random.default_rng(seed)
    tip = _shade(color, 1.25)

    def branch(x, y, ang, length, width, depth):
        x2 = x + math.cos(ang) * length
        y2 = y - math.sin(ang) * length
        d.line([(x, y), (x2, y2)], fill=OL, width=int(width + 8))
        d.line([(x, y), (x2, y2)], fill=_rgba(color), width=int(width))
        d.ellipse((x2 - width / 2, y2 - width / 2, x2 + width / 2, y2 + width / 2),
                  fill=_rgba(tip if depth == 0 else color))
        if depth > 0:
            for da in (-spread, spread * 0.9):
                branch(x2, y2, ang + da + rng.uniform(-0.25, 0.25), length * rng.uniform(0.65, 0.8),
                       width * 0.72, depth - 1)
    for k in range(rng.integers(1, 3)):
        branch(256 + rng.uniform(-60, 60), 512, math.pi / 2 + rng.uniform(-0.3, 0.3), 140, 42, depth)
    return finish(ground(img), DECOR_OUT)


def sea_fan(seed=0, color=(200, 70, 150)):
    """Gorgonian: a flat, lacy fan on a short stem."""
    img, d = _canvas()
    rng = np.random.default_rng(seed)
    cx, base = 256, 500
    fan = [(cx, base - 40)]
    for i in range(25):
        a = math.pi * (0.08 + 0.84 * i / 24)
        r = 300 * rng.uniform(0.88, 1.0)
        fan.append((cx + math.cos(a) * r * 0.95, base - 40 - math.sin(a) * r))
    d.polygon(fan, fill=_rgba(color, 120))
    # lattice: radiating branches plus cross links
    for i in range(1, 25, 2):
        x, y = fan[i]
        d.line([(cx, base - 40), (x, y)], fill=_rgba(color), width=7)
    for r in range(60, 300, 34):
        pts = [(cx + math.cos(math.pi * (0.08 + 0.84 * j / 30)) * r * 0.95,
                base - 40 - math.sin(math.pi * (0.08 + 0.84 * j / 30)) * r) for j in range(31)]
        d.line(pts, fill=_rgba(_shade(color, 1.2)), width=4)
    d.polygon(fan, outline=OL, width=5)
    d.line([(cx, base - 40), (cx, 512)], fill=OL, width=24)
    d.line([(cx, base - 40), (cx, 512)], fill=_rgba(_shade(color, 0.7)), width=14)
    return finish(ground(img), DECOR_OUT)


def brain_coral(seed=0, color=(200, 180, 110)):
    img, d = _canvas()
    bbox = (40, 250, 472, 520 + 250)
    layer = radial_layer((S, S), bbox, _shade(color, 1.3), _shade(color, 0.6), hl=(-0.2, -0.6))
    img.alpha_composite(layer)
    # meandering grooves
    rng = np.random.default_rng(seed)
    for row in range(8):
        y0 = 280 + row * 28
        pts = []
        for i in range(60):
            x = 50 + i * 7
            y = y0 + math.sin(i * 0.5 + rng.uniform(0, 0.3) + row) * 9
            pts.append((x, y))
        d.line(pts, fill=_rgba(_shade(color, 0.55)), width=5)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse(bbox, fill=255)
    a = np.minimum(np.asarray(img)[..., 3], np.asarray(mask))
    img.putalpha(Image.fromarray(a))
    d = ImageDraw.Draw(img)
    d.chord(bbox, 180, 360, outline=OL, width=OW)
    return finish(ground(img), DECOR_OUT)


def tube_sponge(seed=0, color=(230, 120, 60)):
    img, d = _canvas()
    rng = np.random.default_rng(seed)
    tubes = sorted([(rng.uniform(120, 390), rng.uniform(200, 440), rng.uniform(34, 52)) for _ in range(5)],
                   key=lambda t: -t[1])
    for x, h, w in tubes:
        top = 512 - h
        c = _shade(color, rng.uniform(0.85, 1.15))
        d.rounded_rectangle((x - w, top, x + w, 520), radius=int(w), fill=_rgba(c), outline=OL, width=OW)
        d.line([(x - w * 0.5, top + 30), (x - w * 0.5, 500)], fill=_rgba(_shade(c, 1.2)), width=6)
        d.ellipse((x - w * 0.8, top + 4, x + w * 0.8, top + 30), fill=_rgba(_shade(c, 0.35)), outline=OL, width=4)
    return finish(ground(img), DECOR_OUT)


def anemone(seed=0, color=(255, 130, 170), stem=(200, 90, 60)):
    img, d = _canvas()
    rng = np.random.default_rng(seed)
    cx = 256
    d.rounded_rectangle((cx - 70, 330, cx + 70, 520), radius=40, fill=_rgba(stem), outline=OL, width=OW)
    for k in range(26):
        a = math.pi * (0.05 + 0.9 * k / 25) + rng.uniform(-0.05, 0.05)
        L = rng.uniform(150, 240)
        pts = []
        for i in range(10):
            t = i / 9
            r = L * t
            wig = math.sin(t * 4 + k) * 18 * t
            pts.append((cx + math.cos(a) * (60 + r) * 0.9 + wig, 345 - math.sin(a) * (20 + r)))
        d.line(pts, fill=OL, width=20)
        d.line(pts, fill=_rgba(color), width=12)
        x, y = pts[-1]
        d.ellipse((x - 10, y - 10, x + 10, y + 10), fill=_rgba(_shade(color, 1.3)), outline=OL, width=3)
    return finish(ground(img), DECOR_OUT)


def kelp_tall(seed=0, color=(150, 120, 40)):
    """A tall golden kelp stalk with alternating blades and gas bladders."""
    img, d = _canvas()
    rng = np.random.default_rng(seed)
    for stalk in range(2):
        x0 = 256 + (stalk - 0.5) * rng.uniform(50, 110)
        pts = [(x0 + math.sin(t / 60 + stalk + seed) * 26, 512 - t) for t in range(0, 500, 20)]
        d.line(pts, fill=OL, width=16)
        d.line(pts, fill=_rgba(_shade(color, 0.8)), width=9)
        for i, (x, y) in enumerate(pts[2::2]):
            side = 1 if (i + stalk) % 2 else -1
            L = rng.uniform(70, 120)
            leaf = [(x, y), (x + side * L * 0.45, y - 62), (x + side * L, y - 78),
                    (x + side * L * 0.8, y - 30), (x + side * L * 0.35, y - 4)]
            d.polygon(leaf, fill=_rgba(_shade(color, rng.uniform(0.9, 1.25))), outline=OL, width=4)
            d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=_rgba(_shade(color, 1.35)), outline=OL, width=3)
    return finish(ground(img), DECOR_OUT)


def rock_small(seed=0):
    return ground(boulder(seed)).resize((DECOR_OUT, DECOR_OUT), Image.LANCZOS)


DECOR_DRAW = {
    "weed0": lambda: weed_tuft(1),
    "weed1": lambda: weed_tuft(2, ((150, 120, 40), (120, 140, 40), (90, 120, 30))),
    "weed2": lambda: weed_tuft(6, ((60, 90, 70), (80, 110, 80), (50, 80, 90))),
    "weed3": lambda: weed_tuft(8, ((40, 160, 120), (60, 180, 100), (30, 130, 110)), blades=12),
    "grass0": lambda: sea_grass(10),
    "grass1": lambda: sea_grass(11, ((140, 150, 70), (110, 130, 60), (160, 160, 90))),
    "coral0": lambda: coral_tuft(3, (240, 110, 120)),
    "coral1": lambda: coral_tuft(4, (170, 120, 230)),
    "coral2": lambda: coral_tuft(5, (250, 190, 60)),
    "coral3": lambda: coral_tuft(13, (255, 120, 60), depth=5, spread=0.35),
    "coral4": lambda: coral_tuft(14, (220, 60, 70), depth=3, spread=0.6),
    "coral5": lambda: coral_tuft(15, (220, 235, 250), depth=5, spread=0.5),
    "fan0": lambda: sea_fan(16, (200, 70, 150)),
    "fan1": lambda: sea_fan(17, (240, 160, 60)),
    "fan2": lambda: sea_fan(18, (150, 110, 200)),
    "brain0": lambda: brain_coral(19, (200, 180, 110)),
    "brain1": lambda: brain_coral(20, (150, 200, 120)),
    "sponge0": lambda: tube_sponge(21, (230, 120, 60)),
    "sponge1": lambda: tube_sponge(22, (170, 90, 200)),
    "sponge2": lambda: tube_sponge(23, (220, 200, 90)),
    "anemone0": lambda: anemone(24, (255, 130, 170)),
    "anemone1": lambda: anemone(25, (120, 230, 200), (60, 120, 140)),
    "anemone2": lambda: anemone(26, (255, 200, 90), (200, 80, 60)),
    "kelp0": lambda: kelp_tall(27, (150, 120, 40)),
    "kelp1": lambda: kelp_tall(28, (90, 140, 50)),
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
    "iceberg": lambda: [iceberg()],
    "hook": lambda: [hook()],
    "galleon": lambda: [galleon()],
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
