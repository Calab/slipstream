"""Main application: window setup, input, game states and scoring."""

import os
import random
import sys
from pathlib import Path

from panda3d.core import Filename, TextNode, loadPrcFileData

from . import config
from .themes import THEMES, THEME_BY_KEY

FONT_PATH = Path(__file__).resolve().parent / "fonts" / "SomeTimeLater.otf"


DEFAULT_WIN = (1280, 720)


def position_is_meaningful():
    """Wayland doesn't let programs know or choose where their window is
    (XWayland reports 0,0), so only remember positions on other systems."""
    return not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland")


def usable_origin(origin):
    """A saved position worth restoring, or None (let the OS place the window)."""
    if not origin or not position_is_meaningful():
        return None
    x, y = int(origin[0]), int(origin[1])
    if x < 0 or y < 0 or (x, y) == (0, 0):   # 0,0 means "unknown", not a real choice
        return None
    return x, y


def configure_panda(args, saved_window=None):
    """Window/engine settings.  The window opens at the size (and position)
    it had last time unless --width/--height are given."""
    saved = saved_window or {}
    w, h = saved.get("size") or DEFAULT_WIN
    if args.width or args.height:
        w, h = args.width or DEFAULT_WIN[0], args.height or DEFAULT_WIN[1]
    w, h = max(640, int(w)), max(400, int(h))
    origin = usable_origin(saved.get("origin"))
    if origin and not (args.width or args.height):
        loadPrcFileData("", f"win-origin {origin[0]} {origin[1]}")
    loadPrcFileData("", f"""
        window-title {config.TITLE}
        win-size {w} {h}
        fullscreen {'#t' if args.fullscreen else '#f'}
        sync-video #t
        framebuffer-multisample #t
        multisamples 4
        audio-library-name p3openal_audio
        textures-power-2 none
        show-frame-rate-meter {'#t' if args.fps else '#f'}
        notify-level-audio error
    """)
    if args.offscreen:
        loadPrcFileData("", "window-type offscreen\naudio-library-name null")


