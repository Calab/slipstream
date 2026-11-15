"""Procedural sound effects and music (numpy synthesis -> 16-bit WAV).

A sound here is just a numpy array of samples between -1 and +1, SR of
them per second.  Tones are made by adding sine waves: sin(2*pi*f*t) is a
pure tone of frequency f; adding multiples of f ("harmonics") changes its
character (a whistle has few, a fiddle many).  Multiplying by an
*envelope* shapes its volume over time, e.g. exp(-t * 9) dies away quickly.
Noise filtered to a band of frequencies gives swishes, shakers and splashes.

A pitch that changes over time (a falling "thump") is made with
sin(2*pi * cumsum(f) / SR): the running sum of the frequency is the phase.

Notes are numbered the MIDI way: 60 = middle C, +1 = one semitone up, +12 =
one octave up.  midi_hz() converts a note number to a frequency.
"""

import wave

import numpy as np

SR = 22050          # sample rate: samples per second


def write_wav(path, samples, sr=SR):
    """Save samples (-1..1) as a mono 16-bit WAV file."""
    s = np.asarray(samples, dtype=np.float32)
    # if anything would go past full volume, turn the whole sound down so it
    # doesn't distort
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
    """Time in seconds of each sample of a sound `dur` seconds long."""
    return np.arange(int(dur * SR)) / SR


def _noise(n, seed=0):
    """n samples of white noise (hiss)."""
    return np.random.default_rng(seed).uniform(-1, 1, n)


def _bandpass(x, lo, hi):
    """Keep only the frequencies between lo and hi Hz (via FFT)."""
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    gain = ((f >= lo) & (f <= hi)).astype(float)
    # soft edges
    gain = np.convolve(gain, np.ones(31) / 31, mode="same")
    return np.fft.irfft(spec * gain, len(x))


def _lowpass(x, cutoff):
    """Keep only frequencies below `cutoff` Hz (muffles a sound)."""
    return _bandpass(x, 0, cutoff)


def midi_hz(m):
    """Frequency of MIDI note m (69 = the A above middle C = 440 Hz; each
    semitone multiplies the frequency by 2^(1/12))."""
    return 440.0 * 2 ** ((m - 69) / 12)


# ---------------------------------------------------------------------------
# Sound effects
# ---------------------------------------------------------------------------

def sfx_swish(variant=0):
    """Swimming whoosh: a burst of band-passed noise that swells and fades."""
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
    """Crashing into something: a falling-pitch thump, a muffled splash and
    a sprinkle of short watery blips."""
    dur = 0.6
    t = _t(dur)
    f = 140 * np.exp(-t * 9) + 40            # pitch drops from 180 Hz towards 40 Hz
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
    """A bell-like note: the base tone plus fast-fading overtones, a sharp
    start (the min(1, t*400) ramp, 2.5 ms) and an exponential fade."""
    t = _t(dur)
    s = (np.sin(2 * np.pi * freq * t) + 0.45 * np.sin(2 * np.pi * freq * 2.0 * t) * np.exp(-t * 3)
         + 0.25 * np.sin(2 * np.pi * freq * 3.01 * t) * np.exp(-t * 6))
    return s * np.exp(-t * decay) * np.minimum(1, t * 400)


def sfx_chime(level):
    """Reward jingle; bigger rewards play longer arpeggios."""
    notes = {0: [79, 84], 1: [76, 79, 84], 2: [72, 76, 79, 84], 3: [72, 76, 79, 84, 88, 91]}[level]
    step = 0.075                       # seconds between notes
    dur = step * len(notes) + 0.6
    out = np.zeros(int(dur * SR) + SR)
    for i, m in enumerate(notes):
        b = _bell(midi_hz(m), 0.6)
        s = int(i * step * SR)
        out[s:s + len(b)] += b * 0.4
    return out


def sfx_bounce():
    """Bumping the floor or a cliff: a quick rising "boing" plus bubbles."""
    t = _t(0.28)
    f = 180 + 420 * (t / 0.28)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14)
    return s * 0.6 + sfx_bubbles(0.28, seed=5) * 0.5


def sfx_bubbles(dur=0.5, seed=1):
    """Random little "bloop"s: each a short sine whose pitch rises quickly."""
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
    """New best time: a rising major arpeggio of bells.  (note, start time)."""
    notes = [(72, 0.0), (76, 0.12), (79, 0.24), (84, 0.36), (79, 0.52), (84, 0.62)]
    out = np.zeros(int(1.5 * SR))
    for m, st in notes:
        b = _bell(midi_hz(m), 0.8, decay=3)
        s = int(st * SR)
        out[s:s + len(b)] += b * 0.35
    return out


