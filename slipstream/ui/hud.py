"""In-game heads-up display: time, walls passed, health, best time, banners.

Layout of the top bar:   TIME 0:42.1   WALLS 7   HEALTH [=====   ] 63   BEST 1:05.3
                                                                    last run 0:40.0
Also: big banners mid-screen ("NEW BEST TIME!"), floating "+12"/"-25"
popups and a red full-screen flash when hit.
"""

from direct.gui.DirectGui import DirectFrame
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode, TransparencyAttrib

from .. import config
from .common import fmt_time, TEXT, ACCENT, MUTED

BAR_H = 0.13      # height of the top bar (aspect2d units)


class HUD:
    """The top bar and in-game messages.  The app calls set_values() each
    frame with the numbers to show, and update() to animate messages."""

    def __init__(self, base):
        self.base = base
        self.root = base.aspect2d.attachNewNode("hud")
        self.bar = DirectFrame(parent=base.a2dTopCenter, frameColor=(0.0, 0.04, 0.09, 0.85),
                               frameSize=(-4, 4, -BAR_H, 0))
        self.bar.setBin("background", 0)     # drawn first, behind all HUD items

        self.time = OnscreenText(parent=base.a2dTopLeft, text="", pos=(0.05, -0.088), scale=0.075,
                                 fg=TEXT, align=TextNode.ALeft, mayChange=True, shadow=(0, 0, 0, 0.6))
        self.walls = OnscreenText(parent=base.a2dTopLeft, text="", pos=(0.55, -0.088), scale=0.075,
                                  fg=ACCENT, align=TextNode.ALeft, mayChange=True, shadow=(0, 0, 0, 0.6))
        self.best = OnscreenText(parent=base.a2dTopRight, text="", pos=(-0.05, -0.065), scale=0.064,
                                 fg=(0.5, 1, 0.6, 1), align=TextNode.ARight, mayChange=True,
                                 shadow=(0, 0, 0, 0.6))
        self.last = OnscreenText(parent=base.a2dTopRight, text="", pos=(-0.05, -0.115), scale=0.045,
                                 fg=MUTED, align=TextNode.ARight, mayChange=True)

        # health bar: placed by layout() in the space between WALLS and BEST,
        # shrinking on narrow windows so nothing overlaps
        self.hp_group = base.a2dTopCenter.attachNewNode("health")
        self.hp_bar = self.hp_group.attachNewNode("health-bar")     # scaled in x to fit
        self.hp_group.setBin("fixed", 10)    # always drawn on top of the dark top bar
        self.hp_label = OnscreenText(parent=self.hp_group, text="HEALTH", pos=(-0.42, -0.085),
                                     scale=0.055, fg=MUTED, align=TextNode.ARight)
        # outline marking the full (100%) size of the bar; the dark background
        # drawn on top of it leaves just a thin light border showing
        self.hp_outline = DirectFrame(parent=self.hp_bar, frameColor=(0.85, 0.92, 1.0, 0.95),
                                      frameSize=(-0.407, 0.407, -0.102, -0.038))
        self.hp_bg = DirectFrame(parent=self.hp_bar, frameColor=(0.1, 0.1, 0.12, 0.9),
                                 frameSize=(-0.4, 0.4, -0.095, -0.045))
        self.hp_fill = DirectFrame(parent=self.hp_bar, frameColor=(0.2, 0.9, 0.35, 1),
                                   frameSize=(0, 0.79, -0.09, -0.05), pos=(-0.395, 0, 0))
        self.hp_text = OnscreenText(parent=self.hp_group, text="", pos=(0, -0.083), scale=0.045,
                                    fg=(1, 1, 1, 1), mayChange=True, shadow=(0, 0, 0, 1))

        # transient elements
        self.banner = OnscreenText(parent=base.aspect2d, text="", pos=(0, 0.28), scale=0.11,
                                   fg=ACCENT, mayChange=True, shadow=(0, 0, 0, 0.8))
        self.banner_t = 0.0      # seconds the banner stays up
        self.popups = []         # [text node, seconds left] for each "+12" / "-25"
        # red full-screen overlay, normally fully transparent
        self.flash = DirectFrame(parent=base.render2d, frameColor=(1, 0.1, 0.05, 0),
                                 frameSize=(-1, 1, -1, 1))
        self.flash.setTransparency(TransparencyAttrib.M_alpha)
        self.flash.setBin("fixed", 100)
        self.flash_t = 0.0
        self.nodes = [self.bar, self.time,self.walls, self.best, self.last, self.hp_label, self.hp_outline, self.hp_bg,
                      self.hp_fill, self.hp_text]
        self.hide()

    def show(self):
        self.root.show()
        for n in self.nodes:
            n.show()

    def hide(self):
        self.root.hide()
        for n in self.nodes:
            n.hide()
        self.banner.setText("")
        self.flash["frameColor"] = (1, 0.1, 0.05, 0)

    def set_values(self, run_time, walls, health, best_time, last_time):
        """Show these numbers in the top bar."""
        self.time.setText(f"TIME  {fmt_time(run_time)}")
        self.walls.setText(f"WALLS  {walls}")
        self.best.setText(f"BEST  {fmt_time(best_time)}" if best_time > 0 else "BEST  --")
        self.last.setText(f"last run  {fmt_time(last_time)}" if last_time > 0 else "")
        f = max(0.0, min(1.0, health / config.HEALTH_MAX))    # fraction of full health
        self.hp_fill.setSx(max(f, 0.001))     # shrink the bar (scale 0 isn't allowed)
        # green above half, yellow above a quarter, red below
        col = (0.2, 0.9, 0.35, 1) if f > 0.5 else (0.95, 0.8, 0.2, 1) if f > 0.25 else (1, 0.25, 0.2, 1)
        self.hp_fill["frameColor"] = col
        self.hp_text.setText(f"{int(round(health))}")
        self.layout()

    def layout(self):
        """Fit the health bar between the WALLS counter and the BEST time."""
        def width(t, scale):
            # an empty TextNode reports a garbage width, so treat it as zero
            return t.textNode.getWidth() * scale if t.textNode.getText() else 0.0
        a = self.base.getAspectRatio()
        walls_right = -a + 0.55 + width(self.walls, 0.075)
        best_left = a - 0.05 - max(width(self.best, 0.064), width(self.last, 0.045))
        label_w = width(self.hp_label, 0.055) + 0.03
        gap = 0.07
        left, right = walls_right + gap, best_left - gap
        show_label = right - left - label_w >= 0.35
        if show_label:
            left += label_w
        width = max(0.2, min(0.8, right - left))
        center = (left + right) / 2
        self.hp_group.setX(center)
        self.hp_bar.setSx(width / 0.8)
        self.hp_label.setX(-width / 2 - 0.02)
        if show_label:
            self.hp_label.show()
        else:
            self.hp_label.hide()

    def show_banner(self, text, color=ACCENT, duration=2.5):
        """Big message in the middle of the screen that fades after `duration` s."""
        self.banner.setText(text)
        self.banner.setFg(color)
        self.banner.setTransparency(TransparencyAttrib.M_alpha)
        self.banner.setAlphaScale(1.0)
        self.banner_t = duration

    def damage_flash(self):
        """Flash the screen red briefly."""
        self.flash_t = 0.35

    def popup(self, text, color=(0.6, 1, 0.7, 1)):
        """A short message (e.g. "+12") that floats up and fades over a second."""
        t = OnscreenText(parent=self.base.aspect2d, text=text, pos=(0, -0.05), scale=0.08, fg=color,
                         shadow=(0, 0, 0, 0.8), mayChange=True)
        t.setTransparency(TransparencyAttrib.M_alpha)
        self.popups.append([t, 1.0])

    def update(self, dt):
        """Animate the banner, flash and popups (every frame)."""
        if self.banner_t > 0:
            self.banner_t -= dt
            self.banner.setAlphaScale(max(0.0, min(1.0, self.banner_t * 2)))
            if self.banner_t <= 0:
                self.banner.setText("")
        if self.flash_t > 0:
            self.flash_t = max(0.0, self.flash_t - dt)
        self.flash["frameColor"] = (1, 0.1, 0.05, self.flash_t * 1.1)
        for p in list(self.popups):
            p[1] -= dt
            t = p[0]
            t.setZ(t.getZ() + dt * 0.25)
            t.setAlphaScale(max(0.0, min(1.0, p[1] * 2)))
            if p[1] <= 0:
                t.destroy()
                self.popups.remove(p)
