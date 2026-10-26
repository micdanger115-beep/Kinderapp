"""Eltern-PIN für die Webseite.

Ohne PIN darf niemand im WLAN den Roboter steuern. Der PIN wird beim ersten
Öffnen der Eltern-Webseite festgelegt und nur als salziger Hash gespeichert.
Wer den PIN vergessen hat, startet die App im Reachy-Dashboard neu: In den
ersten Minuten danach darf ein neuer PIN ohne den alten gesetzt werden.
"""

import hashlib
import hmac
import secrets
import threading
import time
from pathlib import Path
from typing import Callable

MIN_LENGTH = 4
MAX_FAILURES = 5  # danach kurze Sperre gegen Durchprobieren
LOCKOUT_S = 60.0
RESET_WINDOW_S = 300.0  # nach dem App-Start darf der PIN neu gesetzt werden


class ParentLock:
    def __init__(self, path: Path, clock: Callable[[], float] = time.monotonic) -> None:
        self.path = path
        self.clock = clock
        self.started = clock()
        self.failures = 0
        self.locked_until = 0.0
        self._lock = threading.Lock()

    @property
    def is_set(self) -> bool:
        return self.path.exists()

    @property
    def reset_allowed(self) -> bool:
        return self.clock() - self.started < RESET_WINDOW_S

    def _hash(self, pin: str, salt: bytes) -> str:
        return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 100_000).hex()

    def check(self, pin: str | None) -> bool:
        """Prüft den PIN. Nach zu vielen Fehlversuchen wird eine Minute lang alles abgelehnt."""
        with self._lock:
            now = self.clock()
            if not pin or not self.is_set or now < self.locked_until:
                return False
            salt_hex, _, stored = self.path.read_text().strip().partition(":")
            ok = hmac.compare_digest(self._hash(pin, bytes.fromhex(salt_hex)), stored)
            if ok:
                self.failures = 0
            else:
                self.failures += 1
                if self.failures >= MAX_FAILURES:
                    self.failures = 0
                    self.locked_until = now + LOCKOUT_S
            return ok

    def set_pin(self, new_pin: str, old_pin: str | None = None) -> bool:
        if len(new_pin) < MIN_LENGTH or len(new_pin) > 64:
            raise ValueError(f"PIN braucht {MIN_LENGTH} bis 64 Zeichen")
        if self.is_set and not self.reset_allowed and not self.check(old_pin):
            return False
        salt = secrets.token_bytes(16)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(f"{salt.hex()}:{self._hash(new_pin, salt)}")
        tmp.chmod(0o600)
        tmp.replace(self.path)
        return True
