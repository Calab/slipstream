#!/usr/bin/env python3
"""Build docs/architecture.odt: the architecture overview with its diagrams.

    python tools/build_docs.py

The six diagrams are drawn here as SVG (no browser or extra packages needed),
then packed with formatted text into an OpenDocument text file that opens in
LibreOffice, Word and other ODF-aware editors.  If ImageMagick is installed a
PNG copy of each diagram is embedded as well, for programs without SVG support.

The same content, with Mermaid diagrams, is in docs/architecture.md; keep the
two in step when the game changes.
"""

import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "architecture.odt"

# --------------------------------------------------------------------------
# Diagram drawing
# --------------------------------------------------------------------------
FONT = "DejaVu Sans, Liberation Sans, Arial, sans-serif"
FS = 13                     # font size (px)
CHAR_W = 7.3                # average character width at FS (estimate)
LINE_H = 17
INK = "#0f2a33"
EDGE = "#4a646d"
STYLES = {                  # fill, stroke
    "box": ("#e3f1f4", "#0b7285"),
    "dec": ("#ffffff", "#0b7285"),
    "hit": ("#fbe3dc", "#c8553d"),
    "good": ("#e1f2e6", "#2f7d4f"),
    "muted": ("#f1f4f5", "#8aa0a6"),
    "key": ("#0b7285", "#0b7285"),
}


def text_w(s):
    return len(s) * CHAR_W


class Node:
    def __init__(self, d, key, text, c, r, kind="box", shape=None):
        self.key, self.kind = key, kind
        self.lines = text.split("\n")
        self.shape = shape or ("hex" if kind == "dec" else "rect")
        self.x = d.margin + c * d.col_w + d.col_w / 2
        self.y = d.margin + r * d.row_h + d.row_h / 2
        if self.shape == "dot":
            self.w = self.h = 18
        else:
            # the first line is bold on multi-line boxes, and bold is wider
            bold = len(self.lines) > 1 and kind != "dec"
            widths = [text_w(s) * (1.12 if bold and i == 0 else 1.0) for i, s in enumerate(self.lines)]
            self.w = max(80, max(widths) + 26)
            if self.shape == "hex":
                self.w += 28
            self.h = len(self.lines) * LINE_H + 16

    @property
    def top(self):
        return self.y - self.h / 2

    @property
    def bottom(self):
        return self.y + self.h / 2

    @property
    def left(self):
        return self.x - self.w / 2

    @property
    def right(self):
        return self.x + self.w / 2


