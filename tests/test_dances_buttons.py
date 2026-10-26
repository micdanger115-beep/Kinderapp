import numpy as np
import pytest

from tanz_reachy import dances
from tanz_reachy.buttons import AntennaPressDetector


@pytest.mark.parametrize("name", list(dances.DANCES))
def test_dances_stay_within_child_safe_limits(name):
    fn = dances.DANCES[name]
    for t in np.linspace(0, 80, 4001):
        p = dances.clamp(fn(t, 4) + dances.huepfer((t % 1.0)))
        assert abs(p.roll) <= dances.MAX_TILT_DEG and abs(p.pitch) <= dances.MAX_TILT_DEG
        assert abs(p.yaw) <= dances.MAX_YAW_DEG and abs(p.body_yaw) <= dances.MAX_BODY_YAW_DEG
        assert abs(p.z) <= dances.MAX_Z_MM


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
