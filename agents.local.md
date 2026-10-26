# Reachy Mini Local Configuration

## Setup Status
Setup complete: YES (Entwicklung in einer Cloud-Umgebung, nicht auf dem Rechner des Nutzers)

## User Environment
- Robot type: Wireless
- App flavour: Python (on-robot, offline, Kind steuert per Antenne)
- Code: GitHub micdanger115-beep/Kinderapp (kein Hugging-Face-Publish bisher)
- Sprache für Antworten und UI: Deutsch

## Notes for Future Sessions
- Zielgruppe: Kind ca. 1,5 Jahre, spricht noch nicht → keine Spracheingabe.
- Phase 2 (vom Nutzer auf später verschoben): Klatschen per Mikrofon, Kamera/Kuckuck.
- Getestet mit `reachy-mini-daemon --mockup-sim --no-media`; Audio und Antennen-Druck nur am echten Gerät prüfbar.
- Am echten Gerät einstellen: audio_latency_s (controller.py), threshold_rad (buttons.py).