def sfx_gameover():
    """Four falling notes."""
    out = np.zeros(int(1.9 * SR))
    for i, m in enumerate([67, 63, 60, 55]):
        t = _t(0.6)
        s = (np.sin(2 * np.pi * midi_hz(m) * t) + 0.3 * np.sin(4 * np.pi * midi_hz(m) * t)) * np.exp(-t * 4)
        st = int(i * 0.3 * SR)
        out[st:st + len(s)] += s * 0.4
    return out


def sfx_click():
    """Menu click: a very short, fast-fading 900 Hz beep."""
    t = _t(0.06)
    return np.sin(2 * np.pi * 900 * t) * np.exp(-t * 80) * 0.5


# sound effect name (sfx/<name>.wav, what SoundManager.play() takes) -> generator
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

# the notes of each scale, in semitones above the key's root note
SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
}


def _adsr(n, a=0.01, d=0.08, s=0.7, r=0.1):
    """Classic synthesizer volume envelope, n samples long:
    Attack (rise to full in a seconds), Decay (fall to level s over d seconds),
    Sustain (hold at s), Release (fade to 0 over the final r seconds)."""
    t = np.arange(n) / SR
    dur = n / SR
    env = np.where(t < a, t / max(a, 1e-4),
                   np.where(t < a + d, 1 - (1 - s) * (t - a) / max(d, 1e-4), s))
    rel = np.clip((dur - t) / max(r, 1e-4), 0, 1)
    return env * rel


# --- instruments: each returns one note of the given frequency and length ---

def inst_whistle(freq, dur):
    """Tin whistle: nearly pure tone with vibrato (a slight wobble in pitch)
    and a little breath noise."""
    t = _t(dur)
    vib = 1 + 0.006 * np.sin(2 * np.pi * 5.5 * t) * np.minimum(1, t * 3)
    ph = 2 * np.pi * freq * np.cumsum(vib) / SR
    s = np.sin(ph) + 0.12 * np.sin(2 * ph) + 0.04 * np.sin(3 * ph)
    breath = _noise(len(t), int(freq)) * 0.03
    return (s + breath) * _adsr(len(t), 0.03, 0.1, 0.75, 0.08)


def inst_accordion(freq, dur):
    """Accordion: two slightly out-of-tune reeds (det = detune), each rich in
    harmonics; the detuning gives the typical shimmering beat."""
    t = _t(dur)
    out = np.zeros_like(t)
    for det in (0.997, 1.003):
        ph = 2 * np.pi * freq * det * t
        for k, amp in enumerate([1, 0.55, 0.45, 0.28, 0.18, 0.1], start=1):
            out += amp * np.sin(k * ph)
    return out * 0.22 * _adsr(len(t), 0.04, 0.1, 0.8, 0.07)


def inst_marimba(freq, dur):
    """Marimba: a struck tone that rings on and fades (always at least 0.5 s)."""
    t = _t(max(dur, 0.5))
    s = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * freq * 4 * t) * np.exp(-t * 18)
    return s * np.exp(-t * 6) * np.minimum(1, t * 600)


def inst_bass(freq, dur):
    """Plucked bass note."""
    t = _t(dur)
    s = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(4 * np.pi * freq * t) + 0.1 * np.sin(6 * np.pi * freq * t)
    return s * np.exp(-t * 3.0) * _adsr(len(t), 0.005, 0.05, 1.0, 0.05)


def inst_pad(freq, dur):
    """Soft sustained background chord tone (three slightly detuned sines)."""
    t = _t(dur)
    s = np.zeros_like(t)
    for det in (0.995, 1.0, 1.005):
        s += np.sin(2 * np.pi * freq * det * t)
    return s / 3 * _adsr(len(t), min(0.5, dur / 3), 0.2, 0.8, min(0.6, dur / 3))


def drum(kind, seed=0):
    """Percussion hit: "low" (bass drum), "tap" (wood block) or anything else
    (shaker)."""
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
    """Background sea rumble: muffled noise that swells like waves."""
    n = _lowpass(_noise(int(dur * SR), seed), 500)
    t = _t(dur)
    # waves: slow swells whose period divides the loop so it stays seamless
    k = max(1, round(dur / 6.0))
    swell = 0.55 + 0.45 * np.sin(2 * np.pi * k * t / dur) ** 2
    return n * swell * 0.5


