"""Ablaufsteuerung: Warten → Lied + Tanz → Warten → … → Gute-Nacht-Lied → Schlafen.

Die Steuerung kennt den Roboter nur über wenige SDK-Aufrufe, damit sie sich
auch ohne Roboter testen lässt (siehe ``tests/``).
"""

import logging
import math
import queue
import threading
import time
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import numpy as np

from . import dances, synth
from .buttons import AntennaPressDetector
from .dances import DancePose
from .songs import ALL_SONGS, LULLABY, SONGS, Song

logger = logging.getLogger(__name__)

TICK_S = 0.02  # 50 Hz Regelschleife
BLEND_S = 1.2  # weicher Übergang zwischen zwei Zuständen
HOP_S = 0.6
REST_ANTENNAS_RAD = (-0.1745, 0.1745)  # wie INIT_ANTENNAS_JOINT_POSITIONS im SDK
# Schlafstellung wie SLEEP_HEAD_POSE / SLEEP_ANTENNAS_JOINT_POSITIONS im SDK
SLEEP_HEAD_POSE = np.array(
    [
        [0.911, 0.004, 0.413, -0.021],
        [-0.004, 1.0, -0.001, 0.001],
        [-0.413, -0.001, 0.911, -0.044],
        [0.0, 0.0, 0.0, 1.0],
    ]
)
SLEEP_ANTENNAS_RAD = (-3.05, 3.05)
SLEEP_S = 3.0  # langsam einschlafen

MAX_VOLUME = 0.6
LULLABY_VOLUME_FACTOR = 0.7  # Gute-Nacht-Lied leiser als die Tanzlieder
MAX_TICK_ERRORS = 50  # so viele Fehler in Folge (1 s), dann gibt die App auf


class State(str, Enum):
    WAITING = "warten"
    PLAYING = "lied"
    BEDTIME = "gute_nacht"
    ASLEEP = "schlafen"


@dataclass
class Settings:
    volume: float = 0.4  # 0..MAX_VOLUME, wird in die erzeugte Musik eingerechnet
    session_minutes: float = 15.0
    antenna_buttons: bool = True  # Kind darf per Antenne starten
    audio_latency_s: float = 0.15  # Tanz wartet so lange auf den Ton

    def sanitized(self, fallback: "Settings | None" = None) -> "Settings":
        # Ungültige Werte (NaN, unendlich, keine Zahl) behalten den bisherigen Wert.
        fallback = fallback or Settings()

        def num(value: Any, old: float, lo: float, hi: float) -> float:
            try:
                value = float(value)
            except (TypeError, ValueError):
                return old
            return float(np.clip(value, lo, hi)) if math.isfinite(value) else old

        return Settings(
            volume=num(self.volume, fallback.volume, 0.0, MAX_VOLUME),
            session_minutes=num(self.session_minutes, fallback.session_minutes, 1.0, 60.0),
            antenna_buttons=bool(self.antenna_buttons),
            audio_latency_s=num(self.audio_latency_s, fallback.audio_latency_s, 0.0, 1.0),
        )


def smoothstep(k: float) -> float:
    k = float(np.clip(k, 0.0, 1.0))
    return k * k * (3.0 - 2.0 * k)


