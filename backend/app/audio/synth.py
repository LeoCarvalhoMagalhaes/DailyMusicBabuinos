"""Sintetizador do modo demonstração.

Gera, a partir de partituras simples, arranjos originais de melodias em domínio
público. Todo o áudio é produzido por este código (síntese aditiva), portanto não
há gravação de terceiros envolvida. Cada categoria tem um "estilo" de arranjo
(bateria, baixo, acordes e timbre da melodia) para dar identidade ao desafio.

Formato das partituras (ver app/data/scores/melodies.json):
- melodia: "E4 E4 F4:0.5 G4:1.5 R:1" -> nota[:duração em tempos]; R = pausa.
- acordes: "C:4 G:2 Am:2 R:1" -> acorde[:duração]; qualidades: "", m, 7, m7, dim.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

SR = 22050
MELODIES_PATH = Path(__file__).resolve().parent.parent / "data" / "scores" / "melodies.json"

_NOTE_RE = re.compile(r"^([A-G])([#b]?)(-?\d)$")
_CHORD_RE = re.compile(r"^([A-G])([#b]?)(m7|m|7|dim)?$")
_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_QUALITIES = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "m7": (0, 3, 7, 10),
              "dim": (0, 3, 6)}


class ScoreFormatError(ValueError):
    pass


def note_to_midi(token: str) -> int:
    match = _NOTE_RE.match(token)
    if not match:
        raise ScoreFormatError(f"Nota inválida: {token}")
    letter, accidental, octave = match.groups()
    offset = {"#": 1, "b": -1}.get(accidental, 0)
    return 12 * (int(octave) + 1) + _SEMITONES[letter] + offset


def midi_to_freq(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def _split(token: str) -> tuple[str, float]:
    name, _, dur = token.partition(":")
    beats = float(dur) if dur else 1.0
    if beats <= 0:
        raise ScoreFormatError(f"Duração inválida: {token}")
    return name, beats


def parse_melody(text: str) -> list[tuple[int | None, float]]:
    events = []
    for token in text.replace("|", " ").split():
        name, beats = _split(token)
        events.append((None if name == "R" else note_to_midi(name), beats))
    return events


def parse_chords(text: str) -> list[tuple[tuple[int, ...] | None, float]]:
    events = []
    for token in text.replace("|", " ").split():
        name, beats = _split(token)
        if name == "R":
            events.append((None, beats))
            continue
        match = _CHORD_RE.match(name)
        if not match:
            raise ScoreFormatError(f"Acorde inválido: {token}")
        letter, accidental, quality = match.groups()
        root = 48 + _SEMITONES[letter] + {"#": 1, "b": -1}.get(accidental, 0)  # C3
        events.append((tuple(root + i for i in _QUALITIES[quality or ""]), beats))
    return events


@dataclass(frozen=True)
class Song:
    key: str
    bpm: float
    bar_eighths: int
    pickup_beats: float
    melody: list[tuple[int | None, float]]
    chords: list[tuple[tuple[int, ...] | None, float]]

    @property
    def total_beats(self) -> float:
        return sum(b for _, b in self.melody)


@lru_cache(maxsize=1)
def load_songs() -> dict[str, Song]:
    raw = json.loads(MELODIES_PATH.read_text(encoding="utf-8"))
    songs = {}
    for key, spec in raw["melodies"].items():
        song = Song(
            key=key,
            bpm=float(spec["bpm"]),
            bar_eighths=int(spec.get("bar_eighths", 8)),
            pickup_beats=float(spec.get("pickup_beats", 0)),
            melody=parse_melody(spec["melody"]),
            chords=parse_chords(spec["chords"]),
        )
        chord_beats = sum(b for _, b in song.chords)
        if abs(chord_beats - song.total_beats) > 1e-6:
            raise ScoreFormatError(
                f"{key}: melodia ({song.total_beats}) e acordes ({chord_beats}) não batem"
            )
        songs[key] = song
    return songs


# --------------------------------------------------------------------------
# Instrumentos (síntese aditiva vetorizada)
# --------------------------------------------------------------------------

def _t(n: int) -> np.ndarray:
    return np.arange(n, dtype=np.float32) / SR


def _adsr(n: int, attack: float, decay: float, sustain: float, release: float,
          held: int) -> np.ndarray:
    env = np.zeros(n, dtype=np.float32)
    a = max(1, int(attack * SR))
    d = max(1, int(decay * SR))
    r = max(1, int(release * SR))
    held = min(held, n)
    idx = np.arange(n)
    env[:] = sustain
    env[idx < a] = idx[idx < a] / a
    dmask = (idx >= a) & (idx < a + d)
    env[dmask] = 1 - (1 - sustain) * (idx[dmask] - a) / d
    rel = idx >= held
    if rel.any():
        level = env[held - 1] if held > 0 else 0.0
        env[rel] = level * np.clip(1 - (idx[rel] - held) / r, 0, 1)
    return env


def _harmonics(freq: float, n: int, amps: list[float], decays: list[float] | None = None,
               vibrato: float = 0.0) -> np.ndarray:
    t = _t(n)
    phase_mod = 0.0
    if vibrato:
        # `vibrato` é a profundidade relativa da frequência (0.003 ~ 5 cents).
        depth = vibrato * freq / 5.5
        phase_mod = depth * np.sin(2 * np.pi * 5.5 * t) * np.clip(t * 3, 0, 1)
    out = np.zeros(n, dtype=np.float32)
    for k, amp in enumerate(amps, start=1):
        if freq * k >= SR / 2 or amp == 0:
            continue
        wave = amp * np.sin(2 * np.pi * freq * k * t + k * phase_mod)
        if decays:
            wave *= np.exp(-decays[k - 1] * t)
        out += wave.astype(np.float32)
    return out


def inst_piano(freq: float, held: int) -> np.ndarray:
    n = held + int(0.35 * SR)
    amps = [1, 0.45, 0.25, 0.15, 0.08, 0.05]
    wave = _harmonics(freq, n, amps, [2.2 + 1.3 * k for k in range(6)])
    return wave * _adsr(n, 0.004, 0.05, 1.0, 0.25, held)


def inst_pluck(freq: float, held: int) -> np.ndarray:
    n = held + int(0.25 * SR)
    amps = [1, 0.7, 0.5, 0.35, 0.25, 0.18, 0.12, 0.08]
    wave = _harmonics(freq, n, amps, [4 + 3.5 * k for k in range(8)])
    return wave * _adsr(n, 0.002, 0.02, 1.0, 0.15, held)


def inst_saw_lead(freq: float, held: int, drive: float = 0.0) -> np.ndarray:
    n = held + int(0.12 * SR)
    amps = [1 / k for k in range(1, 14)]
    wave = _harmonics(freq, n, amps, vibrato=0.003)
    if drive:
        wave = np.tanh(drive * wave) / np.tanh(drive)
    return wave * _adsr(n, 0.01, 0.1, 0.8, 0.1, held)


def inst_square(freq: float, held: int) -> np.ndarray:
    n = held + int(0.06 * SR)
    amps = [(1 / k if k % 2 else 0) for k in range(1, 16)]
    wave = _harmonics(freq, n, amps)
    return wave * _adsr(n, 0.004, 0.08, 0.7, 0.05, held)


def inst_flute(freq: float, held: int, rng: np.random.Generator) -> np.ndarray:
    n = held + int(0.15 * SR)
    wave = _harmonics(freq, n, [1, 0.2, 0.08], vibrato=0.004)
    breath = rng.normal(0, 0.04, n).astype(np.float32)
    return (wave + breath) * _adsr(n, 0.05, 0.1, 0.85, 0.12, held)


def inst_epiano(freq: float, held: int) -> np.ndarray:
    n = held + int(0.4 * SR)
    t = _t(n)
    mod = np.sin(2 * np.pi * freq * 2 * t) * 1.2 * np.exp(-6 * t)
    wave = np.sin(2 * np.pi * freq * t + mod) * np.exp(-1.6 * t)
    trem = 1 - 0.15 * (0.5 + 0.5 * np.sin(2 * np.pi * 4.5 * t))
    return (wave * trem).astype(np.float32) * _adsr(n, 0.003, 0.05, 1.0, 0.3, held)


def inst_bass(freq: float, held: int, sub: bool = False) -> np.ndarray:
    n = held + int(0.06 * SR)
    amps = [1, 0.15] if sub else [1, 0.5, 0.3, 0.15]
    wave = _harmonics(freq, n, amps)
    return wave * _adsr(n, 0.005, 0.08, 0.85, 0.05, held)


def inst_pad(freqs: tuple[float, ...], held: int) -> np.ndarray:
    n = held + int(0.3 * SR)
    out = np.zeros(n, dtype=np.float32)
    for f in freqs:
        for detune in (0.997, 1.003):
            out += _harmonics(f * detune, n, [1, 0.35, 0.18, 0.1])
    return out / max(1, len(freqs)) * _adsr(n, 0.12, 0.2, 0.75, 0.25, held)


def drum_kick(rng: np.random.Generator) -> np.ndarray:
    n = int(0.32 * SR)
    t = _t(n)
    freq = 45 + 110 * np.exp(-28 * t)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    return (np.sin(phase) * np.exp(-9 * t)).astype(np.float32)


def drum_snare(rng: np.random.Generator, brush: bool = False) -> np.ndarray:
    n = int((0.12 if brush else 0.2) * SR)
    t = _t(n)
    noise = rng.normal(0, 1, n).astype(np.float32)
    noise = np.diff(noise, prepend=0) * 0.6
    tone = 0.0 if brush else 0.5 * np.sin(2 * np.pi * 190 * t) * np.exp(-25 * t)
    decay = 30 if brush else 16
    return ((noise * 0.6 + tone) * np.exp(-decay * t)).astype(np.float32)


def drum_hat(rng: np.random.Generator, open_: bool = False) -> np.ndarray:
    n = int((0.22 if open_ else 0.05) * SR)
    t = _t(n)
    noise = rng.normal(0, 1, n).astype(np.float32)
    noise = np.diff(np.diff(noise, prepend=0), prepend=0) * 0.25
    return (noise * np.exp(-(9 if open_ else 70) * t)).astype(np.float32)


def drum_clap(rng: np.random.Generator) -> np.ndarray:
    n = int(0.18 * SR)
    t = _t(n)
    noise = np.diff(rng.normal(0, 1, n).astype(np.float32), prepend=0)
    env = np.exp(-22 * t)
    for offset in (0.01, 0.02):
        k = int(offset * SR)
        env[k:] += 0.6 * np.exp(-40 * t[: n - k])
    return (noise * env * 0.4).astype(np.float32)


# --------------------------------------------------------------------------
# Estilos de arranjo por categoria
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Style:
    name: str
    lead: str
    target_midi: int
    bpm_factor: float
    swing: float
    gains: tuple[float, float, float, float]  # lead, acordes, baixo, bateria


STYLES = {
    "rock": Style("rock", "drive", 69, 1.05, 0.0, (0.55, 0.30, 0.40, 0.55)),
    "pop": Style("pop", "piano", 74, 1.0, 0.0, (0.60, 0.22, 0.35, 0.40)),
    "rap": Style("rap", "flute", 72, 0.8, 0.18, (0.50, 0.30, 0.55, 0.65)),
    "country": Style("country", "pluck", 72, 1.0, 0.0, (0.60, 0.30, 0.38, 0.30)),
    "eletronica": Style("eletronica", "square", 74, 1.1, 0.0, (0.45, 0.28, 0.42, 0.60)),
    "geral": Style("geral", "piano", 72, 1.0, 0.0, (0.60, 0.25, 0.35, 0.35)),
}


def _drum_hits(style: str, step: int, bar_steps: int) -> list[tuple[str, float]]:
    """Batidas para a colcheia `step` dentro de um compasso de `bar_steps` colcheias."""
    half = bar_steps // 2
    backbeats = {2, 6} if bar_steps == 8 else ({3} if bar_steps == 6 else {2})
    hits: list[tuple[str, float]] = []
    if style == "rock":
        if step in (0, half) or (bar_steps == 8 and step == 5):
            hits.append(("kick", 1.0))
        if step in backbeats:
            hits.append(("snare", 1.0))
        hits.append(("hat", 0.6 if step % 2 else 0.9))
    elif style == "pop":
        if step in (0, half):
            hits.append(("kick", 0.9))
        if step in backbeats:
            hits.append(("clap", 0.9))
        hits.append(("hat", 0.4))
    elif style == "rap":
        if step == 0 or (bar_steps == 8 and step in (3, 5)) or (bar_steps == 6 and step == 4):
            hits.append(("kick", 1.0))
        if step in backbeats:
            hits.append(("snare", 1.0))
        hits.append(("hat", 0.55 if step % 2 else 0.8))
    elif style == "country":
        if step in (0, half):
            hits.append(("kick", 0.7))
        hits.append(("brush", 1.0 if step in backbeats else 0.45))
    elif style == "eletronica":
        if step % 2 == 0:
            hits.append(("kick", 1.0))
        else:
            hits.append(("open_hat", 0.6))
        if step in backbeats:
            hits.append(("clap", 0.8))
    else:  # geral
        if step in (0, half):
            hits.append(("kick", 0.8))
        if step in backbeats:
            hits.append(("snare", 0.6))
        hits.append(("hat", 0.35))
    return hits


def _place(buf: np.ndarray, wave: np.ndarray, start: int, gain: float) -> None:
    if start >= len(buf):
        return
    end = min(len(buf), start + len(wave))
    buf[start:end] += gain * wave[: end - start]


def _octave_shift(song: Song, target: int) -> int:
    pitches = [m for m, _ in song.melody if m is not None]
    median = float(np.median(pitches)) if pitches else target
    return int(round((target - median) / 12)) * 12


def render(song: Song, style_name: str, seconds: float, seed: int = 7) -> np.ndarray:
    """Renderiza `seconds` de áudio (float32 mono, -1..1), repetindo a música se preciso."""
    style = STYLES.get(style_name, STYLES["geral"])
    rng = np.random.default_rng(seed)
    beat = 60.0 / (song.bpm * style.bpm_factor)
    total = int(seconds * SR)
    lead = np.zeros(total, dtype=np.float32)
    chords = np.zeros(total, dtype=np.float32)
    bass = np.zeros(total, dtype=np.float32)
    drums = np.zeros(total, dtype=np.float32)
    shift = _octave_shift(song, style.target_midi)
    loop_seconds = song.total_beats * beat

    def at(beats: float) -> float:
        # Swing: atrasa colcheias pares do tempo (feeling "boom bap").
        whole, frac = divmod(beats, 1.0)
        if style.swing and abs(frac - 0.5) < 1e-6:
            frac += style.swing * 0.5
        return (whole + frac) * beat

    loops = int(np.ceil(seconds / loop_seconds)) if loop_seconds > 0 else 1
    for loop in range(loops):
        base = loop * loop_seconds
        # Melodia
        pos = 0.0
        for midi, beats in song.melody:
            start = base + at(pos)
            pos += beats
            if midi is None or start >= seconds:
                continue
            freq = midi_to_freq(midi + shift)
            held = int(max(0.05, beats * beat * 0.92) * SR)
            if style.lead == "drive":
                wave = inst_saw_lead(freq, held, drive=3.0)
            elif style.lead == "square":
                wave = inst_square(freq, held)
            elif style.lead == "flute":
                wave = inst_flute(freq, held, rng)
            elif style.lead == "pluck":
                wave = inst_pluck(freq, held) + 0.4 * inst_pluck(freq * 2, held)
            else:
                wave = inst_piano(freq, held)
            _place(lead, wave, int(start * SR), 1.0)
        # Acordes e baixo
        pos = 0.0
        for notes, beats in song.chords:
            chord_start, chord_pos = base + pos * beat, pos
            pos += beats
            if notes is None or chord_start >= seconds:
                continue
            root = notes[0]
            freqs = tuple(midi_to_freq(n) for n in notes)
            _render_harmony(style.name, chords, bass, freqs, midi_to_freq(root - 12),
                            chord_pos, beats, base, beat, rng)
        # Bateria (grade de colcheias alinhada ao compasso, após a anacruse)
        bar_steps = song.bar_eighths if song.bar_eighths in (4, 6, 8) else 6
        steps = int(song.total_beats * 2)
        for i in range(steps):
            step_beats = i * 0.5
            if step_beats < song.pickup_beats:
                continue
            step_in_bar = int(round((step_beats - song.pickup_beats) * 2)) % bar_steps
            start = base + at(step_beats)
            if start >= seconds:
                break
            for name, vel in _drum_hits(style.name, step_in_bar, bar_steps):
                wave = {
                    "kick": drum_kick, "snare": drum_snare, "hat": drum_hat, "clap": drum_clap,
                    "brush": lambda r: drum_snare(r, brush=True),
                    "open_hat": lambda r: drum_hat(r, open_=True),
                }[name](rng)
                _place(drums, wave, int(start * SR), vel)

    if style.name == "eletronica":
        # Sidechain: os acordes "respiram" a cada bumbo, marca registrada da EDM.
        period = int(beat * SR)
        duck = np.ones(total, dtype=np.float32)
        ramp = np.linspace(0.25, 1.0, max(1, int(period * 0.6)), dtype=np.float32)
        for start in range(int(song.pickup_beats * beat * SR) % max(1, period), total, period):
            end = min(total, start + len(ramp))
            duck[start:end] = ramp[: end - start]
        chords *= duck

    g_lead, g_chords, g_bass, g_drums = style.gains
    mix = g_lead * lead + g_chords * chords + g_bass * bass + g_drums * drums
    peak = float(np.max(np.abs(mix))) or 1.0
    mix = np.tanh(1.2 * mix / peak) * 0.89
    fade = int(0.006 * SR)
    mix[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
    return mix.astype(np.float32)


def _render_harmony(style: str, chords: np.ndarray, bass: np.ndarray,
                    freqs: tuple[float, ...], bass_freq: float, chord_pos: float,
                    beats: float, base: float, beat: float, rng: np.random.Generator) -> None:
    def put(buf: np.ndarray, wave: np.ndarray, at_beats: float, gain: float = 1.0) -> None:
        _place(buf, wave, int((base + at_beats * beat) * SR), gain)

    eighths = max(1, int(round(beats * 2)))
    if style == "rock":
        power = (freqs[0], freqs[0] * 1.5, freqs[0] * 2)
        for e in range(eighths):
            held = int(beat * 0.45 * SR)
            wave = sum(inst_saw_lead(f / 2, held, drive=4.0) for f in power) / 3
            put(chords, wave, chord_pos + e * 0.5)
            put(bass, inst_bass(bass_freq, held), chord_pos + e * 0.5)
    elif style == "pop":
        put(chords, inst_pad(freqs, int(beats * beat * SR)), chord_pos)
        for q in range(max(1, int(beats))):
            held = int(beat * 0.4 * SR)
            put(bass, inst_bass(bass_freq, held), chord_pos + q)
            put(bass, inst_bass(bass_freq * 2, held), chord_pos + q + 0.5, 0.6)
    elif style == "rap":
        put(chords, sum(inst_epiano(f, int(beats * beat * 0.9 * SR)) for f in freqs) / 2,
            chord_pos)
        put(bass, inst_bass(bass_freq, int(beats * beat * 0.95 * SR), sub=True), chord_pos)
    elif style == "country":
        for q in range(max(1, int(beats))):
            held = int(beat * 0.45 * SR)
            note = bass_freq if q % 2 == 0 else bass_freq * 1.5
            put(bass, inst_bass(note, held), chord_pos + q)
            strum = sum(inst_pluck(f * 2, held) for f in freqs) / len(freqs)
            put(chords, strum, chord_pos + q + 0.5)
    elif style == "eletronica":
        put(chords, inst_pad(tuple(f * 2 for f in freqs), int(beats * beat * SR)), chord_pos)
        for e in range(eighths):
            if e % 2 == 1:
                put(bass, inst_bass(bass_freq, int(beat * 0.4 * SR)), chord_pos + e * 0.5)
    else:  # geral
        for q in range(0, max(1, int(beats)), 2):
            held = int(min(2, beats - q) * beat * 0.9 * SR)
            put(chords, sum(inst_piano(f, held) for f in freqs) / len(freqs), chord_pos + q)
        for q in range(max(1, int(beats))):
            put(bass, inst_bass(bass_freq, int(beat * 0.8 * SR)), chord_pos + q)


def render_int16(song_key: str, style: str, seconds: float) -> np.ndarray:
    songs = load_songs()
    if song_key not in songs:
        raise KeyError(song_key)
    audio = render(songs[song_key], style, seconds, seed=sum(map(ord, song_key + style)))
    return (audio * 32767).astype(np.int16)
