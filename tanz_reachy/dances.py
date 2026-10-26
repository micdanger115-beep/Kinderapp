"""Tänze als Funktionen des Taktschlags (Muster aus ``skills/symbolic-motion.md``).

Jeder Tanz liefert für einen Zeitpunkt ``t_beats`` eine kleine Abweichung von
der Ruheposition. Alle Werte gehen am Ende durch :func:`clamp`, damit die
kindgerechten Grenzen nie überschritten werden – egal, was ein Tanz berechnet.
"""

from dataclasses import dataclass
from typing import Callable

import numpy as np

# Kindgerechte Grenzen, deutlich unter den Hardware-Grenzen (±40° / ±160°).
MAX_TILT_DEG = 12.0  # Roll und Pitch
MAX_YAW_DEG = 20.0
MAX_BODY_YAW_DEG = 20.0
MAX_Z_MM = 8.0
MAX_ANTENNA_DEG = 35.0

TAU = 2.0 * np.pi


@dataclass
class DancePose:
    """Abweichung von der Ruheposition. Winkel in Grad, Höhe in mm."""

    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    z: float = 0.0
    antenna_right: float = 0.0
    antenna_left: float = 0.0
    body_yaw: float = 0.0

    def scaled(self, k: float) -> "DancePose":
        return DancePose(*(k * v for v in self.__dict__.values()))

    def __add__(self, other: "DancePose") -> "DancePose":
        return DancePose(*(a + b for a, b in zip(self.__dict__.values(), other.__dict__.values())))


def clamp(p: DancePose) -> DancePose:
    def c(v: float, lim: float) -> float:
        return float(np.clip(v, -lim, lim))

    return DancePose(
        roll=c(p.roll, MAX_TILT_DEG),
        pitch=c(p.pitch, MAX_TILT_DEG),
        yaw=c(p.yaw, MAX_YAW_DEG),
        z=c(p.z, MAX_Z_MM),
        antenna_right=c(p.antenna_right, MAX_ANTENNA_DEG),
        antenna_left=c(p.antenna_left, MAX_ANTENNA_DEG),
        body_yaw=c(p.body_yaw, MAX_BODY_YAW_DEG),
    )


def _bump(phase: float) -> float:
    """Weicher Hügel 0 → 1 → 0 über eine Periode (keine Ecken, kein Ruck)."""
    return 0.5 * (1.0 - np.cos(TAU * (phase % 1.0)))


def entchen(t: float, bar: int) -> DancePose:
    # Watscheln: seitliches Wiegen alle zwei Schläge, Antennen als Flügel.
    # Takte 7–8 "Köpfchen in das Wasser": Kopf taucht ab, Takte 9–10
    # "Schwänzchen in die Höh'": Kopf geht hoch (das Lied hat 10 Takte).
    sway = np.sin(TAU * t / 2.0)
    bar_in_song = int(t // bar) % 10
    in_bar = _bump((t % bar) / bar)
    dip = in_bar if bar_in_song in (6, 7) else -0.6 * in_bar if bar_in_song in (8, 9) else 0.0
    flap = 15.0 * np.cos(TAU * t / 2.0)
    return DancePose(
        roll=9.0 * sway,
        pitch=10.0 * dip,
        z=3.0 * _bump(t),
        antenna_right=-flap,
        antenna_left=flap,
        body_yaw=6.0 * sway,
    )


def haenschen(t: float, bar: int) -> DancePose:
    # Wandern in die weite Welt: Kopf wippt wie Schritte, schaut sich langsam um.
    look = np.sin(TAU * t / (2 * bar))
    step = _bump(t)
    return DancePose(
        yaw=14.0 * look,
        z=5.0 * step,
        pitch=-3.0 * step,
        roll=3.0 * np.sin(TAU * t / 2.0),
        antenna_right=-10.0 * step,
        antenna_left=10.0 * step,
        body_yaw=12.0 * look,
    )


def jakob(t: float, bar: int) -> DancePose:
    # Glocken: Antennen schwingen wie Glockenklöppel, Kopf nickt im Takt.
    bell = 25.0 * np.sin(TAU * t / 2.0)
    return DancePose(
        pitch=7.0 * np.sin(TAU * t),
        roll=5.0 * np.sin(TAU * t / 2.0),
        antenna_right=bell,
        antenna_left=bell,
        body_yaw=8.0 * np.sin(TAU * t / (2 * bar)),
    )


def stern(t: float, bar: int) -> DancePose:
    # Funkeln: Antennen blinken abwechselnd, Kopf schaut nach oben zum Stern.
    twinkle_r = 20.0 * _bump(t / 2.0)
    twinkle_l = 20.0 * _bump(t / 2.0 + 0.5)
    return DancePose(
        pitch=-6.0 + 2.0 * np.sin(TAU * t / 4.0),
        roll=7.0 * np.sin(TAU * t / 4.0),
        yaw=8.0 * np.sin(TAU * t / (2 * bar)),
        antenna_right=-twinkle_r,
        antenna_left=twinkle_l,
        z=2.0 * _bump(t / 2.0),
    )


def wiegenlied(t: float, bar: int) -> DancePose:
    # Wiegen: langsames Schaukeln über einen ganzen Takt, Antennen sinken ab.
    rock = np.sin(TAU * t / bar)
    return DancePose(
        roll=7.0 * rock,
        pitch=4.0,
        antenna_right=12.0 + 3.0 * rock,
        antenna_left=-12.0 - 3.0 * rock,
        body_yaw=5.0 * rock,
    )


def warten(t_s: float) -> DancePose:
    """Freundliches Warten zwischen den Liedern (Zeit in Sekunden, nicht Schlägen).

    Ruhiges "Atmen", langsames Umschauen und ab und zu ein einladendes
    Antennen-Winken, das zum Antippen auffordert.
    """
    breathe = np.sin(TAU * t_s / 5.0)
    look = np.sin(TAU * t_s / 17.0)
    invite = _bump(t_s / 1.5) if (t_s % 12.0) < 3.0 else 0.0
    return DancePose(
        z=2.5 * breathe,
        pitch=1.5 * breathe,
        yaw=10.0 * look,
        antenna_right=-12.0 * invite,
        antenna_left=12.0 * invite,
    )


def huepfer(phase: float) -> DancePose:
    """Extra-Hüpfer, wenn das Kind während des Lieds eine Antenne drückt (phase 0..1)."""
    if not 0.0 <= phase <= 1.0:
        return DancePose()
    b = _bump(phase)
    return DancePose(z=6.0 * b, pitch=-5.0 * b, antenna_right=-20.0 * b, antenna_left=20.0 * b)


def envelope(t_beats: float, total_beats: float, ramp_beats: float = 2.0) -> float:
    """Blendet die Bewegung am Anfang und Ende des Lieds weich ein und aus."""
    if total_beats <= 0:
        return 0.0
    k = min(1.0, t_beats / ramp_beats, (total_beats - t_beats) / ramp_beats)
    k = float(np.clip(k, 0.0, 1.0))
    return 0.5 * (1.0 - np.cos(np.pi * k))


DANCES: dict[str, Callable[[float, int], DancePose]] = {
    "entchen": entchen,
    "haenschen": haenschen,
    "jakob": jakob,
    "stern": stern,
    "wiegenlied": wiegenlied,
}