class Controller:
    def __init__(
        self,
        robot: Any,
        cache_dir: Path,
        clock: Callable[[], float] = time.monotonic,
        make_head_pose: Callable[..., Any] | None = None,
    ) -> None:
        self.robot = robot
        self.cache_dir = cache_dir
        self.clock = clock
        if make_head_pose is None:
            from reachy_mini.utils import create_head_pose

            make_head_pose = create_head_pose
        self.make_head_pose = make_head_pose

        self.settings = Settings()
        self.commands: "queue.Queue[tuple[str, Any]]" = queue.Queue()
        self.detector = AntennaPressDetector()

        self.state = State.WAITING
        self.song: Song | None = None
        self.song_start = 0.0
        self.next_index = 0
        self.session_start = self.clock()
        self.state_start = self.clock()
        self.hop_start: float | None = None
        self.blend_from = DancePose()
        self.last_pose = DancePose()
        self.last_antennas_rad = list(REST_ANTENNAS_RAD)
        self.presses = 0

    # ---------- Befehle von außen (Eltern-Webseite) ----------
    def send(self, name: str, arg: Any = None) -> None:
        self.commands.put((name, arg))

    def status(self) -> dict[str, Any]:
        # Wird aus dem Webserver-Thread gelesen; ein kurz veralteter Wert ist harmlos.
        now = self.clock()
        state, song, settings = self.state, self.song, self.settings
        remaining = max(0.0, settings.session_minutes * 60 - (now - self.session_start))
        return {
            "state": state.value,
            "song": None if song is None else {"id": song.id, "title": song.title, "emoji": song.emoji},
            "song_progress": self._song_progress(now),
            "session_remaining_s": round(remaining) if state in (State.WAITING, State.PLAYING) else 0,
            "settings": asdict(settings),
            "max_volume": MAX_VOLUME,
            "presses": self.presses,
            "songs": [{"id": s.id, "title": s.title, "emoji": s.emoji} for s in SONGS],
        }

    def prerender(self) -> None:
        for song in ALL_SONGS.values():
            synth.song_wav(song, self._volume_for(song), self.cache_dir)

    # ---------- Ablauf ----------
    def start(self) -> None:
        """Sanftes Aufwachen: Motoren an, langsam in die Ruheposition."""
        # Der Daemon lässt den Roboter nach jedem App-Ende mit abgeschalteten
        # Motoren liegen. enable_motors() hält dabei die aktuelle Stellung fest,
        # der Kopf springt also nicht.
        self.robot.enable_motors()
        self.robot.goto_target(
            self.make_head_pose(degrees=True), antennas=list(REST_ANTENNAS_RAD), duration=2.0, body_yaw=0.0
        )
        self.last_pose = DancePose()
        self.last_antennas_rad = list(REST_ANTENNAS_RAD)
        self.session_start = self.clock()
        self._enter(State.WAITING)

    def tick(self) -> None:
        now = self.clock()
        self._handle_commands(now)

        present = None
        try:
            present = list(self.robot.get_present_antenna_joint_positions())
        except Exception:  # Telemetrie kurz nicht verfügbar
            logger.debug("Antennenposition nicht lesbar", exc_info=True)
        if self.detector.update(now, self.last_antennas_rad, present):
            self._on_press(now)

        if self.state == State.ASLEEP:
            return
        if self.state in (State.PLAYING, State.BEDTIME) and self.song is not None:
            if now - self.song_start > self.song.duration_s + self.settings.audio_latency_s + 0.5:
                self._song_finished()
        elif self.state == State.WAITING and self._session_over(now):
            self._start_song(LULLABY, State.BEDTIME)
        if self.state == State.ASLEEP:
            return
        self._apply(self._target_pose(now))

    def run(self, stop_event: threading.Event) -> None:
        self.start()
        next_t = self.clock()
        errors = 0
        try:
            while not stop_event.is_set():
                try:
                    self.tick()
                    errors = 0
                except Exception:
                    # Ein einzelner Fehler (z. B. kurz keine Verbindung) beendet die App nicht.
                    errors += 1
                    logger.warning("Fehler im Steuertakt (%d in Folge)", errors, exc_info=True)
                    if errors >= MAX_TICK_ERRORS:
                        raise
                next_t += TICK_S
                # Nach einem blockierenden Aufruf nicht alle verpassten Takte nachholen.
                next_t = max(next_t, self.clock() - TICK_S)
                time.sleep(max(0.0, next_t - self.clock()))
        finally:
            self._stop_audio()
            if self.state == State.ASLEEP:
                return  # Schlafenden Roboter beim Beenden nicht aufwecken
            try:
                self.robot.goto_target(
                    self.make_head_pose(degrees=True), antennas=list(REST_ANTENNAS_RAD), duration=1.5, body_yaw=0.0
                )
            except Exception:
                logger.warning("Ruheposition beim Beenden nicht erreicht", exc_info=True)

    # ---------- intern ----------
    def _handle_commands(self, now: float) -> None:
        while True:
            try:
                name, arg = self.commands.get_nowait()
            except queue.Empty:
                return
            if name == "settings":
                current = asdict(self.settings)
                merged = {**current, **{k: v for k, v in dict(arg).items() if k in current}}
                old_volume = self.settings.volume
                self.settings = Settings(**merged).sanitized(self.settings)
                if self.settings.volume != old_volume:
                    # Neue Lautstärke im Hintergrund vorbereiten, damit der Tanz nicht stockt.
                    threading.Thread(target=self.prerender, daemon=True).start()
            elif name == "play" and self.state != State.ASLEEP:
                song = ALL_SONGS.get(arg) if arg else None
                self._start_song(song or self._next_song(), State.PLAYING)
            elif name == "stop" and self.state == State.PLAYING:
                self._stop_audio()
                self._enter(State.WAITING)
            elif name == "stop" and self.state == State.BEDTIME:
                # Gute-Nacht-Lied abbrechen heißt: gleich einschlafen, nicht von vorn beginnen.
                self._stop_audio()
                self._song_finished()
            elif name == "sleep" and self.state != State.ASLEEP:
                self._start_song(LULLABY, State.BEDTIME)
            elif name == "wake" and self.state == State.ASLEEP:
                self.start()

    def _on_press(self, now: float) -> None:
        self.presses += 1
        if not self.settings.antenna_buttons:
            return
        if self.state == State.WAITING and not self._session_over(now):
            self._start_song(self._next_song(), State.PLAYING)
        elif self.state == State.PLAYING:
            self.hop_start = now  # Ursache → Wirkung: fröhlicher Extra-Hüpfer

    def _session_over(self, now: float) -> bool:
        return now - self.session_start > self.settings.session_minutes * 60

    def _next_song(self) -> Song:
        song = SONGS[self.next_index % len(SONGS)]
        self.next_index += 1
        return song

    def _volume_for(self, song: Song) -> float:
        factor = LULLABY_VOLUME_FACTOR if song is LULLABY else 1.0
        return self.settings.volume * factor

    def _start_song(self, song: Song, state: State) -> None:
        self._stop_audio()
        path = synth.song_wav(song, self._volume_for(song), self.cache_dir)
        self.song = song
        self._enter(state)
        self.robot.media.play_sound(str(path))
        self.song_start = self.clock()
        logger.info("Spiele %s", song.title)

    def _song_finished(self) -> None:
        if self.state == State.BEDTIME:
            self.song = None
            self.state = State.ASLEEP
            self.state_start = self.clock()
            # Nicht goto_sleep(): das SDK spielt dabei go_sleep.wav in voller
            # Lautstärke, an der Begrenzung der App vorbei.
            self.robot.goto_target(
                SLEEP_HEAD_POSE, antennas=list(SLEEP_ANTENNAS_RAD), duration=SLEEP_S, body_yaw=0.0
            )
            try:
                self.last_antennas_rad = list(self.robot.get_present_antenna_joint_positions())
            except Exception:
                logger.debug("Antennenposition nach dem Einschlafen nicht lesbar", exc_info=True)
            return
        self._enter(State.WAITING)

    def _enter(self, state: State) -> None:
        self.blend_from = self.last_pose
        self.state = state
        self.state_start = self.clock()
        self.hop_start = None
        if state == State.WAITING:
            self.song = None

    def _stop_audio(self) -> None:
        try:
            self.robot.media.stop_playing()
        except Exception:
            logger.debug("stop_playing fehlgeschlagen", exc_info=True)

    def _song_progress(self, now: float) -> float:
        song, start = self.song, self.song_start  # einmal lesen: läuft im Webserver-Thread
        if song is None:
            return 0.0
        return float(np.clip((now - start) / song.duration_s, 0.0, 1.0))

    def _target_pose(self, now: float) -> DancePose:
        if self.state in (State.PLAYING, State.BEDTIME) and self.song is not None:
            song = self.song
            t_beats = (now - self.song_start - self.settings.audio_latency_s) * song.bpm / 60.0
            t_beats = max(0.0, t_beats)
            # Taktschläge relativ zum ersten vollen Takt (nach dem Auftakt)
            pose = dances.DANCES[song.dance](t_beats - song.pickup_beats, song.beats_per_bar)
            pose = pose.scaled(dances.envelope(t_beats, song.total_beats))
            if self.hop_start is not None:
                pose = pose + dances.huepfer((now - self.hop_start) / HOP_S)
        else:
            pose = dances.warten(now - self.state_start)

        k = smoothstep((now - self.state_start) / BLEND_S)
        pose = self.blend_from.scaled(1.0 - k) + pose.scaled(k)
        return dances.clamp(pose)

    def _apply(self, pose: DancePose) -> None:
        self.last_pose = pose
        head = self.make_head_pose(
            z=pose.z,
            roll=pose.roll,
            pitch=pose.pitch,
            # Der Kopf-Yaw gilt im Weltkoordinatensystem: Körperdrehung addieren,
            # damit der Kopf mit dem Körper mitgeht.
            yaw=pose.yaw + pose.body_yaw,
            mm=True,
            degrees=True,
        )
        antennas = [
            REST_ANTENNAS_RAD[0] + np.deg2rad(pose.antenna_right),
            REST_ANTENNAS_RAD[1] + np.deg2rad(pose.antenna_left),
        ]
        self.last_antennas_rad = antennas
        self.robot.set_target(head=head, antennas=antennas, body_yaw=float(np.deg2rad(pose.body_yaw)))
