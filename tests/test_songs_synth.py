import numpy as np
import pytest

from tanz_reachy import synth
from tanz_reachy.songs import ALL_SONGS, LULLABY, SONGS, note_to_midi


def test_note_to_midi():
    assert note_to_midi("A4") == 69
    assert note_to_midi("C5") == 72
    assert note_to_midi("F#4") == 66


@pytest.mark.parametrize("song", list(ALL_SONGS.values()), ids=lambda s: s.id)
def test_songs_fill_whole_bars(song):
    # Jede Wiederholung endet auf einem vollen Takt (Auftakt eingerechnet).
    beats_per_repeat = song.total_beats / song.repeats
    assert beats_per_repeat % song.beats_per_bar == pytest.approx(0)


@pytest.mark.parametrize("song", list(ALL_SONGS.values()), ids=lambda s: s.id)
def test_songs_are_calm_and_short(song):
    assert 60 <= song.bpm <= 110
    assert 15 <= song.duration_s <= 90
    pitches = [n.midi for n in song.notes if n.midi is not None]
    # Spieluhr-Lage, nichts Schrilles
    assert min(pitches) >= note_to_midi("G4") and max(pitches) <= note_to_midi("C6")


def test_render_respects_volume_and_has_soft_edges():
    samples = synth.render(SONGS[0], volume=0.4)
    assert samples.dtype == np.float32
    assert np.max(np.abs(samples)) <= 0.4 + 1e-6
    # weich ein- und ausgeblendet
    assert np.max(np.abs(samples[:50])) < 0.01
    assert np.max(np.abs(samples[-50:])) < 0.01


def test_song_wav_is_cached(tmp_path):
    p1 = synth.song_wav(LULLABY, 0.42, tmp_path)
    mtime = p1.stat().st_mtime_ns
    p2 = synth.song_wav(LULLABY, 0.41, tmp_path)  # gleiche 5-%-Stufe
    assert p1 == p2 and p2.stat().st_mtime_ns == mtime
    assert p1.name == "gute_nacht_v040.wav"
