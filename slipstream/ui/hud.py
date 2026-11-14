"""In-game heads-up display: time, walls passed, health, best time, banners."""

from direct.gui.DirectGui import DirectFrame
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode, TransparencyAttrib

from .. import config
from .common import fmt_time, TEXT, ACCENT, MUTED

BAR_H = 0.13      # height of the top bar (aspect2d units)


class HUD:
    def __init__(self, base):
        self.base = base
        self.root = base.aspect2d.attachNewNode("hud")
        self.bar = DirectFrame(parent=base.a2dTopCenter, frameColor=(0.0, 0.04, 0.09, 0.85),
                               frameSize=(-4, 4, -BAR_H, 0))
        self.bar.setBin("fixed", -10)

        self.time = OnscreenText(parent=base.a2dTopLeft, text="", pos=(0.05, -0.088), scale=0.075,
                                 fg=TEXT, align=TextNode.ALeft, mayChange=True, shadow=(0, 0, 0, 0.6))
        self.walls = OnscreenText(parent=base.a2dTopLeft, text="", pos=(0.55, -0.088), scale=0.075,
                                  fg=ACCENT, align=TextNode.ALeft, mayChange=True, shadow=(0, 0, 0, 0.6))
        self.best = OnscreenText(parent=base.a2dTopRight, text="", pos=(-0.05, -0.065), scale=0.064,
                                 fg=(0.5, 1, 0.6, 1), align=TextNode.ARight, mayChange=True,
                                 shadow=(0, 0, 0, 0.6))
        self.last = OnscreenText(parent=base.a2dTopRight, text="", pos=(-0.05, -0.115), scale=0.045,
                                 fg=MUTED, align=TextNode.ARight, mayChange=True)

        # health bar
        self.hp_label = OnscreenText(parent=base.a2dTopCenter, text="HEALTH", pos=(-0.42, -0.085),
                                     scale=0.055, fg=MUTED, align=TextNode.ARight)
        self.hp_bg = DirectFrame(parent=base.a2dTopCenter, frameColor=(0.1, 0.1, 0.12, 0.9),
                                 frameSize=(-0.4, 0.4, -0.095, -0.045))
        self.hp_fill = DirectFrame(parent=base.a2dTopCenter, frameColor=(0.2, 0.9, 0.35, 1),
                                   frameSize=(0, 0.79, -0.09, -0.05), pos=(-0.395, 0, 0))
        self.hp_text = OnscreenText(parent=base.a2dTopCenter, text="", pos=(0, -0.083), scale=0.045,
                                    fg=(1, 1, 1, 1), mayChange=True, shadow=(0, 0, 0, 1))

        # transient elements
        self.banner = OnscreenText(parent=base.aspect2d, text="", pos=(0, 0.28), scale=0.11,
                                   fg=ACCENT, mayChange=True, shadow=(0, 0, 0, 0.8))
        self.banner_t = 0.0
        self.popups = []
        self.flash = DirectFrame(parent=base.render2d, frameColor=(1, 0.1, 0.05, 0),
                                 frameSize=(-1, 1, -1, 1))
        self.flash.setTransparency(TransparencyAttrib.M_alpha)
        self.flash.setBin("fixed", 100)
        self.flash_t = 0.0
        self.nodes = [self.bar, self.time,self.walls, self.best, self.last, self.hp_label, self.hp_bg,
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
        self.time.setText(f"TIME  {fmt_time(run_time)}")
        self.walls.setText(f"WALLS  {walls}")
        self.best.setText(f"BEST  {fmt_time(best_time)}" if best_time > 0 else "BEST  --")
        self.last.setText(f"last run  {fmt_time(last_time)}" if last_time > 0 else "")
        f = max(0.0, min(1.0, health / config.HEALTH_MAX))
        self.hp_fill.setSx(max(f, 0.001))
        col = (0.2, 0.9, 0.35, 1) if f > 0.5 else (0.95, 0.8, 0.2, 1) if f > 0.25 else (1, 0.25, 0.2, 1)
        self.hp_fill["frameColor"] = col
        self.hp_text.setText(f"{int(round(health))}")

    def show_banner(self, text, color=ACCENT, duration=2.5):
        self.banner.setText(text)
        self.banner.setFg(color)
        self.banner.setTransparency(TransparencyAttrib.M_alpha)
        self.banner.setAlphaScale(1.0)
        self.banner_t = duration

    def damage_flash(self):
        self.flash_t = 0.35

    def popup(self, text, color=(0.6, 1, 0.7, 1)):
        t = OnscreenText(parent=self.base.aspect2d, text=text, pos=(0, -0.05), scale=0.08, fg=color,
                         shadow=(0, 0, 0, 0.8), mayChange=True)
        t.setTransparency(TransparencyAttrib.M_alpha)
        self.popups.append([t, 1.0])

    def update(self, dt):
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
