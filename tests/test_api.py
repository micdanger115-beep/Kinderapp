import sys
import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tanz_reachy.pin import LOCKOUT_S, MAX_FAILURES, RESET_WINDOW_S, ParentLock

try:
    import reachy_mini  # noqa: F401
except Exception:  # SDK (GStreamer) fehlt auf dem Testrechner: nur die Klassen nachbilden
    stub = types.ModuleType("reachy_mini")
    stub.ReachyMini = object
    stub.ReachyMiniApp = object
    sys.modules["reachy_mini"] = stub

from tanz_reachy.main import register_routes  # noqa: E402

from test_controller import FakeClock, make  # noqa: E402


@pytest.fixture
def api(tmp_path):
    c, robot, clock = make(tmp_path)
    lock_clock = FakeClock()
    lock = ParentLock(tmp_path / "eltern_pin", clock=lock_clock)
    app = FastAPI()
    register_routes(app, c, lock)
    client = TestClient(app)
    client.lock_clock = lock_clock
    return client, c


def queued(c):
    items = []
    while not c.commands.empty():
        items.append(c.commands.get_nowait())
    return items


def set_pin(client, pin="2468"):
    return client.post("/api/pin", json={"new_pin": pin}, headers={"X-Eltern-PIN": ""})


def test_controls_need_pin(api):
    client, c = api
    assert client.get("/api/status").json()["pin_set"] is False
    assert client.post("/api/play", json={}).status_code == 403  # noch kein PIN
    assert set_pin(client).status_code == 200
    assert client.post("/api/play", json={}).status_code == 401
    assert client.post("/api/play", json={}, headers={"X-Eltern-PIN": "0000"}).status_code == 401
    assert client.post("/api/play", json={}, headers={"X-Eltern-PIN": "2468"}).status_code == 200
    assert client.post("/api/wake", headers={"X-Eltern-PIN": "0000"}).status_code == 401
    assert queued(c) == [("play", None)]


def test_calming_controls_work_without_pin_but_not_from_other_sites(api):
    client, c = api
    set_pin(client)
    for path in ("/api/stop", "/api/sleep", "/api/still"):
        assert client.post(path).status_code == 403  # ohne Header: fremde Webseite
        assert client.post(path, headers={"X-Eltern-PIN": ""}).status_code == 200
    assert queued(c) == [("stop", None), ("sleep", None), ("still", None)]


def test_foreign_host_names_are_rejected(api):
    client, c = api
    set_pin(client)
    evil = {"Host": "rebind.example.com", "X-Eltern-PIN": "2468"}
    assert client.get("/api/status", headers=evil).status_code == 400
    assert client.post("/api/still", headers=evil).status_code == 400
    assert client.post("/api/pin", json={"new_pin": "9999"}, headers=evil).status_code == 400
    for host in ("reachy-mini.local:8042", "192.168.1.20:8042", "[fe80::1]:8042", "localhost", "reachy-mini"):
        assert client.get("/api/status", headers={"Host": host}).status_code == 200, host


def test_pin_cannot_be_changed_without_old_pin_after_start_window(api):
    client, _ = api
    set_pin(client)
    client.lock_clock.t += RESET_WINDOW_S + 1
    assert set_pin(client, "1111").status_code == 401
    ok = client.post("/api/pin", json={"new_pin": "1111", "old_pin": "2468"}, headers={"X-Eltern-PIN": ""})
    assert ok.status_code == 200


def test_pin_endpoint_needs_header_and_min_length(api):
    client, _ = api
    assert client.post("/api/pin", json={"new_pin": "2468"}).status_code == 403  # fremde Webseite
    assert set_pin(client, "12").status_code == 422


def test_too_many_wrong_pins_lock_out(api):
    client, _ = api
    set_pin(client)
    for _ in range(MAX_FAILURES):
        client.post("/api/wake", headers={"X-Eltern-PIN": "0000"})
    assert client.post("/api/wake", headers={"X-Eltern-PIN": "2468"}).status_code == 401
    client.lock_clock.t += LOCKOUT_S + 1
    assert client.post("/api/wake", headers={"X-Eltern-PIN": "2468"}).status_code == 200


def test_lockout_is_per_device_and_grows(tmp_path):
    clock = FakeClock()
    lock = ParentLock(tmp_path / "eltern_pin", clock=clock)
    lock.set_pin("2468")
    for _ in range(MAX_FAILURES):
        lock.check("0000", "gast")
    assert not lock.check("2468", "gast")
    assert lock.check("2468", "eltern")  # anderes Gerät ist nicht ausgesperrt
    clock.t += LOCKOUT_S + 1
    for _ in range(MAX_FAILURES):
        lock.check("0000", "gast")
    clock.t += LOCKOUT_S + 1
    assert not lock.check("2468", "gast")  # zweite Sperre dauert doppelt so lang
    clock.t += LOCKOUT_S
    assert lock.check("2468", "gast")


def test_pin_file_is_private_and_corrupt_file_does_not_crash(tmp_path):
    lock = ParentLock(tmp_path / "eltern_pin", clock=FakeClock())
    lock.set_pin("2468")
    assert (tmp_path / "eltern_pin").stat().st_mode & 0o777 == 0o600
    assert list(tmp_path.glob("*.tmp")) == []
    (tmp_path / "eltern_pin").write_text("kaputt")
    assert lock.check("2468") is False


def test_status_reports_system_volume(tmp_path):
    from tanz_reachy.main import SystemVolume

    c, robot, clock = make(tmp_path)
    app = FastAPI()
    register_routes(app, c, ParentLock(tmp_path / "eltern_pin"), SystemVolume(fetch=lambda: 80))
    st = TestClient(app).get("/api/status").json()
    assert st["system_volume"] == 80 and st["system_volume_warn"] == 50


def test_nan_and_unknown_song_are_rejected(api):
    client, c = api
    set_pin(client)
    h = {"X-Eltern-PIN": "2468", "Content-Type": "application/json"}
    for body in ('{"volume": NaN}', '{"session_minutes": Infinity}', '{"audio_latency_s": -Infinity}'):
        assert client.post("/api/settings", content=body, headers=h).status_code == 422
    assert client.post("/api/play", json={"song_id": "nope"}, headers=h).status_code == 404
    assert client.post("/api/play", json={"song_id": "stern"}, headers=h).status_code == 200
    assert queued(c) == [("play", "stern")]