class Diagram:
    def __init__(self, cols, rows, col_w=170, row_h=74, margin=24):
        self.cols, self.rows = cols, rows
        self.col_w, self.row_h, self.margin = col_w, row_h, margin
        self.nodes = {}
        self.edges = []
        self.groups = []
        self.notes = []

    # building
    def n(self, key, text, c, r, kind="box", shape=None):
        self.nodes[key] = Node(self, key, text, c, r, kind, shape)

    def e(self, a, b, label="", **kw):
        self.edges.append((a, b, label, kw))

    def group(self, label, c0, r0, c1, r1):
        """Background box from the top-left of cell (c0, r0) to the
        bottom-right of cell (c1, r1)."""
        self.groups.append((label, c0, r0, c1, r1))

    # drawing
    @property
    def width(self):
        return self.margin * 2 + self.cols * self.col_w

    @property
    def height(self):
        return self.margin * 2 + self.rows * self.row_h

    def _label(self, out, x, y, s, anchor="middle"):
        w = text_w(s) + 8
        rx = x - w / 2 if anchor == "middle" else (x if anchor == "start" else x - w)
        out.append(f'<rect x="{rx:.1f}" y="{y - 11:.1f}" width="{w:.1f}" height="16" rx="3" fill="#ffffff" fill-opacity="0.92"/>')
        tx = x if anchor == "middle" else (x + 4 if anchor == "start" else x - 4)
        out.append(f'<text x="{tx:.1f}" y="{y + 1:.1f}" font-size="{FS - 1.5}" fill="{EDGE}" '
                   f'text-anchor="{anchor}" font-style="italic">{escape(s)}</text>')

    def _edge(self, out, labels, a, b, label, kw):
        A, B = self.nodes[a], self.nodes[b]
        sx, ex, off = kw.get("sx", 0), kw.get("ex", 0), kw.get("off", 0)
        route = kw.get("route")
        dash = ' stroke-dasharray="5 4"' if kw.get("dashed") else ""
        pts, lab = None, None
        if route in ("left", "right"):
            ys = (min(A.y, B.y) - 1, max(A.y, B.y) + 1)
            span = [n for n in self.nodes.values() if ys[0] <= n.y <= ys[1]]
            gap = 22 + kw.get("extra", 0)
            if route == "left":
                X = min(n.left for n in span) - gap
                x0, x1 = A.left, B.left
            else:
                X = max(n.right for n in span) + gap
                x0, x1 = A.right, B.right
            y0, y1 = A.y + off, B.y + kw.get("eoff", 0)
            pts = [(x0, y0), (X, y0), (X, y1), (x1, y1)]
            lab = (X + (-6 if route == "left" else 6), (y0 + y1) / 2, "end" if route == "left" else "start")
        elif route == "hv":
            right = B.x > A.x
            x0 = A.right if right else A.left
            y0 = A.y + off
            down = B.y > A.y
            y1 = B.top if down else B.bottom
            pts = [(x0, y0), (B.x + ex, y0), (B.x + ex, y1)]
            lab = ((x0 + B.x + ex) / 2, y0 - 9, "middle")
        elif abs(A.y - B.y) < 1:
            right = B.x > A.x
            x0, x1 = (A.right, B.left) if right else (A.left, B.right)
            pts = [(x0, A.y + off), (x1, A.y + off)]
            lab = ((x0 + x1) / 2, A.y + off - 10 if off <= 0 else A.y + off + 14, "middle")
        else:
            down = B.y > A.y
            y0 = A.bottom if down else A.top
            y1 = B.top if down else B.bottom
            x0, x1 = A.x + sx, B.x + ex
            if abs(x0 - x1) < 1:
                pts = [(x0, y0), (x1, y1)]
                lab = (x0 + 6, (y0 + y1) / 2 + 4, "start")
            else:
                if kw.get("bend") == "dst":
                    my = y1 - (16 if down else -16)
                else:
                    my = y0 + (16 if down else -16) if kw.get("bend") == "src" else (y0 + y1) / 2
                pts = [(x0, y0), (x0, my), (x1, my), (x1, y1)]
                lab = (x1 + 6, (my + y1) / 2 + 4, "start")
        d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        out.append(f'<polyline points="{d}" fill="none" stroke="{EDGE}" stroke-width="1.4"{dash} '
                   f'stroke-linejoin="round" marker-end="url(#arrow)"/>')
        if label:
            if "lab" in kw:
                lab = kw["lab"]
            labels.append((lab, label))

    def _node(self, out, n):
        fill, stroke = STYLES[n.kind]
        if n.shape == "dot":
            out.append(f'<circle cx="{n.x}" cy="{n.y}" r="8" fill="{INK}"/>')
            return
        if n.shape == "hex":
            k = 14
            p = [(n.left, n.y), (n.left + k, n.top), (n.right - k, n.top), (n.right, n.y),
                 (n.right - k, n.bottom), (n.left + k, n.bottom)]
            out.append('<polygon points="%s" fill="%s" stroke="%s" stroke-width="1.6"/>'
                       % (" ".join(f"{x:.1f},{y:.1f}" for x, y in p), fill, stroke))
        else:
            rx = n.h / 2 if n.shape == "pill" else 6
            out.append(f'<rect x="{n.left:.1f}" y="{n.top:.1f}" width="{n.w:.1f}" height="{n.h:.1f}" '
                       f'rx="{rx:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
        color = "#ffffff" if n.kind == "key" else INK
        y = n.y - (len(n.lines) - 1) * LINE_H / 2 + 4.5
        for i, line in enumerate(n.lines):
            weight = ' font-weight="bold"' if i == 0 and n.kind != "dec" and len(n.lines) > 1 else ""
            out.append(f'<text x="{n.x:.1f}" y="{y + i * LINE_H:.1f}" font-size="{FS}" fill="{color}" '
                       f'text-anchor="middle"{weight}>{escape(line)}</text>')

    def svg(self):
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" '
               f'viewBox="0 0 {self.width} {self.height}" font-family="{FONT}">',
               '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
               f'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{EDGE}"/>'
               '</marker></defs>',
               f'<rect width="100%" height="100%" fill="#ffffff"/>']
        for label, c0, r0, c1, r1 in self.groups:
            x0 = self.margin + c0 * self.col_w + 6
            y0 = self.margin + r0 * self.row_h + 2
            x1 = self.margin + (c1 + 1) * self.col_w - 6
            y1 = self.margin + (r1 + 1) * self.row_h - 2
            out.append(f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" rx="10" '
                       'fill="#f4f8f9" stroke="#b9cfd4" stroke-width="1.2" stroke-dasharray="6 4"/>')
            out.append(f'<text x="{x0 + 12}" y="{y0 + 18}" font-size="{FS - 1}" font-weight="bold" '
                       f'fill="#0b7285" letter-spacing="0.5">{escape(label)}</text>')
        labels = []
        for a, b, label, kw in self.edges:
            self._edge(out, labels, a, b, label, kw)
        for n in self.nodes.values():
            self._node(out, n)
        for (x, y, anchor), s in labels:
            self._label(out, x, y, s, anchor)
        out.append("</svg>")
        return "\n".join(out)


