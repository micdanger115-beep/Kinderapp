import ipaddress
import json
import logging
import math
import threading
import time
import urllib.request
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from reachy_mini import ReachyMini, ReachyMiniApp

from . import synth
from .controller import Controller
from .pin import ParentLock
from .songs import ALL_SONGS

logger = logging.getLogger(__name__)

DAEMON_VOLUME_URL = "http://127.0.0.1:8000/api/volume/current"
SYSTEM_VOLUME_WARN = 50  # ab dieser Grundlautstärke (Prozent) weist die Eltern-Seite darauf hin


class SettingsUpdate(BaseModel):
    volume: float | None = None
    session_minutes: float | None = None
    antenna_buttons: bool | None = None
    audio_latency_s: float | None = None


class PlayRequest(BaseModel):
    song_id: str | None = None


class PinRequest(BaseModel):
    new_pin: str
    old_pin: str | None = None


class TanzReachy(ReachyMiniApp):
    # Eltern-Webseite (Handy im selben WLAN): http://reachy-mini.local:8042
    custom_app_url: str | None = "http://0.0.0.0:8042"
    # Medien-Backend: SDK wählt selbst (auf dem Wireless spielt der Ton dann aus dem Roboter).
    request_media_backend: str | None = None

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event):
        cache_dir = Path.home() / ".cache" / "tanz_reachy"
        synth.clean_cache(cache_dir, list(ALL_SONGS.values()))
        controller = Controller(reachy_mini, cache_dir)
        register_routes(self.settings_app, controller, ParentLock(cache_dir / "eltern_pin"), SystemVolume())

        # Lieder vorab erzeugen, damit der erste Antennen-Druck sofort Musik macht.
        controller.prerender_in_background()
        controller.run(stop_event)


class SystemVolume:
    """Liest die Grundlautstärke des Roboters beim Daemon (nur lesen, nichts verstellen).

    Die Lautstärke der App gilt relativ dazu. Steht die Grundlautstärke hoch,
    weist die Eltern-Seite darauf hin.
    """

    def __init__(self, fetch: Callable[[], int | None] | None = None, max_age_s: float = 30.0) -> None:
        self.fetch = fetch or self._fetch
        self.max_age_s = max_age_s
        self.value: int | None = None
        self.read_at = -math.inf

    @staticmethod
    def _fetch() -> int | None:
        with urllib.request.urlopen(DAEMON_VOLUME_URL, timeout=0.5) as res:
            return int(json.load(res)["volume"])

    def get(self) -> int | None:
        now = time.monotonic()
        if now - self.read_at > self.max_age_s:
            self.read_at = now
            try:
                self.value = self.fetch()
            except Exception:
                logger.debug("Systemlautstärke nicht lesbar", exc_info=True)
                self.value = None
        return self.value


def is_local_host(host: str | None) -> bool:
    """Nur Adressen im Heimnetz, keine öffentlichen Namen (Schutz gegen DNS-Rebinding).

    Wie der Reachy-Daemon: IP-Adresse, ``localhost`` oder ``*.local``, dazu
    Namen ohne Punkt (z. B. ``reachy-mini``). Eine fremde Webseite, die ihren
    Namen auf den Roboter umleitet, kommt mit ihrem eigenen Namen an.
    """
    if not host:
        return False
    if host.startswith("["):  # IPv6 mit Port: [fe80::1]:8042
        name = host[1 : host.find("]")] if "]" in host else ""
    else:
        name = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    name = name.rstrip(".").lower()
    try:
        ipaddress.ip_address(name)
        return True
    except ValueError:
        pass
    return name == "localhost" or name.endswith(".local") or (name != "" and "." not in name)


def register_routes(app, controller: Controller, lock: ParentLock, system_volume: SystemVolume | None = None) -> None:
    system_volume = system_volume or SystemVolume(fetch=lambda: None)

    def local_only(request: Request) -> None:
        if not is_local_host(request.headers.get("host")):
            raise HTTPException(400, "host_not_local")

    def same_page(x_eltern_pin: str | None = Header(default=None)) -> None:
        # Der eigene Header schützt vor fremden Webseiten (CSRF): Browser
        # schicken ihn nur von der eigenen Seite aus. Der Inhalt ist hier egal.
        if x_eltern_pin is None:
            raise HTTPException(403, "header_missing")

    def parent(request: Request, x_eltern_pin: str | None = Header(default=None)) -> None:
        if not lock.is_set:
            raise HTTPException(403, "pin_required")
        if not lock.check(x_eltern_pin, _client(request)):
            raise HTTPException(401, "pin_wrong")

    api = APIRouter(dependencies=[Depends(local_only)])

    @api.get("/api/status")
    def status():
        return {
            **controller.status(),
            "pin_set": lock.is_set,
            "pin_reset_allowed": lock.reset_allowed,
            "system_volume": system_volume.get(),
            "system_volume_warn": SYSTEM_VOLUME_WARN,
        }

    @api.post("/api/pin", dependencies=[Depends(same_page)])
    def set_pin(req: PinRequest, request: Request):
        try:
            ok = lock.set_pin(req.new_pin, req.old_pin, _client(request))
        except ValueError as e:
            raise HTTPException(422, str(e))
        if not ok:
            raise HTTPException(401, "pin_wrong")
        return {"ok": True}

    @api.post("/api/play", dependencies=[Depends(parent)])
    def play(req: PlayRequest):
        if req.song_id is not None and req.song_id not in ALL_SONGS:
            raise HTTPException(404, "unknown_song")
        controller.send("play", req.song_id)
        return {"ok": True}

    # Anhalten, Schlafen und "Sofort still" machen den Roboter nur ruhiger.
    # Sie gehen deshalb ohne PIN, damit z. B. auch ein Babysitter oder ein
    # gesperrtes Handy den Roboter jederzeit stoppen kann.
    @api.post("/api/stop", dependencies=[Depends(same_page)])
    def stop():
        controller.send("stop")
        return {"ok": True}

    @api.post("/api/sleep", dependencies=[Depends(same_page)])
    def sleep():
        controller.send("sleep")
        return {"ok": True}

    @api.post("/api/still", dependencies=[Depends(same_page)])
    def still():
        controller.send("still")
        return {"ok": True}

    @api.post("/api/wake", dependencies=[Depends(parent)])
    def wake():
        controller.send("wake")
        return {"ok": True}

    @api.post("/api/settings", dependencies=[Depends(parent)])
    def update_settings(update: SettingsUpdate):
        values = update.model_dump(exclude_none=True)
        # NaN/unendlich ablehnen (pydantic lässt sie durch, siehe Prüfbericht)
        if any(isinstance(v, float) and not math.isfinite(v) for v in values.values()):
            raise HTTPException(422, "invalid_number")
        controller.send("settings", values)
        return {"ok": True}

    app.include_router(api)


def _client(request: Request) -> str:
    return request.client.host if request.client else ""


if __name__ == "__main__":
    app = TanzReachy()
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
