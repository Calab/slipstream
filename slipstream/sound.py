"""Sound effects and cross-fading, stage-based background music.

Each theme has several music "stages" (see assetgen/audio.py).  A run starts
at stage 0 and moves up a stage every MUSIC_STAGE_EVERY walls/obstacles
passed; each change fades the old tune out while the new one fades in.
"""

from . import config
from .assetgen.audio import MUSIC_STAGES


class SoundManager:
    """Plays effects by name and handles the music for the current theme."""

    def __init__(self, base, res, enabled=True):
        self.base = base
        self.res = res
        self.enabled = enabled
        self._sfx = {}            # loaded sound effects by name
        self.theme_key = None
        self.tracks = {}          # loaded music by stage number (current theme)
        self.current = None       # (stage, sound)
        self.fading = []          # sounds fading out
        self.fade_in_time = 2.5
        # ShowBase limits the music manager to one sound at a time, which cuts
        # the old tune off instantly; allow overlap so tunes can crossfade.
        if base.musicManager:
            base.musicManager.setConcurrentSoundLimit(4)
        self._apply_enabled()

    # -- effects -----------------------------------------------------------
    def play(self, name, volume=1.0, rate=1.0):
        """Play sound effect `name`.  rate > 1 plays it faster and higher."""
        if not self.enabled:
            return
        snd = self._sfx.get(name)
        if snd is None:
            snd = self.base.loader.loadSfx(self.res.sfx_path(name))
            self._sfx[name] = snd
        snd.setVolume(volume * config.SFX_VOLUME)
        snd.setPlayRate(rate)
        snd.play()

    # -- music -------------------------------------------------------------
    def set_theme(self, theme_key):
        """Switch to another theme's music (unloads the old theme's tunes)."""
        if theme_key == self.theme_key:
            return
        self.stop_music()
        for s in self.tracks.values():
            s.stop()
        self.tracks = {}
        self.theme_key = theme_key

    def _track(self, stage):
        """(stage index, looping music) for a stage, loading it if needed."""
        stage = self.stage_index(stage)
        if stage not in self.tracks:
            snd = self.base.loader.loadMusic(self.res.music_path(self.theme_key, stage))
            snd.setLoop(True)
            self.tracks[stage] = snd
        return stage, self.tracks[stage]

    @staticmethod
    def stage_index(stage):
        """Stages beyond the last generated one cycle through the final four."""
        if stage < MUSIC_STAGES:
            return stage
        return MUSIC_STAGES - 4 + (stage - MUSIC_STAGES) % 4

    def play_stage(self, stage, fade=3.0):
        """Crossfade to the tune for `stage`: the old one fades out while the
        new one fades in over `fade` seconds."""
        idx, snd = self._track(stage)
        if self.current and self.current[0] == idx:
            return
        if self.current:
            self.fading.append(self.current[1])
        if snd in self.fading:            # coming back to a tune that's fading out
            self.fading.remove(snd)
        else:
            snd.setVolume(0.0 if fade > 0 else config.MUSIC_VOLUME)
            snd.setTime(0)
            snd.play()
        self.current = (idx, snd)
        self.fade_in_time = max(fade, 0.01)
        self._track(stage + 1)            # preload the next tune so it starts without a gap

    def stop_music(self):
        """Fade the current tune out."""
        if self.current:
            self.fading.append(self.current[1])
        self.current = None

    def update(self, dt):
        """Called every frame: move the fades along.  The current tune gets
        louder up to MUSIC_VOLUME; tunes being replaced get quieter and stop."""
        step = dt / self.fade_in_time * config.MUSIC_VOLUME
        if self.current:
            snd = self.current[1]
            snd.setVolume(min(config.MUSIC_VOLUME, snd.getVolume() + step))
        for snd in list(self.fading):
            v = snd.getVolume() - step
            if v <= 0:
                snd.stop()
                self.fading.remove(snd)
            else:
                snd.setVolume(v)

    # -- toggle ------------------------------------------------------------
    def set_enabled(self, on):
        """Sound on/off (the S key)."""
        self.enabled = on
        self._apply_enabled()
        if on and self.current:
            snd = self.current[1]
            if snd.status() != snd.PLAYING:
                snd.play()

    def _apply_enabled(self):
        """Mute or unmute Panda3D's audio managers (music and effects)."""
        for mgr in [self.base.musicManager] + list(self.base.sfxManagerList):
            if mgr:
                mgr.setActive(self.enabled)
