"""Gemeinfreie Kinderlieder als einfache Notenlisten.

Jedes Lied ist eine Folge von Noten im Format ``"<Ton><Oktave>[:<Schläge>]"``,
z. B. ``"G5:2"`` (G in Oktave 5, zwei Schläge lang). Ohne Dauer dauert eine
Note einen Schlag. ``"R"`` ist eine Pause.

Da wir die Musik selbst erzeugen, kennen wir jeden Taktschlag exakt und
können den Tanz perfekt synchronisieren.
"""

from dataclasses import dataclass, field

NOTE_OFFSETS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


@dataclass(frozen=True)
class Note:
    """Eine Note: MIDI-Tonhöhe (``None`` = Pause), Start und Dauer in Schlägen."""

    midi: int | None
    start_beat: float
    beats: float


@dataclass(frozen=True)
class Song:
    """Ein Kinderlied mit Tempo, Taktart und zugehörigem Tanzstil."""

    id: str
    title: str
    emoji: str
    bpm: float
    beats_per_bar: int
    dance: str
    melody: str
    repeats: int = 2
    pickup_beats: float = 0.0  # Auftakt vor dem ersten vollen Takt
    notes: tuple[Note, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "notes", tuple(parse_melody(self.melody, self.repeats)))

    @property
    def total_beats(self) -> float:
        last = self.notes[-1]
        return last.start_beat + last.beats

    @property
    def duration_s(self) -> float:
        return self.total_beats * 60.0 / self.bpm


def note_to_midi(token: str) -> int:
    """Wandelt z. B. ``"C5"`` oder ``"F#4"`` in eine MIDI-Nummer um."""
    name = token[0].upper()
    rest = token[1:]
    shift = 0
    if rest.startswith("#"):
        shift, rest = 1, rest[1:]
    elif rest.startswith("b"):
        shift, rest = -1, rest[1:]
    octave = int(rest)
    return 12 * (octave + 1) + NOTE_OFFSETS[name] + shift


def parse_melody(melody: str, repeats: int = 1) -> list[Note]:
    """Zerlegt eine Melodie-Zeichenkette in Noten mit Startzeitpunkten."""
    tokens = melody.replace("|", " ").split()
    notes: list[Note] = []
    beat = 0.0
    for _ in range(repeats):
        for token in tokens:
            pitch, _, dur = token.partition(":")
            beats = float(dur) if dur else 1.0
            midi = None if pitch.upper() == "R" else note_to_midi(pitch)
            notes.append(Note(midi, beat, beats))
            beat += beats
    return notes


SONGS: list[Song] = [
    Song(
        id="entchen",
        title="Alle meine Entchen",
        emoji="🦆",
        bpm=96,
        beats_per_bar=4,
        dance="entchen",
        melody=(
            "C5 D5 E5 F5 | G5:2 G5:2 | A5 A5 A5 A5 | G5:4 | A5 A5 A5 A5 | G5:4 |"
            " F5 F5 F5 F5 | E5:2 E5:2 | D5 D5 D5 D5 | C5:4"
        ),
    ),
    Song(
        id="haenschen",
        title="Hänschen klein",
        emoji="🎒",
        bpm=100,
        beats_per_bar=4,
        dance="haenschen",
        repeats=1,
        melody=(
            "G5 E5 E5:2 | F5 D5 D5:2 | C5 D5 E5 F5 | G5 G5 G5:2 |"
            " G5 E5 E5:2 | F5 D5 D5:2 | C5 E5 G5 G5 | C5:4 |"
            " D5 D5 D5 D5 | D5 E5 F5:2 | E5 E5 E5 E5 | E5 F5 G5:2 |"
            " G5 E5 E5:2 | F5 D5 D5:2 | C5 E5 G5 G5 | C5:4"
        ),
    ),
    Song(
        id="jakob",
        title="Bruder Jakob",
        emoji="🔔",
        bpm=92,
        beats_per_bar=4,
        dance="jakob",
        melody=(
            "C5 D5 E5 C5 | C5 D5 E5 C5 | E5 F5 G5:2 | E5 F5 G5:2 |"
            " G5:0.5 A5:0.5 G5:0.5 F5:0.5 E5 C5 | G5:0.5 A5:0.5 G5:0.5 F5:0.5 E5 C5 |"
            " C5 G4 C5:2 | C5 G4 C5:2"
        ),
    ),
    Song(
        id="stern",
        title="Blinke, blinke, kleiner Stern",
        emoji="⭐",
        bpm=88,
        beats_per_bar=4,
        dance="stern",
        repeats=1,
        melody=(
            "C5 C5 G5 G5 | A5 A5 G5:2 | F5 F5 E5 E5 | D5 D5 C5:2 |"
            " G5 G5 F5 F5 | E5 E5 D5:2 | G5 G5 F5 F5 | E5 E5 D5:2 |"
            " C5 C5 G5 G5 | A5 A5 G5:2 | F5 F5 E5 E5 | D5 D5 C5:2"
        ),
    ),
]

# Ruhiges Abschlusslied vor dem Einschlafen (Brahms, "Guten Abend, gut' Nacht").
LULLABY = Song(
    id="gute_nacht",
    title="Guten Abend, gut' Nacht",
    emoji="🌙",
    bpm=66,
    beats_per_bar=3,
    dance="wiegenlied",
    repeats=2,
    pickup_beats=1.0,
    melody=(
        # "Guten Abend, gut' Nacht, mit Rosen bedacht, mit Näglein besteckt, schlupf unter die Deck'"
        "E5:0.5 E5:0.5 | G5:1.5 E5:0.5 E5 | G5:2 E5:0.5 G5:0.5 | C6 B5:1.5 A5:0.5 |"
        " A5 G5 D5:0.5 E5:0.5 | F5 D5 D5:0.5 E5:0.5 | F5:2 D5:0.5 F5:0.5 |"
        " B5:0.5 A5:0.5 G5 B5 | C6:2"
        # "Morgen früh, wenn Gott will, wirst du wieder geweckt" (zweimal)
        " C5:0.5 C5:0.5 | C6:2 A5:0.5 F5:0.5 | G5:2 E5:0.5 C5:0.5 | F5 G5 A5 | G5:2"
        " C5:0.5 C5:0.5 | C6:2 A5:0.5 F5:0.5 | G5:2 E5:0.5 C5:0.5 | F5 E5 D5 | C5:2"
    ),
)

ALL_SONGS: dict[str, Song] = {s.id: s for s in [*SONGS, LULLABY]}