def module_map():
    d = Diagram(5, 8, col_w=162, row_h=80)
    d.n("main", "main.py\nparse arguments", 2, 0)
    d.n("app", "SlipstreamApp\nstate machine + rules", 2, 1, "key")
    d.n("themes", "themes.py\ntheme tables", 0, 1, "muted")
    d.n("config", "config.py\ntuning constants", 4, 1, "muted")
    d.n("save", "SaveData\nsave.json", 0, 2)
    d.n("snd", "SoundManager\neffects + music", 1, 2)
    d.n("res", "Resources\ncustom/ or assets/", 3, 2)
    d.n("ui", "UI overlays\nHUD, menus, panels\ntouch, wave band", 4, 2)
    d.n("gen", "AssetBuilder\ngenerators", 3, 3)
    d.n("world", "World\nmoves things, reports collisions", 2, 4.15, "key")
    d.n("env", "Environment\nfloor, cliffs, fog", 0, 5.1)
    d.n("player", "Player\nmovement", 1, 5.1)
    d.n("trench", "Trench\ncliff drift", 2, 5.1)
    d.n("aim", "AimHelper\nring + dots", 3, 5.1)
    d.n("fx", "Bubbles", 4, 5.1)
    d.n("course", "Course\nendless course", 1, 6.1)
    d.n("markers", "DistanceMarkers\nLast Run / Best", 3, 6.1)
    d.n("walls", "WallFactory → Wall", 0.5, 7.1)
    d.n("obs", "Obstacle, Reward", 1.6, 7.1)
    d.group("ONE PER THEME", 0, 3.7, 4, 7.55)
    d.e("main", "app")
    d.e("themes", "app", dashed=True)
    d.e("config", "app", dashed=True)
    for k in ("save", "snd", "res", "ui"):
        d.e("app", k, bend="src")
    d.e("res", "gen")
    d.e("app", "world", "creates")
    d.e("course", "walls", bend="src")
    d.e("course", "obs", bend="src")
    return d


def startup():
    d = Diagram(3, 14, col_w=230, row_h=62)
    d.n("A", "main.py parses --width --height\n--fullscreen --fps --reset-save", 1, 0)
    d.n("B", "SaveData loads save.json\n(defaults if missing)", 1, 1)
    d.n("C", "configure_panda: window size\nand position from the save", 1, 2)
    d.n("D", "ShowBase opens the window\nfont, window-event watcher", 1, 3)
    d.n("E", "--reset-save?", 1, 4, "dec")
    d.n("E1", "clear records", 2, 4, "hit")
    d.n("F", "AssetBuilder", 1, 5)
    d.n("G", "version.json matches\nASSET_VERSION?", 1, 6, "dec")
    d.n("G1", "delete generated folders\n(custom/ untouched)", 2, 6, "hit")
    d.n("H", "generate missing files only\n“Generating sea life… i/n”", 1, 7)
    d.n("I", "Resources, window icon,\nSoundManager", 1, 8)
    d.n("J", "bind keys: held keys → self.keys\npressed keys → on_* handlers", 1, 9)
    d.n("K", "create UI overlays", 1, 10)
    d.n("L", "load_theme(last theme)\nbuilds World, band, music", 1, 11)
    d.n("M", "to_menu()", 1, 12)
    d.n("N", "taskMgr.add(_task)\nruns every frame", 1, 13, "key")
    for a, b in ("AB", "BC", "CD", "DE"):
        d.e(a, b)
    d.e("E", "E1", "yes")
    d.e("E", "F", "no")
    d.e("E1", "F", bend="dst", ex=40)
    d.e("F", "G")
    d.e("G", "G1", "no")
    d.e("G", "H", "yes")
    d.e("G1", "H", bend="dst", ex=40)
    for a, b in ("HI", "IJ", "JK", "KL", "LM", "MN"):
        d.e(a, b)
    return d


def states():
    d = Diagram(3, 4.6, col_w=250, row_h=92)
    d.n("start", "", 1, 0, shape="dot")
    d.n("about", "about\nAbout page", 2, 1, shape="pill")
    d.n("menu", "menu\ntitle screen", 1, 1, "key", shape="pill")
    d.n("quit", "quit\nsave + exit", 0, 1, "muted", shape="pill")
    d.n("play", "play\nrun in progress", 1, 2.4, "good", shape="pill")
    d.n("paused", "paused\nworld frozen", 2, 2.4, shape="pill")
    d.n("gameover", "gameover\nhealth reached 0", 1, 3.8, "hit", shape="pill")
    d.e("start", "menu", "launch")
    d.e("menu", "about", "?", off=-8)
    d.e("about", "menu", "? / Space / Esc", off=8)
    d.e("menu", "quit", "Q / Esc")
    d.e("menu", "play", "Space", sx=-30, ex=-30)
    d.e("play", "menu", "Esc", sx=30, ex=30)
    d.e("play", "paused", "P", off=-8)
    d.e("paused", "play", "P / Space", off=8)
    d.e("paused", "menu", "Esc", ex=50, bend="dst")
    d.e("play", "gameover", "health ≤ 0")
    d.e("gameover", "play", "Space", route="left")
    return d