class SlipstreamApp:
    """Owns the ShowBase instance and the game state machine."""

    def __init__(self, args):
        from .save import SaveData
        self.save = SaveData()
        configure_panda(args, self.save["window"])
        from direct.showbase.ShowBase import ShowBase
        from direct.showbase.DirectObject import DirectObject
        from direct.gui.OnscreenText import OnscreenText
        from .assetgen import AssetBuilder
        from .resources import Resources
        from .sound import SoundManager

        self.args = args
        self.base = base = ShowBase()
        base.disableMouse()
        base.camLens.setFov(72)
        base.camLens.setNearFar(0.2, 450)
        self._load_font()
        # remember the window size/position whenever it changes
        self.window_events = DirectObject()
        self.window_events.accept("window-event", self._on_window_event)
        self._restore_window_size()

        if args.reset_save:
            self.save.data["records"] = {}
            self.save.save()

        # --- generate any missing assets, with a progress message ---------
        builder = AssetBuilder()
        msg = OnscreenText(text="", pos=(0, 0), scale=0.06, fg=(1, 1, 1, 1), mayChange=True)

        def progress(i, n, label):
            if n:
                msg.setText(f"Generating sea life...  {i}/{n}")
                base.graphicsEngine.renderFrame()
        builder.build(THEMES, progress)
        msg.destroy()

        self.res = Resources(base, builder)
        self.sound = SoundManager(base, self.res, bool(self.save["sound"]))

        # --- input state -----------------------------------------------------
        self.keys = {k: False for k in ("arrow_left", "arrow_right", "arrow_up", "arrow_down", "a", "z")}
        for k in self.keys:
            if k != "a":
                base.accept(k, self.keys.__setitem__, [k, True])
            base.accept(k + "-up", self.keys.__setitem__, [k, False])
        base.accept("a", self.on_a)
        for key, fn in (("t", self.on_t), ("s", self.on_s), ("r", self.on_r), ("q", self.on_q),
                        ("escape", self.on_escape), ("space", self.on_space),
                        ("p", self.toggle_pause), ("b", self.toggle_touch)):
            base.accept(key, fn)

        # --- UI ----------------------------------------------------------------
        from .ui.band import SurfaceBand
        from .ui.hud import HUD
        from .ui.menu import GameOverPanel, PausePanel, StartMenu
        from .ui.touch import TouchControls
        self.band = SurfaceBand(base, self.res)
        self.hud = HUD(base)
        self.menu = StartMenu(base, self)
        self.gameover = GameOverPanel(base, self)
        self.pause_panel = PausePanel(base, self)
        self.touch = TouchControls(base, self.res, self.keys, self.toggle_pause)
        touch = self.save["touch"]
        self.touch_on = bool(touch) if touch is not None else sys.platform == "android"

        self.aim_on = bool(self.save["aim"])
        self.world = None
        self.theme = None
        self.state = "menu"
        self.run_time = 0.0
        key = self.save["theme"] if self.save["theme"] in THEME_BY_KEY else THEMES[0].key
        self.load_theme(THEME_BY_KEY[key])
        self.to_menu()
        base.taskMgr.add(self._task, "slipstream-update")

    # ------------------------------------------------------------------ themes
    def load_theme(self, theme):
        from .world import World
        if self.world:
            self.world.destroy()
        self.theme = theme
        self.world = World(self.base, self.res, theme)
        self.world.aim_enabled = self.aim_on
        self.band.set_theme(theme)
        self.sound.set_theme(theme.key)

    def next_theme(self):
        if self.state != "menu":
            return
        i = (THEMES.index(self.theme) + 1) % len(THEMES)
        self.save["theme"] = THEMES[i].key
        self.load_theme(THEMES[i])
        self.sound.play("click")
        self.sound.play_stage(0, fade=0.5)
        self.refresh_menu()

    def refresh_menu(self):
        rec = self.save.record(self.theme.key)
        if self.state == "menu":
            self.hud.set_values(0.0, 0, config.HEALTH_MAX, rec["best_time"], rec["last_time"])
        self.menu.refresh(self.theme, self.save.record(self.theme.key), self.sound.enabled,
                          self.touch_on, self.aim_on, self.res.frames("player", self.theme.player))

    # ------------------------------------------------------------------ states
    def to_menu(self):
        if self.state in ("play", "paused"):
            self._finish_run(show_panel=False)
        self.state = "menu"
        self.world.end_run()
        self.world.player.reset()
        self.hud.hide()
        self.hud.show()            # stats bar stays drawn on the title screen
        self.gameover.hide()
        self.pause_panel.hide()
        self.touch.hide()
        self.menu.show()
        self.refresh_menu()
        self.sound.play_stage(0)

    def start_run(self):
        if self.state not in ("menu", "gameover"):
            return
        self.sound.play("click")
        self.menu.hide()
        self.gameover.hide()
        self.hud.show()
        if self.touch_on:
            self.touch.show()
        rec = self.save.record(self.theme.key)
        self.record = dict(rec)
        self.world.start_run(rec, seed=random.randrange(1 << 30))
        self.state = "play"
        self.run_time = 0.0
        self.health = config.HEALTH_MAX
        self.walls_passed = 0
        self.progress = 0
        self.invuln = 0.0
        self.swish_t = 0.0
        self.swish_n = 0
        self.cliff_cd = 0.0
        self.passed_last = rec["last_distance"] <= 20
        self.passed_best = rec["best_time"] <= 0
        self.sound.play_stage(0, fade=1.0)

    def toggle_pause(self):
        if self.state == "play":
            self.state = "paused"
            self.pause_panel.show()
        elif self.state == "paused":
            self.state = "play"
            self.pause_panel.hide()

    def _finish_run(self, show_panel=True):
        new_best = self.save.finish_run(self.theme.key, self.run_time, self.world.player.y)
        if show_panel:
            rec = self.save.record(self.theme.key)
            self.gameover.show(self.run_time, self.walls_passed, rec["best_time"], new_best)
        return new_best

    def game_over(self):
        self.state = "gameover"
        self.hud.banner.setText("")
        self.sound.play("gameover")
        self.sound.stop_music()
        self.touch.hide()
        self._finish_run()
        self.world.bubbles.spawn(self.world.player.x, self.world.player.y, self.world.player.z, count=25,
                                 spread=0.8)

    def _restore_window_size(self):
        """Ask for the saved size again once the window is open.  Some desktops
        (e.g. GNOME on Wayland) ignore the size requested when the window is
        created, so the request is repeated after it appears."""
        from panda3d.core import WindowProperties
        self._restore_target = None
        saved = self.save["window"] or {}
        if self.args.offscreen or self.args.fullscreen or self.args.width or self.args.height:
            return
        if not saved.get("size"):
            return
        w, h = int(saved["size"][0]), int(saved["size"][1])
        props = self.base.win.getProperties()
        if props.hasSize() and (props.getXSize(), props.getYSize()) == (w, h):
            return                  # it opened at the right size; leave it alone
        self._restore_target = (w, h)
        self._restore_deadline = self.base.clock.getRealTime() + 2.0
        wp = WindowProperties()
        wp.setSize(int(w), int(h))
        self.base.win.requestProperties(wp)

    def _on_window_event(self, win):
        # compare with == : Panda3D may hand back a different Python object for
        # the same window, so an identity check ("is") would never match
        if win != self.base.win or self.args.offscreen:
            return
        props = win.getProperties()
        if not props.getOpen() or props.getMinimized() or props.getFullscreen():
            return
        size = (props.getXSize(), props.getYSize())
        if self._restore_target:
            # while the saved size is being restored, ignore the interim sizes the
            # desktop reports so they don't overwrite what we're restoring
            if size != self._restore_target and self.base.clock.getRealTime() < self._restore_deadline:
                return
            self._restore_target = None
        entry = {"size": list(size)}
        if props.hasOrigin() and usable_origin([props.getXOrigin(), props.getYOrigin()]):
            entry["origin"] = [props.getXOrigin(), props.getYOrigin()]
        if entry["size"][0] > 0 and entry != self.save["window"]:
            self.save["window"] = entry

    def _load_font(self):
        """Use the Some Time Later font for all text, if it is available."""
        from direct.gui import DirectGuiGlobals as DGG
        if not FONT_PATH.exists():
            return
        font = self.base.loader.loadFont(Filename.fromOsSpecific(str(FONT_PATH)).getFullpath())
        if not font.isValid():
            return
        font.setPixelsPerUnit(96)
        TextNode.setDefaultFont(font)
        DGG.setDefaultFont(font)
        self.font = font

    # ------------------------------------------------------------------ menu keys
    def on_a(self):
        """A: toggle the aim helper on the start screen; zoom in while playing."""
        self.keys["a"] = True
        if self.state == "menu":
            self.keys["a"] = False
            self.toggle_aim()

    def toggle_aim(self):
        self.aim_on = not self.aim_on
        self.save["aim"] = self.aim_on
        self.world.aim_enabled = self.aim_on
        self.sound.play("click")
        if self.state == "menu":
            self.refresh_menu()

    def on_t(self):
        self.next_theme()

    def on_s(self):
        if self.state == "menu":
            self.toggle_sound()

    def toggle_sound(self):
        on = not self.sound.enabled
        self.sound.set_enabled(on)
        self.save["sound"] = on
        if on and not self.sound.current:
            self.sound.play_stage(0)
        self.refresh_menu()

    def toggle_touch(self):
        self.touch_on = not self.touch_on
        self.save["touch"] = self.touch_on
        if self.state == "play" and self.touch_on:
            self.touch.show()
        else:
            self.touch.hide()
        if self.state == "menu":
            self.refresh_menu()

    def on_r(self):
        if self.state == "menu":
            self.reset_best()

    def reset_best(self):
        self.save.reset_best(self.theme.key)
        self.sound.play("click")
        self.refresh_menu()

    def on_q(self):
        if self.state == "menu":
            self.quit()

    def on_escape(self):
        if self.state == "menu":
            self.quit()
        else:
            self.to_menu()

    def on_space(self):
        if self.state in ("menu", "gameover"):
            self.start_run()
        elif self.state == "paused":
            self.toggle_pause()

    def quit(self):
        self.save.save()
        self.base.userExit()

    # ------------------------------------------------------------------ frame
    def _task(self, task):
        dt = min(self.base.clock.getDt(), 1 / 20)
        self.sound.update(dt)
        self.hud.update(dt)
        self.menu.update(dt)
        cam_x = self.world.cam_x
        self.band.update(self.world.time, cam_x)
        if self.state == "play":
            self._update_play(dt)
        elif self.state == "menu":
            self._update_attract(dt)
        elif self.state == "gameover":
            self.world.update(dt, 0, 0, 2.0, 0.0, active=False)
        return task.cont

    def _input(self):
        k = self.keys
        ix = (1 if k["arrow_right"] else 0) - (1 if k["arrow_left"] else 0)
        iz = (1 if k["arrow_up"] else 0) - (1 if k["arrow_down"] else 0)
        zoom = (1 if k["z"] else 0) - (1 if k["a"] else 0)
        return ix, iz, zoom

    def _update_attract(self, dt):
        """Menu background: the fish swims lazily through open water."""
        import math
        p = self.world.player
        t = self.world.time
        iz = 1 if p.z < config.WORLD_H * 0.35 and math.sin(t * 0.7) > 0 else 0
        ix = 1 if math.sin(t * 0.37) > 0.8 else -1 if math.sin(t * 0.37) < -0.8 else 0
        self.world.update(dt, ix, iz, 5.0, 0.0, active=False)

    def _update_play(self, dt):
        from .world.pace import forward_speed
        ix, iz, zoom = self._input()
        w = self.world
        p = w.player
        was_moving = p.moving
        self.run_time += dt
        events, hits = w.update(dt, ix, iz, forward_speed(self.run_time), zoom)

        # swimming swish
        self.swish_t -= dt
        if p.moving and (not was_moving or self.swish_t <= 0):
            self.sound.play(f"swish{self.swish_n % 2}", 0.7, random.uniform(0.9, 1.1))
            self.swish_n += 1
            self.swish_t = 0.5
        if "floor" in events:
            self.sound.play("bounce", 0.8)
        self.cliff_cd = max(0.0, self.cliff_cd - dt)
        if "side" in events and self.cliff_cd <= 0:
            # scraped the side cliff (or it drifted into us): a small health hit
            self.cliff_cd = config.CLIFF_COOLDOWN
            self.health -= config.CLIFF_DAMAGE
            self.sound.play("bounce", 0.7, 0.75)
            self.sound.play("splat", 0.35, 1.4)
            self.hud.popup(f"-{int(config.CLIFF_DAMAGE)}", (1, 0.55, 0.3, 1))
            w.bubbles.spawn(p.x, p.y, p.z, count=6, spread=0.4)
            w.shake = 0.15

        self.invuln = max(0.0, self.invuln - dt)
        for kind, obj in hits:
            if kind == "hit":
                if self.invuln <= 0:
                    dmg = config.WALL_DAMAGE if obj.kind == "wall" else config.OBSTACLE_DAMAGE
                    self.health -= dmg
                    self.invuln = config.HIT_INVULNERABLE
                    self.hud.damage_flash()
                    self.hud.popup(f"-{int(dmg)}", (1, 0.4, 0.3, 1))
                    p.flash = config.HIT_INVULNERABLE
                    w.shake = 0.35
                self.sound.play("splat")
                w.bubbles.spawn(p.x, p.y, p.z, count=8, spread=0.5)
            elif kind == "reward":
                self.health = min(config.HEALTH_MAX, self.health + obj.health)
                self.sound.play(f"chime{obj.level}")
                self.hud.popup(f"+{obj.health}")
            elif kind == "passed":
                if obj.kind == "wall":
                    self.walls_passed += 1
                self.progress += 1
                stage = self.progress // config.MUSIC_STAGE_EVERY
                self.sound.play_stage(stage)

        self.health = min(config.HEALTH_MAX, self.health + config.HEALTH_REGEN * dt)

        if not self.passed_last and p.y > self.record["last_distance"]:
            self.passed_last = True
            self.hud.show_banner("Passed your last run!", (1, 0.85, 0.3, 1))
            self.sound.play("chime1")
        if not self.passed_best and self.run_time > self.record["best_time"]:
            self.passed_best = True
            self.hud.show_banner("NEW BEST TIME!", (0.45, 1, 0.55, 1), 3.5)
            self.sound.play("fanfare")

        best = max(self.record["best_time"], self.run_time)
        self.hud.set_values(self.run_time, self.walls_passed, self.health, best, self.record["last_time"])
        if self.health <= 0:
            self.health = 0
            self.hud.set_values(self.run_time, self.walls_passed, 0, best, self.record["last_time"])
            self.game_over()

    def run(self):
        self.base.run()
