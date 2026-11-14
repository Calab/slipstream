"""Procedural sound effects and music (numpy synthesis -> 16-bit WAV)."""

import wave

import numpy as np

SR = 22050


def write_wav(path, samples, sr=SR):
    s = np.asarray(samples, dtype=np.float32)
    peak = np.max(np.abs(s)) if s.size else 0
    if peak > 0.98:
        s = s * (0.98 / peak)
    data = (s * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(data.tobytes())


def _t(dur):
    return np.arange(int(dur * SR)) / SR


def _noise(n, seed=0):
    return np.random.default_rng(seed).uniform(-1, 1, n)


def _bandpass(x, lo, hi):
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    gain = ((f >= lo) & (f <= hi)).astype(float)
    # soft edges
    gain = np.convolve(gain, np.ones(31) / 31, mode="same")
    return np.fft.irfft(spec * gain, len(x))


def _lowpass(x, cutoff):
    return _bandpass(x, 0, cutoff)


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


# ---------------------------------------------------------------------------
# Sound effects
# ---------------------------------------------------------------------------

def sfx_swish(variant=0):
    dur = 0.38
    t = _t(dur)
    n = _noise(len(t), 10 + variant)
    lo, hi = (500, 2600) if variant == 0 else (380, 2000)
    x = _bandpass(n, lo, hi)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 2
    # a little "whoosh" sweep: amplitude-modulated by a rising/falling shape
    x *= env * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))
    return x * 0.55


def sfx_splat():
    dur = 0.6
    t = _t(dur)
    f = 140 * np.exp(-t * 9) + 40
    thump = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
    n = _lowpass(_noise(len(t), 3), 1800) * np.exp(-t * 14)
    wet = np.zeros_like(t)
    rng = np.random.default_rng(4)
    for _ in range(18):
        i = rng.integers(0, int(len(t) * 0.5))
        L = rng.integers(80, 400)
        seg = np.sin(2 * np.pi * rng.uniform(300, 900) * np.arange(L) / SR) * np.exp(-np.arange(L) / (L / 4))
        wet[i:i + L] += seg[: len(wet[i:i + L])] * rng.uniform(0.1, 0.35)
    return thump * 0.9 + n * 1.2 + wet


def _bell(freq, dur, decay=4.0):
    t = _t(dur)
    s = (np.sin(2 * np.pi * freq * t) + 0.45 * np.sin(2 * np.pi * freq * 2.0 * t) * np.exp(-t * 3)
         + 0.25 * np.sin(2 * np.pi * freq * 3.01 * t) * np.exp(-t * 6))
    return s * np.exp(-t * decay) * np.minimum(1, t * 400)


def sfx_chime(level):
    """Reward jingle; bigger rewards play longer arpeggios."""
    notes = {0: [79, 84], 1: [76, 79, 84], 2: [72, 76, 79, 84], 3: [72, 76, 79, 84, 88, 91]}[level]
    step = 0.075
    dur = step * len(notes) + 0.6
    out = np.zeros(int(dur * SR) + SR)
    for i, m in enumerate(notes):
        b = _bell(midi_hz(m), 0.6)
        s = int(i * step * SR)
        out[s:s + len(b)] += b * 0.4
    return out


def sfx_bounce():
    t = _t(0.28)
    f = 180 + 420 * (t / 0.28)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14)
    return s * 0.6 + sfx_bubbles(0.28, seed=5) * 0.5


def sfx_bubbles(dur=0.5, seed=1):
    out = np.zeros(int(dur * SR))
    rng = np.random.default_rng(seed)
    for _ in range(int(dur * 14)):
        i = rng.integers(0, len(out) - 1)
        L = int(SR * rng.uniform(0.03, 0.07))
        tt = np.arange(L) / SR
        f0 = rng.uniform(500, 1400)
        f = f0 * (1 + tt * 12)
        seg = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 60)
        out[i:i + L] += seg[: len(out[i:i + L])] * rng.uniform(0.2, 0.5)
    return out


def sfx_fanfare():
    notes = [(72, 0.0), (76, 0.12), (79, 0.24), (84, 0.36), (79, 0.52), (84, 0.62)]
    out = np.zeros(int(1.5 * SR))
    for m, st in notes:
        b = _bell(midi_hz(m), 0.8, decay=3)
        s = int(st * SR)
        out[s:s + len(b)] += b * 0.35
    return out