def frame():
    d = Diagram(5, 16.2, col_w=182, row_h=64)
    d.n("T", "_task(dt)\ndt capped at 1/20 s", 2, 0, "key")
    d.n("T1", "update sound, HUD, menu, wave band", 2, 1)
    d.n("S", "state?", 2, 2, "dec")
    d.n("att", "menu / about\nattract mode", 0, 3)
    d.n("pau", "paused\nnothing moves", 1, 3, "muted")
    d.n("ply", "play\nread held keys", 2, 3, "good")
    d.n("gov", "gameover\ndrift, no collisions", 3.4, 3)
    d.n("P1", "run_time += dt\nspeed = forward_speed(run_time)", 2, 4)
    d.n("W1", "Player.update: steer, sink when idle,\nclamp to trench, floor bounce", 2, 5.45)
    d.n("W2", "Course.fill(y, difficulty)\ndifficulty = y ÷ 4000, max 1", 2, 6.45)
    d.n("W3", "objects within 4 units of the fish:\nreward · hit (once each) · passed", 2, 7.45)
    d.n("W4", "Course.update: animate, despawn 25 behind\nmarkers, bubbles, camera, aim helper", 2, 8.45)
    d.group("WORLD.UPDATE  (returns events and hits)", 0.55, 4.9, 3.45, 8.95)
    d.n("R0", "for each event and hit", 2, 9.6, "dec")
    d.n("r1", "floor\nbounce sound", 0, 10.9)
    d.n("r2", "side cliff\n−5, 1 s cooldown", 1, 10.9, "hit")
    d.n("r3", "hit\n−25 wall, −14 obstacle\nthen 0.9 s safe", 2, 10.9, "hit")
    d.n("r4", "reward\n+6 to +30 health", 3, 10.9, "good")
    d.n("r5", "passed\ncounters, music\nstage = passed ÷ 10", 4, 10.9)
    d.n("R4", "regenerate 0.6 health/s (max 100)", 2, 12.2)
    d.n("R5", "banners: passed last run · NEW BEST TIME\nupdate the HUD", 2, 13.2)
    d.n("R7", "health ≤ 0?", 2, 14.2, "dec")
    d.n("GO", "game_over()\nsave run, show panel", 3.5, 15.2, "hit")
    d.n("NX", "next frame", 1, 15.2, "muted")
    d.e("T", "T1")
    d.e("T1", "S")
    for k in ("att", "pau", "ply", "gov"):
        d.e("S", k, bend="src")
    d.e("ply", "P1")
    d.e("P1", "W1")
    d.e("W1", "W2")
    d.e("W2", "W3")
    d.e("W3", "W4")
    d.e("W4", "R0")
    for k in ("r1", "r2", "r3", "r4", "r5"):
        d.e("R0", k, bend="src")
    for k in ("r1", "r2", "r3", "r4", "r5"):
        d.e(k, "R4", bend="dst")
    d.e("R4", "R5")
    d.e("R5", "R7")
    d.e("R7", "GO", "yes", bend="src")
    d.e("R7", "NX", "no", bend="src")
    return d


def course():
    d = Diagram(3, 13, col_w=250, row_h=66)
    d.n("S0", "start_run: new random seed\nTrench(seed), Course(seed)", 1, 0, "key")
    d.n("F", "next wall less than\n165 units ahead?", 1, 1, "dec")
    d.n("wait", "wait for the\nnext frame", 2, 1, "muted")
    d.n("N", "choose 1–3 openings\n(fewer 3s once difficulty > 0.6)", 1, 2)
    d.n("R", "pace.reach: time between walls\n− 0.6 s, at 60% of top swim speed", 1, 3)
    d.n("MO", "make_openings: holes within reach of\nevery anchor, inside the trench", 1, 4)
    d.n("OK", "every anchor\ncovered?", 1, 5, "dec")
    d.n("W", "Wall: lumpy holes, radius shrinks\nwith difficulty; mask = collision", 1, 6, "good")
    d.n("A", "anchors = this wall's openings", 1, 7)
    d.n("RW", "45% chance: reward in\nfront of an opening", 1, 8)
    d.n("ROW", "each row until 10\nbefore the next wall", 1, 9, "dec")
    d.n("OB", "obstacle (55% → 95%)\nhalf random x, half in line\nwith an opening; maybe 2", 0, 10.2, "hit")
    d.n("RR", "otherwise 70%: reward\npearl · shell · starfish · gem", 2, 10.2, "good")
    d.n("GAP", "next_wall_y += gap\n46–78 at the start → 30–52 at full difficulty", 1, 11.5)
    d.e("S0", "F")
    d.e("F", "wait", "no")
    d.e("F", "N", "yes")
    d.e("N", "R")
    d.e("R", "MO")
    d.e("MO", "OK")
    d.e("OK", "MO", "no, under 30 tries", route="right", extra=10)
    d.e("OK", "W", "yes, or best of 30")
    d.e("W", "A")
    d.e("A", "RW")
    d.e("RW", "ROW")
    d.e("ROW", "OB", bend="src")
    d.e("ROW", "RR", bend="src")
    d.e("OB", "GAP", bend="dst")
    d.e("RR", "GAP", bend="dst")
    d.e("GAP", "F", "next segment", route="left", extra=8)
    return d


def assets():
    d = Diagram(3, 11, col_w=230, row_h=66)
    d.n("D", "packaged build?", 1, 0.55, "dec")
    d.n("DB", "bundled assets\ncurrent?", 0, 1.6, "dec")
    d.n("PR", "project assets/\n(user folder if read-only)", 2, 1.6)
    d.n("BU", "use bundled assets", 0, 2.65, "good")
    d.n("UD", "user data folder/assets", 1, 2.65)
    d.n("T", "delete outdated assets, then build only\nmissing files (sprites, textures, audio)", 1, 3.75, "key")
    d.group("GENERATE  (first launch)", 0, 0, 2, 4.3)
    d.n("REQ", "request, e.g.\ntexture('fx', 'bubble.png')", 1, 5.35)
    d.n("C1", "in custom/ next\nto the program?", 1, 6.4, "dec")
    d.n("C2", "in bundled or project custom/?\nany of png · jpg · jpeg", 1, 7.45, "dec")
    d.n("G", "generated asset", 1, 8.5)
    d.n("USE", "load once and cache", 2, 8.5, "good")
    d.group("LOAD  (Resources)", 0, 4.8, 2, 9.0)
    d.n("MUS", "SoundManager: 8 tunes per theme, next stage every 10 passes,\nafter the 8th cycles the last 4, crossfades, preloads next", 1, 10.1)
    d.e("D", "DB", "yes", bend="src")
    d.e("D", "PR", "no", bend="src")
    d.e("DB", "BU", "yes")
    d.e("DB", "UD", "no", route="hv")
    d.e("BU", "T", bend="dst", ex=-80)
    d.e("UD", "T")
    d.e("PR", "T", bend="dst", ex=80)
    d.e("T", "REQ", "at load time")
    d.e("REQ", "C1")
    d.e("C1", "USE", "yes", route="hv", ex=-30)
    d.e("C1", "C2", "no")
    d.e("C2", "USE", "yes", route="hv", ex=30)
    d.e("C2", "G", "no")
    d.e("G", "USE")
    d.e("USE", "MUS", "music", bend="src")
    return d


