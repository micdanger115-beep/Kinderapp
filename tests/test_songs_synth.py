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
    # kein Knacken am Anfang, weich ausgeblendet
    assert abs(samples[0]) < 0.01
    assert np.max(np.abs(samples[-50:])) < 0.01


@pytest.mark.parametrize("song", list(ALL_SONGS.values()), ids=lambda s: s.id)
def test_first_note_is_audible(song):
    # Das Einblenden darf den ersten Ton nicht verschlucken.
    samples = synth.render(song, volume=1.0)
    beat = 60.0 / song.bpm * synth.SAMPLE_RATE
    first, second = song.notes[0], song.notes[1]
    peak_first = np.max(np.abs(samples[: int(second.start_beat * beat)]))
    peak_second = np.max(np.abs(samples[int(second.start_beat * beat) : int((second.start_beat + second.beats) * beat)]))
    assert peak_first > 0.5 * peak_second


def test_lullaby_has_both_halves():
    # "Guten Abend, gut' Nacht" und "Morgen früh, wenn Gott will" je Strophe
    assert LULLABY.total_beats / LULLABY.repeats == 48
    pitches = [n.midi for n in LULLABY.notes]
    assert pitches[-1] == note_to_midi("C5")  # endet auf dem Grundton


def test_song_wav_is_cached(tmp_path):
    p1 = synth.song_wav(LULLABY, 0.42, tmp_path)
    mtime = p1.stat().st_mtime_ns
    p2 = synth.song_wav(LULLABY, 0.41, tmp_path)  # gleiche 5-%-Stufe
    assert p1 == p2 and p2.stat().st_mtime_ns == mtime
    assert p1.name == f"gute_nacht_{synth.song_key(LULLABY)}_v040.wav"


def test_changed_song_gets_new_cache_file(tmp_path):
    import dataclasses

    longer = dataclasses.replace(LULLABY, repeats=LULLABY.repeats + 1)
    assert synth.song_key(longer) != synth.song_key(LULLABY)
    old = tmp_path / "gute_nacht_v040.wav"  # Datei aus einer früheren Version
    old.write_bytes(b"alt")
    stale_tmp = tmp_path / "entchen_abc_v040.wav.123.tmp"
    stale_tmp.write_bytes(b"halb")
    pin = tmp_path / "eltern_pin"
    pin.write_text("salz:hash")
    current = synth.song_wav(LULLABY, 0.4, tmp_path)
    synth.clean_cache(tmp_path, [LULLABY])
    assert current.exists() and pin.exists()
    assert not old.exists() and not stale_tmp.exists()
