import numpy as np

from tanz_reachy.controller import Controller, State, REST_ANTENNAS_RAD, SLEEP_ANTENNAS_RAD
from tanz_reachy.songs import LULLABY, SONGS


class FakeClock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class FakeMedia:
    def __init__(self):
        self.played = []
        self.stopped = 0

    def play_sound(self, path):
        self.played.append(path)

    def stop_playing(self):
        self.stopped += 1


class FakeRobot:
    def __init__(self):
        self.media = FakeMedia()
        self.targets = []
        self.gotos = []
        self.sleeps = 0
        self.calls = []  # Reihenfolge von Motoren-an und Bewegungen
        self.push = None  # Zusatz-Auslenkung der Antennen durch Kinderhand
        self.antennas = list(REST_ANTENNAS_RAD)

    def set_target(self, head, antennas, body_yaw):
        self.targets.append((head, antennas, body_yaw))
        self.antennas = list(antennas)

    def enable_motors(self):
        self.calls.append("enable_motors")

    def goto_target(self, head=None, antennas=None, duration=0.5, body_yaw=0.0):
        self.calls.append("goto_target")
        if antennas is not None and tuple(antennas) == SLEEP_ANTENNAS_RAD:
            self.sleeps += 1
        else:
            self.gotos.append(duration)
        if antennas is not None:
            self.antennas = list(antennas)

    def goto_sleep(self):
        raise AssertionError("goto_sleep spielt go_sleep.wav an der Lautstärkegrenze vorbei")

    def get_present_antenna_joint_positions(self):
        if self.push:
            return [self.antennas[0], self.antennas[1] + self.push]
        return list(self.antennas)


def fake_pose(**kw):
    return kw


def make(tmp_path):
    clock = FakeClock()
    robot = FakeRobot()
    c = Controller(robot, tmp_path, clock=clock, make_head_pose=fake_pose)
    c.start()
    return c, robot, clock


def run_for(c, clock, seconds, robot=None, push_at=None):
    steps = int(seconds / 0.02)
    for _ in range(steps):
        clock.t += 0.02
        c.tick()


def press(c, clock, robot):
    robot.push = 0.6
    run_for(c, clock, 0.1)
    robot.push = None
    run_for(c, clock, 0.1)


def test_antenna_press_starts_next_song_and_returns_to_waiting(tmp_path):
    c, robot, clock = make(tmp_path)
    run_for(c, clock, 3)
    assert c.state == State.WAITING
    press(c, clock, robot)
    assert c.state == State.PLAYING and c.song == SONGS[0]
    assert robot.media.played[-1].endswith("entchen_v040.wav")
    run_for(c, clock, SONGS[0].duration_s + 1)
    assert c.state == State.WAITING
    press(c, clock, robot)
    assert c.song == SONGS[1]


def test_press_during_song_makes_a_hop_not_a_new_song(tmp_path):
    c, robot, clock = make(tmp_path)
    press(c, clock, robot)
    run_for(c, clock, 3)
    press(c, clock, robot)
    assert c.state == State.PLAYING and c.song == SONGS[0]
    assert c.hop_start is not None
    assert len(robot.media.played) == 1


def test_antenna_buttons_can_be_disabled(tmp_path):
    c, robot, clock = make(tmp_path)
    c.send("settings", {"antenna_buttons": False})
    run_for(c, clock, 0.1)
    press(c, clock, robot)
    assert c.state == State.WAITING


def test_volume_is_capped(tmp_path):
    c, robot, clock = make(tmp_path)
    c.send("settings", {"volume": 1.0, "unknown": 3})
    run_for(c, clock, 0.1)
    assert c.settings.volume == 0.6


def test_session_ends_with_lullaby_then_sleep_and_ignores_presses(tmp_path):
    c, robot, clock = make(tmp_path)
    c.send("settings", {"session_minutes": 1})
    run_for(c, clock, 61)
    assert c.state == State.BEDTIME and c.song == LULLABY
    run_for(c, clock, LULLABY.duration_s + 1)
    assert c.state == State.ASLEEP and robot.sleeps == 1
    press(c, clock, robot)
    assert c.state == State.ASLEEP
    c.send("wake")
    run_for(c, clock, 0.1)
    assert c.state == State.WAITING


def test_parent_stop_and_song_choice(tmp_path):
    c, robot, clock = make(tmp_path)
    c.send("play", "stern")
    run_for(c, clock, 2)
    assert c.song.id == "stern"
    c.send("stop")
    run_for(c, clock, 0.1)
    assert c.state == State.WAITING and robot.media.stopped >= 1


def test_motion_is_continuous_across_state_changes(tmp_path):
    c, robot, clock = make(tmp_path)
    run_for(c, clock, 5)
    press(c, clock, robot)
    run_for(c, clock, 4)
    c.send("stop")
    run_for(c, clock, 3)
    keys = ["roll", "pitch", "yaw", "z"]
    for (h1, a1, b1), (h2, a2, b2) in zip(robot.targets, robot.targets[1:]):
        for k in keys:
            assert abs(h1[k] - h2[k]) < 3.0, k
        assert abs(b1 - b2) < np.deg2rad(3.0)
        assert max(abs(x - y) for x, y in zip(a1, a2)) < np.deg2rad(4.0)