# --------------------------------------------------------------------------
# Document content
# --------------------------------------------------------------------------
# Inline markup: `code` and **bold**.
SECTIONS = [
    {
        "title": "Module map", "files": "app.py · world/__init__.py", "diagram": module_map,
        "caption": "Who owns what. Dashed lines are data the code reads; WORLD is rebuilt when the theme changes.",
        "text": ["`SlipstreamApp` owns everything. It splits the game into a 3D half (`World`, which "
                 "moves things and reports collisions) and a rules half (the app itself, which turns those "
                 "reports into health, sounds, HUD updates and saved records). `World` knows nothing about "
                 "health or scoring."],
    },
    {
        "title": "Startup", "files": "SlipstreamApp.__init__", "diagram": startup,
        "caption": "From launch to the first frame.",
        "text": ["The save file is read before Panda3D is imported, because the last window size must be "
                 "set before the window opens. Missing assets are generated next, with a progress message "
                 "rendered frame by frame."],
    },
    {
        "title": "Game states", "files": "self.state", "diagram": states,
        "caption": "The five states and the keys that move between them.",
        "text": ["The app is a five-state machine. Key events call `on_*` methods that check the current "
                 "state before acting; `_task` then advances whichever state is active each frame. On the "
                 "title screen, T changes theme, S toggles sound, R resets the best time, A toggles the aim "
                 "helper and B toggles the touch buttons."],
        "notes": [
            "**menu / about:** `_update_attract` fakes key presses from slow sine waves so the fish "
            "weaves through open water.",
            "**play:** `_update_play` runs the rules (next section).",
            "**paused:** the world is not updated at all, so it stays frozen.",
            "**gameover:** the fish drifts forward at speed 2 with `active=False` (no collisions) behind "
            "the panel.",
            "**Esc** from play, paused or game over returns to the menu; leaving a run this way still "
            "records its time.",
        ],
    },
    {
        "title": "One frame of play", "files": "_task → _update_play → World.update", "diagram": frame,
        "caption": "What happens every frame while a run is in progress.",
        "text": ["Each frame, `dt` is capped at 1/20 s so a stall can't push the fish through a wall in one "
                 "step. The world moves everything and returns two lists: **events** (bumped the floor or a "
                 "cliff) and **hits** (hit, reward or passed). The app turns those into game consequences."],
        "notes": [
            "**One hit per object.** Each wall or obstacle sets `hit = True` on first contact, and the "
            "0.9 s invulnerability window stops brushing along a wall from costing several hits.",
            "**Score is time survived.** `run_time` is the score; the fish's `y` is the distance used for "
            "the Last Run and Best gates.",
            "**Wall collision is pixel exact.** A wall's hole mask is also its texture alpha; the fish's "
            "centre and 8 rim points are tested against it.",
        ],
    },
    {
        "title": "Course generation", "files": "course.py · walls.py · pace.py · trench.py",
        "diagram": course,
        "caption": "How each segment of the endless course is built.",
        "text": ["The course is endless but fully determined by one random seed per run. It is built one "
                 "**segment** at a time (a wall, then rows of obstacles up to the next wall) whenever the next "
                 "wall comes within 165 units. The key guarantee: every wall has an opening the player can "
                 "reach in time from some opening of the previous wall."],
        "notes": [
            "**Speed.** Forward speed rises from 9 toward 19 units/s on an exponential curve (time "
            "constant 150 s). `time_at(y)` inverts the distance integral by bisection so generation knows "
            "how long the player has between walls.",
            "**Trench.** Each cliff drifts inward by up to 9.6 units using three long sine waves with "
            "random phases, clipped and faded in after the first 25 units.",
        ],
    },
    {
        "title": "Assets and resources", "files": "assetgen/ · resources.py · sound.py", "diagram": assets,
        "caption": "Where generated files go, and how custom/ overrides them.",
        "text": ["Nothing binary ships in the repo. Generators draw every sprite, texture, effect and tune "
                 "with numpy and Pillow. At load time, files in `custom/` always win over generated ones."],
    },
]

