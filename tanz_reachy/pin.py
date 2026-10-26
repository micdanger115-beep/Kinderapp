"""Eltern-PIN für die Webseite.

Ohne PIN darf niemand im WLAN den Roboter steuern. Der PIN wird beim ersten
Öffnen der Eltern-Webseite festgelegt und nur als salziger Hash gespeichert.
Wer den PIN vergessen hat, startet die App im Reachy-Dashboard neu: In den
ersten Minuten danach darf ein neuer PIN ohne den alten gesetzt werden.
"""

import hashlib
import hmac
import logging
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

MIN_LENGTH = 4
MAX_FAILURES = 5  # danach kurze Sperre gegen Durchprobieren
LOCKOUT_S = 60.0  # verdoppelt sich bei jeder weiteren Sperre desselben Geräts
MAX_LOCKOUT_S = 3600.0
RESET_WINDOW_S = 300.0  # nach dem App-Start darf der PIN neu gesetzt werden


class ParentLock:
    def __init__(self, path: Path, clock: Callable[[], float] = time.monotonic) -> None:
        self.path = path
        self.clock = clock
        self.started = clock()
        # Fehlversuche je Gerät (IP-Adresse): Ein Gast kann so nicht die Eltern aussperren.
        self.failures: dict[str, int] = {}
        self.locked_until: dict[str, float] = {}
        self.lockouts: dict[str, int] = {}
        self._lock = threading.RLock()

    @property
    def is_set(self) -> bool:
        return self.path.exists()

    @property
    def reset_allowed(self) -> bool:
        return self.clock() - self.started < RESET_WINDOW_S

    def _hash(self, pin: str, salt: bytes) -> str:
        return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 100_000).hex()

    def _matches(self, pin: str) -> bool:
        try:
            salt_hex, _, stored = self.path.read_text().strip().partition(":")
            return hmac.compare_digest(self._hash(pin, bytes.fromhex(salt_hex)), stored)
        except (OSError, ValueError):
            logger.warning("PIN-Datei %s ist nicht lesbar", self.path, exc_info=True)
            return False

    def check(self, pin: str | None, client: str = "") -> bool:
        """Prüft den PIN. Nach zu vielen Fehlversuchen wird dieses Gerät eine Weile gesperrt."""
        with self._lock:
            now = self.clock()
            if not pin or not self.is_set or now < self.locked_until.get(client, 0.0):
                return False
            if self._matches(pin):
                self.failures.pop(client, None)
                self.lockouts.pop(client, None)
                return True
            self.failures[client] = self.failures.get(client, 0) + 1
            if self.failures[client] >= MAX_FAILURES:
                self.failures[client] = 0
                strikes = self.lockouts.get(client, 0)
                self.lockouts[client] = strikes + 1
                self.locked_until[client] = now + min(MAX_LOCKOUT_S, LOCKOUT_S * 2**strikes)
            return False

    def set_pin(self, new_pin: str, old_pin: str | None = None, client: str = "") -> bool:
        if len(new_pin) < MIN_LENGTH or len(new_pin) > 64:
            raise ValueError(f"PIN braucht {MIN_LENGTH} bis 64 Zeichen")
        with self._lock:
            if self.is_set and not self.reset_allowed and not self.check(old_pin, client):
                return False
            salt = secrets.token_bytes(16)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(f"{self.path.name}.{secrets.token_hex(4)}.tmp")
            # Gleich mit 0600 anlegen: der Hash ist zu keinem Zeitpunkt für andere lesbar.
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(f"{salt.hex()}:{self._hash(new_pin, salt)}")
            tmp.replace(self.path)
            return True
