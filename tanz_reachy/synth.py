"""Kleiner Spieluhr-Synthesizer: macht aus einem :class:`Song` eine WAV-Datei.

Der Klang ist bewusst weich: Sinus-Grundton mit wenigen Obertönen, sanfter
Anschlag, langsames Ausklingen, dazu ein leiser Basston auf jedem Taktanfang.
Keine harten Klicks, keine schrillen Höhen.
"""

import threading
import wave
from pathlib import Path

import numpy as np

from .songs import Song

SAMPLE_RATE = 22050
FADE_S = 0.6  # sanftes Ausblenden am Liedende
FADE_IN_S = 1.5  # Liedanfang leiser, aber schon der erste Ton gut hörbar
FADE_IN_FLOOR = 0.5

# Akkordgrundton je Melodieton (C-Dur, I/IV/V), für die Basslinie
_ROOT_FOR_PITCH_CLASS = {0: 48, 4: 48, 7: 48, 5: 53, 9: 53, 2: 43, 11: 43}


def midi_to_hz(midi: int) -> float:
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def _tone(freq: float, length_s: float, decay_s: float, harmonics: list[float]) -> np.ndarray:
    n = max(1, int(length_s * SAMPLE_RATE))
    t = np.arange(n) / SAMPLE_RATE
    wave_ = np.zeros(n)
    for k, amp in enumerate(harmonics, start=1):
        wave_ += amp * np.sin(2 * np.pi * freq * k * t)
    attack = np.minimum(1.0, t / 0.008)  # 8 ms Anschlag, kein Klicken
    release = np.exp(-t / decay_s)
    tail = np.minimum(1.0, (length_s - t) / 0.03)  # kurz vor dem Ende auf 0
    return wave_ * attack * release * np.clip(tail, 0.0, 1.0)


def render(song: Song, volume: float = 0.4) -> np.ndarray:
    """Erzeugt das Lied als Mono-float32-Array im Bereich [-volume, volume]."""
    beat_s = 60.0 / song.bpm
    total = int((song.duration_s + 1.0) * SAMPLE_RATE)  # 1 s Nachklang
    out = np.zeros(total)

    for note in song.notes:
        if note.midi is None:
            continue
        start = int(note.start_beat * beat_s * SAMPLE_RATE)
        length = note.beats * beat_s + 0.5  # Ton darf etwas nachklingen
        tone = _tone(midi_to_hz(note.midi), length, decay_s=0.45, harmonics=[1.0, 0.25, 0.08])
        end = min(total, start + len(tone))
        out[start:end] += tone[: end - start]

    # Leiser Bass auf jedem Taktanfang gibt dem Kind einen spürbaren Rhythmus.
    bar_beats = song.beats_per_bar
    bar_start = song.pickup_beats
    while bar_start < song.total_beats - 0.01:
        melody_note = next(
            (n for n in song.notes if n.midi is not None and n.start_beat <= bar_start < n.start_beat + n.beats),
            None,
        )
        if melody_note is not None:
            root = _ROOT_FOR_PITCH_CLASS.get(melody_note.midi % 12, 48)
            start = int(bar_start * beat_s * SAMPLE_RATE)
            tone = 0.35 * _tone(midi_to_hz(root), bar_beats * beat_s, decay_s=0.8, harmonics=[1.0, 0.15])
            end = min(total, start + len(tone))
            out[start:end] += tone[: end - start]
        bar_start += bar_beats

    peak = np.max(np.abs(out)) or 1.0
    out = out / peak

    fade_in = int(FADE_IN_S * SAMPLE_RATE)
    out[:fade_in] *= np.linspace(FADE_IN_FLOOR, 1.0, fade_in)
    fade = int(FADE_S * SAMPLE_RATE)
    out[-fade:] *= np.linspace(1.0, 0.0, fade)
    return (out * float(np.clip(volume, 0.0, 1.0))).astype(np.float32)


def write_wav(path: Path, samples: np.ndarray) -> None:
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(pcm.tobytes())


def song_wav(song: Song, volume: float, cache_dir: Path) -> Path:
    """Gibt den Pfad zur WAV-Datei zurück und erzeugt sie bei Bedarf.

    Pro Lied und Lautstärkestufe (in 5-%-Schritten) wird einmal erzeugt und
    danach wiederverwendet, damit der Roboter-Rechner nicht jedes Mal rechnen muss.
    """
    level = int(round(np.clip(volume, 0.0, 1.0) * 20)) * 5
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{song.id}_v{level:03d}.wav"
    if not path.exists():
        # Eigener Temp-Name je Thread: Vorab-Erzeugung und Abspielen können gleichzeitig laufen.
        tmp = path.with_name(f"{path.stem}.{threading.get_ident()}.tmp")
        write_wav(tmp, render(song, level / 100.0))
        tmp.replace(path)
    return path