TUNING = [
    ("`HEALTH_MAX`", "100", "Run ends at 0"),
    ("`WALL_DAMAGE` / `OBSTACLE_DAMAGE`", "25 / 14", "Health lost per hit"),
    ("`CLIFF_DAMAGE`", "5 per 1 s", "Scraping or being pushed by a side cliff"),
    ("`HIT_INVULNERABLE`", "0.9 s", "Grace period after a hit"),
    ("`HEALTH_REGEN`", "0.6 /s", "Slow natural healing"),
    ("`FORWARD_SPEED_START` → `MAX`", "9 → 19", "Units/s, ramp constant 150 s"),
    ("`DIFFICULTY_DISTANCE`", "4000", "Distance at which difficulty reaches 1"),
    ("`SPAWN_AHEAD` / `DESPAWN_BEHIND`", "165 / 25", "Course window around the fish"),
    ("`MUSIC_STAGE_EVERY`", "10", "Walls and obstacles passed per tune change"),
    ("`CAM_DIST_MIN` – `MAX`", "3 – 18", "A / Z zoom range"),
]

# --------------------------------------------------------------------------
# OpenDocument writing
# --------------------------------------------------------------------------
NS = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
      'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
      'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
      'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
      'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" '
      'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
      'xmlns:xlink="http://www.w3.org/1999/xlink" '
      'xmlns:dc="http://purl.org/dc/elements/1.1/" '
      'xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" '
      'xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" '
      'office:version="1.3"')

TEAL, CORAL, MUTED = "#0b7285", "#c8553d", "#4d6870"
PAGE_W, MARGIN = 21.59, 2.0          # US Letter, cm
TEXT_W = PAGE_W - 2 * MARGIN
MAX_FIG_H = 19.5                     # keep tall diagrams on one page (cm)


def inline(s):
    """`code` and **bold** -> ODF spans."""
    out, i = [], 0
    while i < len(s):
        if s.startswith("**", i):
            j = s.index("**", i + 2)
            out.append(f'<text:span text:style-name="Strong">{inline(s[i + 2:j])}</text:span>')
            i = j + 2
        elif s[i] == "`":
            j = s.index("`", i + 1)
            out.append(f'<text:span text:style-name="Code">{escape(s[i + 1:j])}</text:span>')
            i = j + 1
        else:
            j = min([k for k in (s.find("**", i), s.find("`", i)) if k >= 0] or [len(s)])
            out.append(escape(s[i:j]))
            i = j
    return "".join(out)


def styles_xml():
    def pstyle(name, display, parent="Standard", next_=None, p="", t="", cls="text"):
        nx = f' style:next-style-name="{next_}"' if next_ else ""
        return (f'<style:style style:name="{name}" style:display-name="{display}" style:family="paragraph" '
                f'style:parent-style-name="{parent}"{nx} style:class="{cls}">'
                f'<style:paragraph-properties {p}/><style:text-properties {t}/></style:style>')
    body_font = 'style:font-name="Body" fo:font-size="10.5pt"'
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles {NS}>
<office:font-face-decls>
  <style:font-face style:name="Body" svg:font-family="'Liberation Sans'" style:font-family-generic="swiss"/>
  <style:font-face style:name="Display" svg:font-family="'DejaVu Sans'" style:font-family-generic="swiss"/>
  <style:font-face style:name="Mono" svg:font-family="'DejaVu Sans Mono'" style:font-family-generic="modern" style:font-pitch="fixed"/>
</office:font-face-decls>
<office:styles>
  <style:default-style style:family="paragraph">
    <style:paragraph-properties fo:orphans="2" fo:widows="2"/>
    <style:text-properties {body_font} fo:language="en" fo:country="CA" fo:color="#0f2a33"/>
  </style:default-style>
  <style:style style:name="Standard" style:family="paragraph" style:class="text">
    <style:text-properties {body_font}/>
  </style:style>
  {pstyle("Text_20_body", "Text body", p='fo:margin-top="0cm" fo:margin-bottom="0.22cm" fo:line-height="140%"')}
  {pstyle("Title", "Title", next_="Subtitle", cls="chapter",
          p='fo:margin-bottom="0.15cm"',
          t='style:font-name="Display" fo:font-size="24pt" fo:font-weight="bold"')}
  {pstyle("Subtitle", "Subtitle", next_="Text_20_body", cls="chapter",
          p='fo:margin-bottom="0.5cm" fo:line-height="135%"',
          t=f'fo:font-size="12pt" fo:color="{MUTED}"')}
  {pstyle("Eyebrow", "Eyebrow", p='fo:margin-bottom="0.1cm"',
          t=f'style:font-name="Mono" fo:font-size="8.5pt" fo:letter-spacing="0.06cm" fo:color="{TEAL}" fo:text-transform="uppercase"')}
  {pstyle("Heading_20_1", "Heading 1", next_="Text_20_body", cls="text",
          p='fo:margin-top="0.55cm" fo:margin-bottom="0.05cm" fo:keep-with-next="always"',
          t='style:font-name="Display" fo:font-size="16pt" fo:font-weight="bold"')}
  {pstyle("Files", "Source files", p='fo:margin-bottom="0.2cm" fo:keep-with-next="always"',
          t=f'style:font-name="Mono" fo:font-size="8.5pt" fo:color="{MUTED}"')}
  {pstyle("Figure", "Figure", p='fo:text-align="center" fo:margin-top="0.2cm" fo:margin-bottom="0.1cm" fo:keep-with-next="always"')}
  {pstyle("Caption", "Caption", p='fo:text-align="center" fo:margin-bottom="0.35cm"',
          t=f'fo:font-size="9pt" fo:font-style="italic" fo:color="{MUTED}"')}
  {pstyle("Note", "Note", p='fo:margin-bottom="0.12cm" fo:line-height="135%"', t='fo:font-size="10pt"')}
  {pstyle("Table_20_Contents", "Table Contents", t='fo:font-size="9.5pt"')}
  {pstyle("Table_20_Heading", "Table Heading", parent="Table_20_Contents",
          t=f'style:font-name="Mono" fo:font-size="8pt" fo:color="{MUTED}" fo:text-transform="uppercase" fo:letter-spacing="0.03cm"')}
  {pstyle("Footer", "Footer", p='fo:text-align="center"', t=f'fo:font-size="8.5pt" fo:color="{MUTED}"')}
  {pstyle("Contents", "Contents", p='fo:margin-left="0.4cm" fo:margin-bottom="0.05cm"', t=f'fo:color="{TEAL}"')}
  <style:style style:name="Code" style:family="text">
    <style:text-properties style:font-name="Mono" fo:font-size="9.5pt" fo:color="{TEAL}"/>
  </style:style>
  <style:style style:name="Strong" style:display-name="Strong Emphasis" style:family="text">
    <style:text-properties fo:font-weight="bold"/>
  </style:style>
  <text:list-style style:name="Notes">
    <text:list-level-style-bullet text:level="1" text:bullet-char="■">
      <style:list-level-properties text:list-level-position-and-space-mode="label-alignment">
        <style:list-level-label-alignment text:label-followed-by="listtab" text:list-tab-stop-position="0.6cm" fo:text-indent="-0.45cm" fo:margin-left="0.6cm"/>
      </style:list-level-properties>
      <style:text-properties fo:color="{TEAL}" fo:font-size="70%"/>
    </text:list-level-style-bullet>
  </text:list-style>