def inst_fiddle(freq, dur):
    """Bowed string: bright sawtooth-like tone with vibrato and a bow attack."""
    t = _t(dur)
    vib = 1 + 0.007 * np.sin(2 * np.pi * 6.0 * t) * np.minimum(1, t * 4)
    ph = 2 * np.pi * freq * np.cumsum(vib) / SR
    out = np.zeros_like(t)
    for k in range(1, 9):
        out += np.sin(k * ph) / k * (1.0 if k < 4 else 0.7)
    scratch = _bandpass(_noise(len(t), int(freq) + 3), 1500, 5000) * np.exp(-t * 40) * 0.15
    return (out * 0.35 + scratch) * _adsr(len(t), 0.02, 0.08, 0.8, 0.05)


# lead instrument name (as used in themes.py) -> function
INSTRUMENTS = {"whistle": inst_whistle, "accordion": inst_accordion, "marimba": inst_marimba,
               "fiddle": inst_fiddle}

# Each theme has MUSIC_STAGES different tunes.  The game moves to the next one
# every 10 walls/obstacles; past the last it alternates the final four.
MUSIC_STAGES = 8
# per stage: how busy the arrangement is (0-4), speed multiplier, key shift
STAGE_INTENSITY = [1, 1, 2, 2, 3, 3, 4, 4]
STAGE_SPEED = [1.15, 1.18, 1.21, 1.24, 1.27, 1.30, 1.33, 1.36]
STAGE_KEY = [0, 5, -3, 2, 0, 5, -3, 2]

# chord progressions (scale degrees, one per bar) for the contrasting B section
# (0 = the home chord, 3 = the fourth chord of the scale, 4 = the fifth, ...)
B_PROGRESSIONS = [
    (3, 3, 0, 0, 4, 4, 0, 0),
    (5, 3, 0, 4, 5, 3, 4, 4),
    (0, 4, 5, 3, 0, 3, 4, 0),
    (3, 4, 0, 5, 3, 4, 4, 0),
]

# rhythm cells (in eighth notes) for 6/8 jigs and 4/4 hornpipes.  Each list
# is one bar: [3, 3] = two long notes, [2, 1, 2, 1] = long-short-long-short...
PATTERNS = {
    6: [[3, 3], [2, 1, 2, 1], [3, 2, 1], [1, 1, 1, 3], [2, 1, 3], [1, 1, 1, 2, 1], [6]],
    8: [[2, 2, 2, 2], [1, 1, 2, 2, 2], [3, 1, 2, 2], [2, 1, 1, 2, 2], [1, 1, 1, 1, 2, 2],
        [3, 1, 3, 1], [4, 4]],
}


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


def _melody(rng, scale, root, chord_roots, beats_per_bar, octave_span=9, bar_offset=0):
    """A shanty-ish melody: list of (start_beat, length_beats, midi).

    Bars 1 and 3 of each four-bar phrase repeat a motif, so tunes are hummable.
    """
    notes = []
    patterns = PATTERNS[beats_per_bar]
    # deg is the current note as a scale step (0 = root, 7 = root an octave
    # up); the melody moves mostly by small steps from note to note
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
                deg += int(rng.choice([-2, -1, -1, 1, 1, 2, 0, 3, -3]))
            deg = int(np.clip(deg, 0, octave_span + 2))
            if bar == len(chord_roots) - 1 and beat + L >= beats_per_bar:
                deg = 7 if deg > 3 else 0  # resolve to the tonic
            o, s = divmod(deg, 7)        # octave and position within the scale
            notes.append(((bar + bar_offset) * beats_per_bar + beat, L, root + 12 * o + scale[s]))
            beat += L
    return notes


