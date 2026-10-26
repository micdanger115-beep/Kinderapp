import math
import threading
from pathlib import Path

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel
from reachy_mini import ReachyMini, ReachyMiniApp

from .controller import Controller
from .pin import ParentLock
from .songs import ALL_SONGS


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
        controller = Controller(reachy_mini, cache_dir)
        register_routes(self.settings_app, controller, ParentLock(cache_dir / "eltern_pin"))

        # Lieder vorab erzeugen, damit der erste Antennen-Druck sofort Musik macht.
        threading.Thread(target=controller.prerender, daemon=True).start()
        controller.run(stop_event)


def register_routes(app, controller: Controller, lock: ParentLock) -> None:
    def parent(x_eltern_pin: str | None = Header(default=None)) -> None:
        # Der eigene Header schützt zusätzlich vor fremden Webseiten (CSRF):
        # Browser schicken ihn nur von der eigenen Seite aus.
        if not lock.is_set:
            raise HTTPException(403, "pin_required")
        if not lock.check(x_eltern_pin):
            raise HTTPException(401, "pin_wrong")

    @app.get("/api/status")
    def status():
        return {**controller.status(), "pin_set": lock.is_set, "pin_reset_allowed": lock.reset_allowed}

    @app.post("/api/pin")
    def set_pin(req: PinRequest, x_eltern_pin: str | None = Header(default=None)):
        if x_eltern_pin is None:  # Header muss da sein (CSRF), Inhalt egal
            raise HTTPException(403, "header_missing")
        try:
            ok = lock.set_pin(req.new_pin, req.old_pin)
        except ValueError as e:
            raise HTTPException(422, str(e))
        if not ok:
            raise HTTPException(401, "pin_wrong")
        return {"ok": True}

    @app.post("/api/play", dependencies=[Depends(parent)])
    def play(req: PlayRequest):
        if req.song_id is not None and req.song_id not in ALL_SONGS:
            raise HTTPException(404, "unknown_song")
        controller.send("play", req.song_id)
        return {"ok": True}

    @app.post("/api/stop", dependencies=[Depends(parent)])
    def stop():
        controller.send("stop")
        return {"ok": True}

    @app.post("/api/sleep", dependencies=[Depends(parent)])
    def sleep():
        controller.send("sleep")
        return {"ok": True}

    @app.post("/api/wake", dependencies=[Depends(parent)])
    def wake():
        controller.send("wake")
        return {"ok": True}

    @app.post("/api/settings", dependencies=[Depends(parent)])
    def update_settings(update: SettingsUpdate):
        values = update.model_dump(exclude_none=True)
        # NaN/unendlich ablehnen (pydantic lässt sie durch, siehe Prüfbericht)
        if any(isinstance(v, float) and not math.isfinite(v) for v in values.values()):
            raise HTTPException(422, "invalid_number")
        controller.send("settings", values)
        return {"ok": True}


if __name__ == "__main__":
    app = TanzReachy()
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
