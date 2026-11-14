"""Start screen, pause overlay and game-over panel."""

from direct.gui.DirectGui import DirectFrame, OnscreenImage
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode, TransparencyAttrib

from .common import button, fmt_time, PANEL, ACCENT, TEXT, MUTED


class StartMenu:
    def __init__(self, base, app):
        self.app = app
        # more see-through than the other panels so the scene shows behind it
        self.frame = DirectFrame(parent=base.aspect2d, frameColor=PANEL[:3] + (0.55,),
                                 frameSize=(-0.78, 0.78, -0.80, 0.56), pos=(0, 0, -0.08))
        OnscreenText(parent=self.frame, text="SLIPSTREAM", pos=(0, 0.42), scale=0.13, fg=ACCENT,
                     shadow=(0, 0, 0, 0.8))
        OnscreenText(parent=self.frame, text="swim through the gaps", pos=(0, 0.345), scale=0.058, fg=MUTED)
        # theme details centred under the title, with the animated player on both sides
        self.previews = []
        for x in (-0.58, 0.58):
            img = OnscreenImage(image=app.res.texture("player", "fish_clown_0.png"),
                                parent=self.frame, pos=(x, 0, 0.10), scale=0.15)
            img.setTransparency(TransparencyAttrib.M_alpha)
            self.previews.append(img)
        self.theme_name = OnscreenText(parent=self.frame, text="", pos=(0, 0.20), scale=0.085,
                                       fg=TEXT, align=TextNode.ACenter, mayChange=True)
        self.blurb = OnscreenText(parent=self.frame, text="", pos=(0, 0.125), scale=0.05, fg=MUTED,
                                  align=TextNode.ACenter, mayChange=True, wordwrap=16)
        self.record = OnscreenText(parent=self.frame, text="", pos=(0, -0.055), scale=0.056,
                                   fg=(0.5, 1, 0.6, 1), align=TextNode.ACenter, mayChange=True)

        x0, x1 = -0.36, 0.36
        self.b_start = button(self.frame, "Start  [Space]", app.start_run, (0, 0, -0.16), width=1.3, scale=0.065)
        self.b_theme = button(self.frame, "", app.next_theme, (x0, 0, -0.30))
        self.b_sound = button(self.frame, "", app.toggle_sound, (x1, 0, -0.30))
        self.b_reset = button(self.frame, "Reset Best  [R]", app.reset_best, (x0, 0, -0.42))
        self.b_touch = button(self.frame, "", app.toggle_touch, (x1, 0, -0.42))
        self.b_aim = button(self.frame, "", app.toggle_aim, (x0, 0, -0.54))
        self.b_quit = button(self.frame, "Quit  [Q / Esc]", app.quit, (x1, 0, -0.54))
        OnscreenText(parent=self.frame,
                     text="Arrows: swim     A / Z: camera closer / further     P: pause",
                     pos=(0, -0.71), scale=0.05, fg=MUTED)
        self.anim = 0.0
        self.frames = []

    def refresh(self, theme, record, sound_on, touch_on, aim_on, frames):
        self.frames = frames
        for img in self.previews:
            img.setImage(frames[0])
            img.setTransparency(TransparencyAttrib.M_alpha)
        self.theme_name.setText(theme.name)
        self.blurb.setText(theme.blurb)
        if record["best_time"] > 0:
            self.record.setText(f"Best time:  {fmt_time(record['best_time'])}")
        else:
            self.record.setText("Best time:  --")
        self.b_theme["text"] = "Theme  [T]"
        self.b_sound["text"] = f"Sound: {'On' if sound_on else 'Off'}  [S]"
        self.b_touch["text"] = f"Touch Buttons: {'On' if touch_on else 'Off'}  [B]"
        self.b_aim["text"] = f"Aim Helper: {'On' if aim_on else 'Off'}  [A]"

    def update(self, dt):
        if self.frames and not self.frame.isHidden():
            self.anim += dt * 8
            for img in self.previews:
                img.setTexture(self.frames[int(self.anim) % len(self.frames)], 1)

    def show(self):
        self.frame.show()

    def hide(self):
        self.frame.hide()


class GameOverPanel:
    def __init__(self, base, app):
        self.frame = DirectFrame(parent=base.aspect2d, frameColor=PANEL,
                                 frameSize=(-0.7, 0.7, -0.5, 0.45), pos=(0, 0, -0.08))
        OnscreenText(parent=self.frame, text="GAME OVER", pos=(0, 0.3), scale=0.12, fg=(1, 0.45, 0.35, 1),
                     shadow=(0, 0, 0, 0.8))
        self.stats = OnscreenText(parent=self.frame, text="", pos=(0, 0.13), scale=0.085, fg=TEXT,
                                  mayChange=True)
        self.best = OnscreenText(parent=self.frame, text="", pos=(0, 0.0), scale=0.055, fg=ACCENT,
                                 mayChange=True)
        button(self.frame, "Swim Again  [Space]", app.start_run, (0, 0, -0.18), width=0.9, scale=0.06)
        button(self.frame, "Menu  [Esc]", app.to_menu, (0, 0, -0.34), width=0.9, scale=0.06)
        self.hide()

    def show(self, run_time, walls, best_time, new_best):
        self.stats.setText(f"Time {fmt_time(run_time)}     Walls {walls}")
        self.best.setText("NEW BEST TIME!" if new_best else f"Best {fmt_time(best_time)}")
        self.frame.show()

    def hide(self):
        self.frame.hide()


class PausePanel:
    def __init__(self, base, app):
        self.frame = DirectFrame(parent=base.aspect2d, frameColor=PANEL,
                                 frameSize=(-0.55, 0.55, -0.32, 0.3))
        OnscreenText(parent=self.frame, text="PAUSED", pos=(0, 0.15), scale=0.1, fg=ACCENT)
        button(self.frame, "Resume  [P / Space]", app.toggle_pause, (0, 0, -0.02), width=0.8)
        button(self.frame, "Menu  [Esc]", app.to_menu, (0, 0, -0.17), width=0.8)
        self.hide()

    def show(self):
        self.frame.show()

    def hide(self):
        self.frame.hide()
