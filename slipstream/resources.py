"""Runtime access to assets: textures, sprite frames, sounds.

Every lookup checks the ``custom/`` folder first (same sub-folders and file
names as the generated ``assets/`` folder), so your own art and sounds replace
the generated ones.  ``custom/`` is never modified by the game.
"""

import sys
from pathlib import Path

from panda3d.core import Filename, SamplerState, Texture

from .assetgen import AssetBuilder

CUSTOM_DIR = Path(__file__).resolve().parents[1] / "custom"


def custom_dirs():
    """Folders searched for replacement art and sounds, in order.

    In a packaged build a ``custom`` folder next to the program comes first, so
    players can add their own files without rebuilding; then the ``custom``
    folder bundled into the build (or the project's, when running from source).
    """
    dirs = []
    if getattr(sys, "frozen", False):
        dirs.append(Path(sys.executable).resolve().parent / "custom")
    dirs.append(CUSTOM_DIR)
    return dirs
IMAGE_EXTS = (".png", ".jpg", ".jpeg")
SOUND_EXTS = (".wav", ".ogg", ".mp3", ".flac")


class Resources:
    def __init__(self, base, builder: AssetBuilder, custom_dir=None):
        self.base = base
        self.builder = builder
        self.custom = [Path(custom_dir)] if custom_dir else custom_dirs()
        self._tex = {}
        self._sfx = {}

    def custom_path(self, *parts):
        """The override for an asset in custom/ (any supported extension), or None."""
        for folder in self.custom:
            p = folder.joinpath(*parts)
            exts = IMAGE_EXTS if p.suffix.lower() in IMAGE_EXTS else SOUND_EXTS
            for ext in (p.suffix,) + tuple(e for e in exts if e != p.suffix):
                q = p.with_suffix(ext)
                if q.is_file():
                    return q
        return None

    def path(self, *parts):
        """custom/ override if there is one, otherwise the generated asset."""
        return self.custom_path(*parts) or self.builder.path(*parts)

    def texture(self, *parts, wrap=False, mipmap=True):
        key = parts + (wrap, mipmap)
        if key not in self._tex:
            path = self.path(*parts)
            tex = self.base.loader.loadTexture(Filename.fromOsSpecific(str(path)))
            mode = SamplerState.WM_repeat if wrap else SamplerState.WM_clamp
            tex.setWrapU(mode)
            tex.setWrapV(mode)
            tex.setMinfilter(SamplerState.FT_linear_mipmap_linear if mipmap else SamplerState.FT_linear)
            tex.setMagfilter(SamplerState.FT_linear)
            tex.setAnisotropicDegree(4)
            self._tex[key] = tex
        return self._tex[key]

    def frames(self, folder, name):
        """Animation frames name_0, name_1, ...  If custom/ has a name_0 image,
        only the custom frames are used (any count, even a single frame)."""
        n = 0
        while self.custom_path(folder, f"{name}_{n}.png"):
            n += 1
        if n == 0:
            n = self.builder.frame_count(folder, name)
        return [self.texture(folder, f"{name}_{i}.png") for i in range(n)]

    def sfx_path(self, name):
        return Filename.fromOsSpecific(str(self.path("sfx", f"{name}.wav")))

    def music_path(self, theme_key, stage):
        return Filename.fromOsSpecific(str(self.path("music", f"{theme_key}_{stage}.wav")))

    @staticmethod
    def texture_from_array(rgba, name="dyn"):
        """Create a texture from a HxWx4 uint8 numpy array (row 0 = top)."""
        h, w = rgba.shape[:2]
        tex = Texture(name)
        tex.setup2dTexture(w, h, Texture.T_unsigned_byte, Texture.F_rgba8)
        tex.setRamImageAs(rgba[::-1].tobytes(), "RGBA")
        tex.setWrapU(SamplerState.WM_clamp)
        tex.setWrapV(SamplerState.WM_clamp)
        tex.setMinfilter(SamplerState.FT_linear_mipmap_linear)
        tex.setMagfilter(SamplerState.FT_linear)
        tex.setAnisotropicDegree(4)
        return tex