def render_music(params, stage):
    """Render one looping tune for a theme.

    Every stage is a different tune: jigs (6/8) and hornpipes (4/4) alternate,
    each with an A section on the theme's chord progression and a contrasting
    B section, a changing lead instrument and key, and an arrangement that gets
    busier and faster as the stages go up.
    """
    stage = min(stage, MUSIC_STAGES - 1)
    # seeded per theme and stage: the same tune comes out every time
    rng = np.random.default_rng(params["seed"] * 100 + stage)
    scale = SCALES[params["scale"]]
    root = params["root"] + STAGE_KEY[stage]
    intensity = STAGE_INTENSITY[stage]
    bpm = params["bpm"] * STAGE_SPEED[stage]
    beats_per_bar = 6 if stage % 2 == 0 else 8      # jig / hornpipe
    leads = [params["lead"], "fiddle", "accordion", params["lead"], "whistle", "fiddle",
             params["lead"], "fiddle"]
    lead = INSTRUMENTS[leads[stage]]
    eighth = 60.0 / bpm / 2                         # length of one eighth note (s)
    bar_len = eighth * beats_per_bar
    prog_a = list(params["progression"])[:8]
    prog_b = list(B_PROGRESSIONS[(params["seed"] + stage) % len(B_PROGRESSIONS)])
    prog = prog_a + prog_b                           # 16 bars: A then B
    bars = len(prog)
    dur = bar_len * bars
    n = int(dur * SR)
    buf = np.zeros(n)                                # the whole tune is mixed into this
    strong = (0, 3) if beats_per_bar == 6 else (0, 4)   # accented eighths in each bar

    def chord(degree):
        """The three notes (1st, 3rd, 5th) of the chord on scale step `degree`,
        an octave below the root."""
        return [root - 12 + 12 * ((degree + k) // 7) + scale[(degree + k) % 7] for k in (0, 2, 4)]

    def at(bar, beat):
        """Sample position of eighth-note `beat` in bar `bar`."""
        return int((bar * beats_per_bar + beat) * eighth * SR)

    # pad chords and ocean ambience (always)
    for b, deg in enumerate(prog):
        for m in chord(deg):
            _add(buf, inst_pad(midi_hz(m), bar_len * 1.05), at(b, 0), 0.08)
    buf += ocean_bed(dur, params["seed"])[:n] * 0.22

    # melody: A and B sections are composed separately
    mel = (_melody(rng, scale, root + 12, prog_a, beats_per_bar) +
           _melody(rng, scale, root + 12, prog_b, beats_per_bar, bar_offset=8))
    for st, L, m in mel:
        s = int(st * eighth * SR)
        _add(buf, lead(midi_hz(m), L * eighth * 0.95), s, 0.30)
        if intensity >= 3:
            _add(buf, inst_marimba(midi_hz(m + 12), L * eighth), s, 0.07)
        if intensity >= 4:  # harmony a third below in the B section
            if st >= 8 * beats_per_bar:
                # find which scale step the melody note is, then go two steps down
                deg_idx = min(range(7), key=lambda i: abs((root + 12 + scale[i]) % 12 - m % 12))
                h = m - (scale[deg_idx] - scale[(deg_idx - 2) % 7]) % 12
                _add(buf, inst_accordion(midi_hz(h), L * eighth * 0.9), s, 0.09)

    # bass: "oom-pah" on the strong beats; walking eighths at full intensity
    for b, deg in enumerate(prog):
        r = chord(deg)[0] - 12
        if intensity >= 4:
            steps = [r, r + 7, r + 12, r + 7] * 2
            for i in range(0, beats_per_bar, 2):
                _add(buf, inst_bass(midi_hz(steps[i // 2]), eighth * 1.8), at(b, i), 0.3)
        else:
            for beat, m in zip(strong, (r, r + 7)):
                _add(buf, inst_bass(midi_hz(m), eighth * 2.6), at(b, beat), 0.33)

    # percussion: a heartbeat drum from the start, more layers as it builds
    for b in range(bars):
        for beat in range(beats_per_bar):
            s = at(b, beat)
            if beat in strong:
                _add(buf, drum("low"), s, 0.42)
            if intensity >= 2 and beat not in strong:
                _add(buf, drum("shaker", b * 8 + beat), s, 0.45)
            if intensity >= 3 and beat == strong[1]:
                _add(buf, drum("tap", b), s, 0.38)
            if intensity >= 4 and beat == beats_per_bar - 1 and b % 4 == 3:
                _add(buf, drum("tap", b + 50), s + int(eighth * SR / 2), 0.3)

    # rhythm chords on the off-beats (accordion "chop") from intensity 2
    if intensity >= 2:
        offs = (1, 2, 4, 5) if beats_per_bar == 6 else (1, 3, 5, 7)
        for b, deg in enumerate(prog):
            for beat in offs:
                for m in chord(deg):
                    _add(buf, inst_accordion(midi_hz(m + 12), eighth * 0.5), at(b, beat), 0.045)

    return buf * 0.8           # leave some headroom
