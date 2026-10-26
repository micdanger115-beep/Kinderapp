import threading
from pathlib import Path

from pydantic import BaseModel
from reachy_mini import ReachyMini, ReachyMiniApp

from .controller import Controller


class SettingsUpdate(BaseModel):
    volume: float | None = None
    session_minutes: float | None = None
    antenna_buttons: bool | None = None
    audio_latency_s: float | None = None


class PlayRequest(BaseModel):
    song_id: str | None = None


class TanzReachy(ReachyMiniApp):
    # Eltern-Webseite (Handy im selben WLAN): http://reachy-mini.local:8042
    custom_app_url: str | None = "http://0.0.0.0:8042"
    # Keine Kamera in Phase 1: spart Rechenzeit auf dem Wireless (CM4).
    request_media_backend: str | None = "gstreamer_no_video"

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event):
        cache_dir = Path.home() / ".cache" / "tanz_reachy"
        controller = Controller(reachy_mini, cache_dir)

        @self.settings_app.get("/api/status")
        def status():
            return controller.status()

        @self.settings_app.post("/api/play")
        def play(req: PlayRequest):
            controller.send("play", req.song_id)
            return {"ok": True}

        @self.settings_app.post("/api/stop")
        def stop():
            controller.send("stop")
            return {"ok": True}

        @self.settings_app.post("/api/sleep")
        def sleep():
            controller.send("sleep")
            return {"ok": True}

        @self.settings_app.post("/api/wake")
        def wake():
            controller.send("wake")
            return {"ok": True}

        @self.settings_app.post("/api/settings")
        def update_settings(update: SettingsUpdate):
            controller.send("settings", update.model_dump(exclude_none=True))
            return {"ok": True}

        # Lieder vorab erzeugen, damit der erste Antennen-Druck sofort Musik macht.
        threading.Thread(target=controller.prerender, daemon=True).start()
        controller.run(stop_event)


if __name__ == "__main__":
    app = TanzReachy()
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