def test_invalid_numbers_keep_previous_settings(tmp_path):
    c, robot, clock = make(tmp_path)
    c.send("settings", {"volume": 0.3, "session_minutes": 10})
    run_for(c, clock, 0.1)
    for bad in (float("nan"), float("inf"), "laut", None):
        c.send("settings", {"volume": bad, "session_minutes": bad, "audio_latency_s": bad})
        run_for(c, clock, 0.1)
    assert c.settings.volume == 0.3 and c.settings.session_minutes == 10
    assert c.settings.audio_latency_s == 0.15
    press(c, clock, robot)  # Lied startet trotzdem
    assert c.state == State.PLAYING
    assert c.status()["session_remaining_s"] > 0


def test_stop_during_lullaby_goes_to_sleep(tmp_path):
    c, robot, clock = make(tmp_path)
    c.send("sleep")
    run_for(c, clock, 3)
    assert c.state == State.BEDTIME
    c.send("stop")
    run_for(c, clock, 1)
    assert c.state == State.ASLEEP and robot.sleeps == 1
    assert len(robot.media.played) == 1  # Schlaflied startet nicht neu


def test_start_enables_motors_before_moving(tmp_path):
    c, robot, clock = make(tmp_path)
    assert robot.calls[:2] == ["enable_motors", "goto_target"]


def test_wake_enables_motors_again(tmp_path):
    c, robot, clock = make(tmp_path)
    c.send("sleep")
    c.send("stop")
    run_for(c, clock, 0.1)
    assert c.state == State.ASLEEP
    robot.calls.clear()
    c.send("wake")
    run_for(c, clock, 0.1)
    assert robot.calls[:2] == ["enable_motors", "goto_target"]
    assert c.state == State.WAITING


def test_falling_asleep_plays_no_extra_sound(tmp_path):
    c, robot, clock = make(tmp_path)
    c.send("sleep")
    run_for(c, clock, LULLABY.duration_s + 1)
    assert c.state == State.ASLEEP and robot.sleeps == 1
    assert len(robot.media.played) == 1  # nur das Schlaflied, kein go_sleep.wav


def test_lullaby_is_quieter(tmp_path):
    c, robot, clock = make(tmp_path)
    c.send("sleep")
    run_for(c, clock, 0.1)
    assert robot.media.played[-1].endswith("gute_nacht_v030.wav")  # 0.4 * 0.7


def test_press_after_session_end_does_not_start_new_song(tmp_path):
    c, robot, clock = make(tmp_path)
    c.send("settings", {"session_minutes": 1})
    c.send("play", "stern")
    run_for(c, clock, 0.1)
    clock.t += 61  # Lied endet nach Ablauf der Spielzeit
    robot.push = 0.6  # Kind drückt genau beim Liedende
    run_for(c, clock, 0.1)
    robot.push = None
    run_for(c, clock, 0.1)
    assert c.state == State.BEDTIME and c.song == LULLABY


class FlakyRobot(FakeRobot):
    def __init__(self, failures):
        super().__init__()
        self.failures = failures

    def set_target(self, head, antennas, body_yaw):
        if self.failures > 0:
            self.failures -= 1
            raise ConnectionError("kurz weg")
        super().set_target(head, antennas, body_yaw)


def _run_briefly(c, seconds):
    import threading
    import time

    stop = threading.Event()
    t = threading.Thread(target=c.run, args=(stop,))
    t.start()
    time.sleep(seconds)
    stop.set()
    t.join(timeout=2)
    return t


def test_single_error_does_not_end_app(tmp_path):
    robot = FlakyRobot(failures=3)
    c = Controller(robot, tmp_path, make_head_pose=fake_pose)
    t = _run_briefly(c, 0.3)
    assert not t.is_alive()
    assert len(robot.targets) > 3  # lief nach den Fehlern weiter
    assert robot.gotos[-1] == 1.5  # beim Beenden in Ruheposition


def test_shutdown_while_asleep_keeps_robot_asleep(tmp_path):
    c, robot, clock = make(tmp_path)
    c.state = State.ASLEEP
    stop = __import__("threading").Event()
    stop.set()
    c.start = lambda: None  # schon wach/schlafend, kein Aufwachen beim Start
    c.run(stop)
    assert robot.gotos == [2.0]  # nur das Aufwachen aus make(), kein Ruhe-goto


def test_sleep_pose_matches_sdk():
    import pytest

    sdk = pytest.importorskip("reachy_mini.reachy_mini")
    from tanz_reachy.controller import SLEEP_HEAD_POSE

    assert np.allclose(SLEEP_HEAD_POSE, sdk.SLEEP_HEAD_POSE)
    assert list(SLEEP_ANTENNAS_RAD) == list(sdk.SLEEP_ANTENNAS_JOINT_POSITIONS)