</office:styles>
<office:automatic-styles>
  <style:page-layout style:name="pm1">
    <style:page-layout-properties fo:page-width="{PAGE_W}cm" fo:page-height="27.94cm" style:print-orientation="portrait"
      fo:margin-top="1.8cm" fo:margin-bottom="1.4cm" fo:margin-left="{MARGIN}cm" fo:margin-right="{MARGIN}cm"/>
    <style:footer-style><style:header-footer-properties fo:min-height="0.6cm" fo:margin-top="0.4cm"/></style:footer-style>
  </style:page-layout>
</office:automatic-styles>
<office:master-styles>
  <style:master-page style:name="Standard" style:page-layout-name="pm1">
    <style:footer><text:p text:style-name="Footer">Slipstream architecture · page <text:page-number text:select-page="current">1</text:page-number></text:p></style:footer>
  </style:master-page>
</office:master-styles>
</office:document-styles>"""


def content_xml(figures):
    body = []
    P = lambda style, s: body.append(f'<text:p text:style-name="{style}">{s}</text:p>')
    P("Eyebrow", "Slipstream · architecture")
    P("Title", "How Slipstream runs, from launch to game over")
    P("Subtitle", "Six diagrams covering the whole Python/Panda3D game: who owns what, the startup path, "
                  "the state machine, one frame of play, how the endless course is generated, and how art "
                  "and sound are found.")
    for i, sec in enumerate(SECTIONS):
        P("Contents", f"{i + 1}. {escape(sec['title'])}")
    P("Contents", f"{len(SECTIONS) + 1}. Tuning numbers")
    for i, sec in enumerate(SECTIONS):
        body.append(f'<text:h text:style-name="Heading_20_1" text:outline-level="1">'
                    f'{i + 1}. {escape(sec["title"])}</text:h>')
        P("Files", escape(sec["files"]))
        for t in sec["text"]:
            P("Text_20_body", inline(t))
        name, w, h = figures[i]
        fw = TEXT_W
        fh = fw * h / w
        if fh > MAX_FIG_H:
            fh, fw = MAX_FIG_H, MAX_FIG_H * w / h
        imgs = (f'<draw:image xlink:href="Pictures/{name}.svg" xlink:type="simple" xlink:show="embed" '
                f'xlink:actuate="onLoad" draw:mime-type="image/svg+xml"/>')
        if (Path(TMP) / f"{name}.png").exists():
            imgs += (f'<draw:image xlink:href="Pictures/{name}.png" xlink:type="simple" xlink:show="embed" '
                     f'xlink:actuate="onLoad" draw:mime-type="image/png"/>')
        P("Figure", f'<draw:frame draw:style-name="fr1" draw:name="Figure {i + 1}" text:anchor-type="as-char" '
                    f'svg:width="{fw:.2f}cm" svg:height="{fh:.2f}cm" draw:z-index="{i}">{imgs}</draw:frame>')
        P("Caption", f"Figure {i + 1}. {escape(sec['caption'])}")
        if sec.get("notes"):
            body.append('<text:list text:style-name="Notes">')
            for n in sec["notes"]:
                body.append(f'<text:list-item><text:p text:style-name="Note">{inline(n)}</text:p></text:list-item>')
            body.append("</text:list>")

    body.append(f'<text:h text:style-name="Heading_20_1" text:outline-level="1">'
                f'{len(SECTIONS) + 1}. Tuning numbers</text:h>')
    P("Files", "config.py")
    P("Text_20_body", "The values the diagrams refer to. Changing these in `config.py` is the quickest way to "
                      "change how the game feels.".replace("`config.py`", inline("`config.py`")))
    rows = ['<table:table table:name="Tuning" table:style-name="Tbl">',
            '<table:table-column table:style-name="TblA"/><table:table-column table:style-name="TblB"/>'
            '<table:table-column table:style-name="TblC"/>',
            '<table:table-header-rows><table:table-row>']
    for h in ("Constant", "Value", "What it controls"):
        rows.append(f'<table:table-cell table:style-name="TblHead" office:value-type="string">'
                    f'<text:p text:style-name="Table_20_Heading">{h}</text:p></table:table-cell>')
    rows.append("</table:table-row></table:table-header-rows>")
    for k, v, what in TUNING:
        rows.append("<table:table-row>")
        for s, mono in ((k, False), (v, True), (what, False)):
            txt = f'<text:span text:style-name="Code">{escape(s)}</text:span>' if mono else inline(s)
            rows.append(f'<table:table-cell table:style-name="TblCell" office:value-type="string">'
                        f'<text:p text:style-name="Table_20_Contents">{txt}</text:p></table:table-cell>')
        rows.append("</table:table-row>")
    rows.append("</table:table>")
    body.extend(rows)
    P("Caption", "Drawn from the source code. The diagrams simplify some detail; the code is the reference.")

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-content {NS}>
<office:automatic-styles>
  <style:style style:name="fr1" style:family="graphic">
    <style:graphic-properties style:vertical-pos="middle" style:vertical-rel="line" fo:border="none" style:wrap="none"/>
  </style:style>
  <style:style style:name="Tbl" style:family="table">
    <style:table-properties style:width="{TEXT_W}cm" table:align="margins" fo:margin-top="0.2cm" fo:margin-bottom="0.3cm"/>
  </style:style>
  <style:style style:name="TblA" style:family="table-column"><style:table-column-properties style:column-width="6.6cm"/></style:style>
  <style:style style:name="TblB" style:family="table-column"><style:table-column-properties style:column-width="2.8cm"/></style:style>
  <style:style style:name="TblC" style:family="table-column"><style:table-column-properties style:column-width="{TEXT_W - 9.4:.2f}cm"/></style:style>
  <style:style style:name="TblHead" style:family="table-cell">
    <style:table-cell-properties fo:background-color="#e3f1f4" fo:padding="0.14cm" fo:border-top="none" fo:border-left="none" fo:border-right="none" fo:border-bottom="0.75pt solid {TEAL}"/>
  </style:style>
  <style:style style:name="TblCell" style:family="table-cell">
    <style:table-cell-properties fo:padding="0.14cm" fo:border-top="none" fo:border-left="none" fo:border-right="none" fo:border-bottom="0.5pt solid #c9dadd"/>
  </style:style>
</office:automatic-styles>
<office:body><office:text>
{chr(10).join(body)}
</office:text></office:body>
</office:document-content>"""


