"""Shared UI styling helpers."""

from direct.gui.DirectGui import DirectButton, DGG
from panda3d.core import TextNode

# colours (r, g, b, alpha) shared by all screens
PANEL = (0.02, 0.08, 0.14, 0.82)      # dark see-through panel background
ACCENT = (1.0, 0.78, 0.25, 1)         # gold: titles and highlights
TEXT = (0.92, 0.97, 1.0, 1)           # normal text
MUTED = (0.65, 0.78, 0.88, 1)         # less important text


def fmt_time(seconds):
    """Seconds as "m:ss.s", e.g. 75.25 -> "1:15.2"."""
    seconds = max(0.0, seconds)
    m = int(seconds // 60)
    s = seconds - m * 60
    return f"{m}:{s:04.1f}"


def button(parent, text, command, pos, width=0.62, scale=0.055, extra=None):
    """A flat menu button in the game's style that calls command(*extra) when
    clicked.  width is in screen units; the four frame colours are for
    normal, pressed, mouse-over and disabled."""
    b = DirectButton(
        parent=parent, text=text, command=command, extraArgs=extra or [],
        pos=pos, scale=scale, text_fg=TEXT, text_align=TextNode.ACenter,
        frameColor=((0.10, 0.32, 0.48, 0.95), (0.18, 0.48, 0.66, 1),
                    (0.22, 0.56, 0.76, 1), (0.2, 0.2, 0.2, 0.6)),
        frameSize=(-width / scale / 2, width / scale / 2, -0.62, 1.12),
        relief=DGG.FLAT, pressEffect=True, rolloverSound=None, clickSound=None,
    )
    return b
