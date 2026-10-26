"""Antennen als Knöpfe (Muster aus ``skills/interaction-patterns.md``).

Die Antennen-Motoren sind weich geregelt und dürfen gedrückt werden. Ein Druck
ist erkannt, wenn die gemessene Position deutlich von der befohlenen Position
abweicht, und zwar einige Messungen hintereinander. So funktioniert es auch,
während die Antennen selbst tanzen.
"""

from dataclasses import dataclass


@dataclass
class AntennaPressDetector:
    threshold_rad: float = 0.35  # Abweichung, ab der ein Druck zählt
    hold_samples: int = 3  # so viele Messungen hintereinander (bei 50 Hz = 60 ms)
    cooldown_s: float = 1.5  # Entprellen: kleine Hände drücken oft mehrmals

    def __post_init__(self) -> None:
        self._count = 0
        self._last_press_t = -1e9
        self._released = True

    def update(self, t: float, commanded: list[float], present: list[float] | None) -> bool:
        """Gibt ``True`` zurück, genau wenn ein neuer Druck erkannt wurde."""
        if present is None or len(present) != 2:
            return False
        deviation = max(abs(c - p) for c, p in zip(commanded, present))
        if deviation < self.threshold_rad * 0.5:
            # Erst nach dem Loslassen zählt der nächste Druck.
            self._released = True
            self._count = 0
            return False
        if deviation < self.threshold_rad:
            self._count = 0
            return False
        self._count += 1
        if (
            self._count >= self.hold_samples
            and self._released
            and t - self._last_press_t >= self.cooldown_s
        ):
            self._last_press_t = t
            self._released = False
            return True
        return False