META = f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-meta {NS}><office:meta>
<dc:title>How Slipstream runs</dc:title>
<dc:description>Architecture overview and diagrams for the Slipstream game.</dc:description>
<meta:generator>slipstream tools/build_docs.py</meta:generator>
</office:meta></office:document-meta>"""

TMP = None


def main():
    global TMP
    TMP = tempfile.mkdtemp(prefix="slipstream-docs-")
    figures = []
    magick = shutil.which("magick") or shutil.which("convert")
    for i, sec in enumerate(SECTIONS):
        d = sec["diagram"]()
        name = f"figure{i + 1}"
        (Path(TMP) / f"{name}.svg").write_text(d.svg(), encoding="utf-8")
        if magick:
            subprocess.run([magick, "-density", "192", f"{name}.svg", f"{name}.png"],
                           cwd=TMP, check=False, capture_output=True)
        figures.append((name, d.width, d.height))

    manifest = ['<?xml version="1.0" encoding="UTF-8"?>',
                '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.3">',
                '<manifest:file-entry manifest:full-path="/" manifest:version="1.3" manifest:media-type="application/vnd.oasis.opendocument.text"/>',
                '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>',
                '<manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>',
                '<manifest:file-entry manifest:full-path="meta.xml" manifest:media-type="text/xml"/>']
    pictures = []
    for name, _w, _h in figures:
        for ext, mime in (("svg", "image/svg+xml"), ("png", "image/png")):
            p = Path(TMP) / f"{name}.{ext}"
            if p.exists():
                pictures.append((f"Pictures/{name}.{ext}", p))
                manifest.append(f'<manifest:file-entry manifest:full-path="Pictures/{name}.{ext}" manifest:media-type="{mime}"/>')
    manifest.append("</manifest:manifest>")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w") as z:
        # the mimetype entry must come first and be stored uncompressed
        z.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.oasis.opendocument.text",
                   compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/manifest.xml", "\n".join(manifest), compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("content.xml", content_xml(figures), compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("styles.xml", styles_xml(), compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("meta.xml", META, compress_type=zipfile.ZIP_DEFLATED)
        for arc, p in pictures:
            z.write(p, arc, compress_type=zipfile.ZIP_DEFLATED)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(figures)} diagrams"
          f"{', with PNG copies' if any(a.endswith('.png') for a, _ in pictures) else ''})")
    if "--keep" in __import__("sys").argv:
        print("diagram files kept in", TMP)
    else:
        shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    main()