def sfx_gameover():
    out = np.zeros(int(1.9 * SR))
    for i, m in enumerate([67, 63, 60, 55]):
        t = _t(0.6)
        s = (np.sin(2 * np.pi * midi_hz(m) * t) + 0.3 * np.sin(4 * np.pi * midi_hz(m) * t)) * np.exp(-t * 4)
        st = int(i * 0.3 * SR)
        out[st:st + len(s)] += s * 0.4
    return out


def sfx_click():
    t = _t(0.06)
    return np.sin(2 * np.pi * 900 * t) * np.exp(-t * 80) * 0.5


SFX = {
    "swish0": lambda: sfx_swish(0),
    "swish1": lambda: sfx_swish(1),
    "splat": sfx_splat,
    "chime0": lambda: sfx_chime(0),
    "chime1": lambda: sfx_chime(1),
    "chime2": lambda: sfx_chime(2),
    "chime3": lambda: sfx_chime(3),
    "bounce": sfx_bounce,
    "bubbles": lambda: sfx_bubbles(0.7, 9),
    "fanfare": sfx_fanfare,
    "gameover": sfx_gameover,
    "click": sfx_click,
}


# ---------------------------------------------------------------------------
# Music
# ---------------------------------------------------------------------------

SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
}


def _adsr(n, a=0.01, d=0.08, s=0.7, r=0.1):
    t = np.arange(n) / SR
    dur = n / SR
    env = np.where(t < a, t / max(a, 1e-4),
                   np.where(t < a + d, 1 - (1 - s) * (t - a) / max(d, 1e-4), s))
    rel = np.clip((dur - t) / max(r, 1e-4), 0, 1)
    return env * rel


def inst_whistle(freq, dur):
    t = _t(dur)
    vib = 1 + 0.006 * np.sin(2 * np.pi * 5.5 * t) * np.minimum(1, t * 3)
    ph = 2 * np.pi * freq * np.cumsum(vib) / SR
    s = np.sin(ph) + 0.12 * np.sin(2 * ph) + 0.04 * np.sin(3 * ph)
    breath = _noise(len(t), int(freq)) * 0.03
    return (s + breath) * _adsr(len(t), 0.03, 0.1, 0.75, 0.08)


def inst_accordion(freq, dur):
    t = _t(dur)
    out = np.zeros_like(t)
    for det in (0.997, 1.003):
        ph = 2 * np.pi * freq * det * t
        for k, amp in enumerate([1, 0.55, 0.45, 0.28, 0.18, 0.1], start=1):
            out += amp * np.sin(k * ph)
    return out * 0.22 * _adsr(len(t), 0.04, 0.1, 0.8, 0.07)


def inst_marimba(freq, dur):
    t = _t(max(dur, 0.5))
    s = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * freq * 4 * t) * np.exp(-t * 18)
    return s * np.exp(-t * 6) * np.minimum(1, t * 600)


def inst_bass(freq, dur):
    t = _t(dur)
    s = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(4 * np.pi * freq * t) + 0.1 * np.sin(6 * np.pi * freq * t)
    return s * np.exp(-t * 3.0) * _adsr(len(t), 0.005, 0.05, 1.0, 0.05)


def inst_pad(freq, dur):
    t = _t(dur)
    s = np.zeros_like(t)
    for det in (0.995, 1.0, 1.005):
        s += np.sin(2 * np.pi * freq * det * t)
    return s / 3 * _adsr(len(t), min(0.5, dur / 3), 0.2, 0.8, min(0.6, dur / 3))


def drum(kind, seed=0):
    if kind == "low":
        t = _t(0.35)
        f = 110 * np.exp(-t * 8) + 55
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 10)
    if kind == "tap":
        t = _t(0.12)
        return _bandpass(_noise(len(t), seed), 800, 3000) * np.exp(-t * 40) * 0.6
    t = _t(0.08)  # shaker
    return _bandpass(_noise(len(t), seed + 7), 4000, 9000) * np.exp(-t * 50) * 0.35


def ocean_bed(dur, seed=0):
    n = _lowpass(_noise(int(dur * SR), seed), 500)
    t = _t(dur)
    # waves: slow swells whose period divides the loop so it stays seamless
    k = max(1, round(dur / 6.0))
    swell = 0.55 + 0.45 * np.sin(2 * np.pi * k * t / dur) ** 2
    return n * swell * 0.5


INSTRUMENTS = {"whistle": inst_whistle, "accordion": inst_accordion, "marimba": inst_marimba}


def _add(buf, sig, start, gain, loop=True):
    """Mix sig into buf at sample offset start, wrapping around for seamless loops."""
    n = len(buf)
    start %= n
    end = start + len(sig)
    if end <= n:
        buf[start:end] += sig * gain
    else:
        first = n - start
        buf[start:] += sig[:first] * gain
        rest = sig[first:]
        if loop:
            while len(rest):
                k = min(len(rest), n)
                buf[:k] += rest[:k] * gain
                rest = rest[k:]


