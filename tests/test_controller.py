import numpy as np

from tanz_reachy.controller import Controller, State, REST_ANTENNAS_RAD
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
        self.push = None  # Zusatz-Auslenkung der Antennen durch Kinderhand
        self.antennas = list(REST_ANTENNAS_RAD)

    def set_target(self, head, antennas, body_yaw):
        self.targets.append((head, antennas, body_yaw))
        self.antennas = list(antennas)

    def goto_target(self, head=None, antennas=None, duration=0.5, body_yaw=0.0):
        self.gotos.append(duration)
        if antennas is not None:
            self.antennas = list(antennas)

    def goto_sleep(self):
        self.sleeps += 1

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
