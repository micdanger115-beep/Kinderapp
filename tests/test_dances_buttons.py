import numpy as np
import pytest

from tanz_reachy import dances
from tanz_reachy.buttons import AntennaPressDetector


def _within_limits(p):
    return (
        abs(p.roll) <= dances.MAX_TILT_DEG
        and abs(p.pitch) <= dances.MAX_TILT_DEG
        and abs(p.yaw) <= dances.MAX_YAW_DEG
        and abs(p.body_yaw) <= dances.MAX_BODY_YAW_DEG
        and abs(p.z) <= dances.MAX_Z_MM
        and abs(p.antenna_right) <= dances.MAX_ANTENNA_DEG
        and abs(p.antenna_left) <= dances.MAX_ANTENNA_DEG
    )


@pytest.mark.parametrize("name", list(dances.DANCES))
def test_dances_stay_within_child_safe_limits(name):
    # Die Tänze selbst bleiben in den Grenzen, nicht erst nach clamp().
    fn = dances.DANCES[name]
    for bar in (3, 4):
        for t in np.linspace(0, 80, 4001):
            assert _within_limits(fn(t, bar)), t
    assert all(_within_limits(dances.warten(t)) for t in np.linspace(0, 60, 3001))


def test_clamp_enforces_limits_even_with_hop():
    for t in np.linspace(0, 80, 4001):
        big = dances.DancePose(*(50.0 for _ in range(7)))
        assert _within_limits(dances.clamp(dances.DANCES["jakob"](t, 4) + dances.huepfer(t % 1.0) + big))


@pytest.mark.parametrize("name", list(dances.DANCES))
def test_dances_move_smoothly(name):
    # Keine Sprünge: zwischen zwei 20-ms-Schritten (bei 110 bpm) höchstens wenige Grad.
    fn = dances.DANCES[name]
    dt_beats = 0.02 * 110 / 60
    ts = np.arange(0, 60, dt_beats)
    poses = [fn(t, 4) for t in ts]
    for a, b in zip(poses, poses[1:]):
        for va, vb in zip(a.__dict__.values(), b.__dict__.values()):
            assert abs(va - vb) < 3.0


def test_envelope_starts_and_ends_at_rest():
    assert dances.envelope(0, 32) == 0
    assert dances.envelope(32, 32) == 0
    assert dances.envelope(16, 32) == 1


def test_press_needs_hold_release_and_cooldown():
    d = AntennaPressDetector(threshold_rad=0.3, hold_samples=3, cooldown_s=1.0)
    cmd = [0.0, 0.0]
    pushed = [0.0, 0.5]
    assert not d.update(0.00, cmd, pushed)
    assert not d.update(0.02, cmd, pushed)
    assert d.update(0.04, cmd, pushed)  # dritter Messwert → Druck
    assert not d.update(0.06, cmd, pushed)  # festhalten zählt nicht doppelt
    d.update(0.5, cmd, cmd)  # loslassen
    assert not any(d.update(0.6 + i * 0.02, cmd, pushed) for i in range(5))  # Cooldown
    d.update(1.2, cmd, cmd)
    assert not d.update(1.3, cmd, pushed)
    assert not d.update(1.32, cmd, pushed)
    assert d.update(1.34, cmd, pushed)


def test_small_tracking_lag_is_not_a_press():
    d = AntennaPressDetector()
    assert not any(d.update(i * 0.02, [0.0, 0.0], [0.15, -0.15]) for i in range(100))
    assert not d.update(0, [0.0, 0.0], None)


def test_moves_turn_around_on_the_beat():
    # Umkehrpunkte (größte Auslenkung) auf dem Schlag, nicht auf dem "und".
    for t in (4.0, 5.0, 6.0):
        assert abs(dances.jakob(t, 4).pitch) == pytest.approx(7.0)  # tiefster/höchster Punkt beim Nicken
        assert abs(dances.jakob(t, 4).antenna_right) == pytest.approx(25.0)
        assert abs(dances.entchen(t, 4).roll) == pytest.approx(9.0)
        assert abs(dances.haenschen(t, 4).roll) == pytest.approx(3.0)
    assert dances.jakob(4.0, 4).pitch > 0  # auf dem Schlag nickt der Kopf nach unten


def test_lullaby_antennas_droop_towards_sleep():
    # Schlafstellung im SDK: rechts -3.05 rad, links +3.05 rad
    for t in np.linspace(0, 6, 25):
        pose = dances.wiegenlied(t, 3)
        assert pose.antenna_right < 0 < pose.antenna_left