def _melody(rng, scale, root, chord_roots, beats_per_bar, octave_span=9):
    """Generate a 6/8 shanty-ish melody: list of (start_beat, length_beats, midi)."""
    notes = []
    patterns = [[3, 3], [2, 1, 2, 1], [3, 2, 1], [1, 1, 1, 3], [2, 1, 3], [6]]
    deg = 4
    motif_a = [patterns[rng.integers(len(patterns))] for _ in range(2)]
    for bar, croot in enumerate(chord_roots):
        if bar % 4 in (0, 2):
            pat = motif_a[(bar // 2) % 2]
        else:
            pat = patterns[rng.integers(len(patterns))]
        beat = 0
        for L in pat:
            if beat == 0:
                # strong beat: chord tone
                choices = [croot, croot + 2, croot + 4, croot + 7]
                deg = min(choices, key=lambda c: abs(c - deg) + rng.uniform(0, 2.5))
            else:
                deg += int(rng.choice([-2, -1, -1, 1, 1, 2, 0]))
            deg = int(np.clip(deg, 0, octave_span + 2))
            if bar == len(chord_roots) - 1 and beat + L >= beats_per_bar:
                deg = 7 if deg > 3 else 0  # resolve to the tonic
            o, s = divmod(deg, 7)
            notes.append((bar * beats_per_bar + beat, L, root + 12 * o + scale[s]))
            beat += L
    return notes


def render_music(params, stage, bars=8):
    """Render one looping music stage for a theme.  Higher stages are busier."""
    rng = np.random.default_rng(params["seed"] * 100 + stage)
    scale = SCALES[params["scale"]]
    root = params["root"] + (2 if stage >= 4 else 0)
    bpm = params["bpm"] * (1 + 0.05 * min(stage, 4))
    beats_per_bar = 6                     # 6/8 time, counting eighth notes
    eighth = 60.0 / bpm / 2
    bar_len = eighth * beats_per_bar
    dur = bar_len * bars
    n = int(dur * SR)
    buf = np.zeros(n)
    prog = list(params["progression"])[:bars]
    lead = INSTRUMENTS[params["lead"]]

    def chord(degree):
        return [root - 12 + 12 * ((degree + k) // 7) + scale[(degree + k) % 7] for k in (0, 2, 4)]

    # pad chords (always)
    for b, deg in enumerate(prog):
        for m in chord(deg):
            _add(buf, inst_pad(midi_hz(m), bar_len * 1.05), int(b * bar_len * SR), 0.10)

    # ocean ambience (always)
    buf += ocean_bed(dur, params["seed"])[:n] * (0.35 if stage == 0 else 0.25)

    # melody (always; higher stages double it an octave up)
    mel = _melody(rng, scale, root + 12, prog, beats_per_bar)
    for st, L, m in mel:
        s = int(st * eighth * SR)
        _add(buf, lead(midi_hz(m), L * eighth * 0.95), s, 0.30)
        if stage >= 3:
            _add(buf, inst_marimba(midi_hz(m + 12), L * eighth), s, 0.08)

    # bass from stage 1: "oom-pah" on beats 1 and 4
    if stage >= 1:
        for b, deg in enumerate(prog):
            r = chord(deg)[0] - 12
            for beat, m in ((0, r), (3, r + 7)):
                s = int((b * beats_per_bar + beat) * eighth * SR)
                _add(buf, inst_bass(midi_hz(m), eighth * 2.8), s, 0.35)

    # percussion from stage 2
    if stage >= 2:
        for b in range(bars):
            for beat in range(beats_per_bar):
                s = int((b * beats_per_bar + beat) * eighth * SR)
                if beat in (0, 3):
                    _add(buf, drum("low"), s, 0.45)
                elif stage >= 3 or beat in (2, 5):
                    _add(buf, drum("shaker", b * 6 + beat), s, 0.5)
                if stage >= 4 and beat == 3:
                    _add(buf, drum("tap", b), s, 0.4)

    # counter-melody / harmony from stage 3 (accordion chords on off-beats)
    if stage >= 3:
        for b, deg in enumerate(prog):
            for beat in (1, 2, 4, 5):
                s = int((b * beats_per_bar + beat) * eighth * SR)
                for m in chord(deg):
                    _add(buf, inst_accordion(midi_hz(m + 12), eighth * 0.6), s, 0.05)

    return buf * 0.8


MUSIC_STAGES = 5
