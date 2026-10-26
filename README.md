---
title: Tanz Reachy
emoji: 🎵
colorFrom: yellow
colorTo: red
sdk: static
pinned: false
short_description: Kinderlieder mit Tanz für Kleinkinder
tags:
 - reachy_mini
 - reachy_mini_python_app
---

# Tanz-Reachy 🎵🤖

Reachy Mini spielt gemeinfreie Kinderlieder als sanfte Spieluhr-Musik und tanzt im Takt dazu.
Gemacht für ein Kind von etwa 1,5 Jahren, das noch nicht spricht: Es gibt **keine Spracheingabe**.
Das Kind spielt direkt mit dem Roboter, die Eltern steuern bei Bedarf über eine Handy-Webseite.

## So spielt das Kind

| Das Kind … | Reachy … |
|---|---|
| tippt eine **Antenne** an | wackelt kurz und startet das nächste Lied mit Tanz |
| drückt eine Antenne **während des Lieds** | macht einen fröhlichen Extra-Hüpfer |
| macht nichts | wartet freundlich: atmet ruhig, schaut sich um und winkt ab und zu mit den Antennen |

Nach der eingestellten Spielzeit (Standard 15 Minuten) kommt das Gute-Nacht-Lied, danach schläft Reachy ein.
Im Schlaf reagiert Reachy nicht mehr auf die Antennen. Nur die Eltern können ihn über die Webseite wieder aufwecken.

## Lieder

Alle Melodien sind traditionell und gemeinfrei. Die Musik wird direkt auf dem Roboter erzeugt, es werden also keine fremden Aufnahmen verwendet.

| Lied | Tanz |
|---|---|
| 🦆 Alle meine Entchen | Watscheln, Antennen als Flügel, „Köpfchen in das Wasser“ |
| 🎒 Hänschen klein | wippende Schritte, schaut sich in der weiten Welt um |
| 🔔 Bruder Jakob | Antennen schwingen wie Glocken, Kopf nickt im Takt |
| ⭐ Blinke, blinke, kleiner Stern | Antennen funkeln abwechselnd, Blick nach oben |
| 🌙 Guten Abend, gut' Nacht (Brahms) | langsames Wiegen zum Einschlafen |

## Sicherheit

- Langsame Tempi (66–100 Schläge pro Minute), weiche Bewegungen ohne Ruck, sanfte Übergänge zwischen allen Zuständen.
- Kleine Ausschläge: Kopf neigt sich höchstens 12°, dreht sich höchstens 20°, der Körper dreht sich höchstens 20°.
  Diese Grenzen werden im Code bei jeder Bewegung erzwungen (`tanz_reachy/dances.py`).
- Lautstärke der Musik höchstens 60 % (Standard 40 %), sanft ein- und ausgeblendet.
  Das ist ein Anteil der eingestellten Systemlautstärke des Roboters, die Systemlautstärke selbst begrenzt die App nicht.
  Das Gute-Nacht-Lied ist etwas leiser als die Tanzlieder.
- Ungültige Werte von der Webseite werden abgelehnt, und ein einzelner Fehler (z. B. kurz keine Verbindung) beendet die App nicht.
- Begrenzte Spielzeit, danach Schlafen.
- Beim Beenden der App fährt Reachy immer langsam in die Ruheposition.
- Bitte nur unter Aufsicht benutzen und Reachy stabil auf den Boden oder einen niedrigen Tisch stellen.

## Eltern-Webseite

Wenn die App läuft, im selben WLAN am Handy öffnen: **http://reachy-mini.local:8042**
Dort gibt es Start und Stopp, Liedauswahl, Gute Nacht und Aufwecken, Lautstärke, Spielzeit
und einen Schalter, ob das Kind per Antenne starten darf.

Beim ersten Öffnen legt ihr einen **Eltern-PIN** fest (mindestens 4 Zeichen). Ohne PIN kann niemand
im WLAN den Roboter steuern, auch keine fremde Webseite. Das Handy merkt sich den PIN.
Nach 5 falschen Versuchen ist die Seite eine Minute gesperrt.
PIN vergessen? Die App im Reachy-Dashboard neu starten: In den ersten 5 Minuten danach kann ein neuer PIN festgelegt werden.

Stopp während des Gute-Nacht-Lieds beendet das Lied, und Reachy schläft sofort ein.

## Installation auf dem Reachy Mini Wireless

Das Reachy-Mini-Dashboard installiert Apps aus einem Hugging-Face-Space. Der übliche Weg ist deshalb:

1. Kostenloses Konto auf [huggingface.co](https://huggingface.co) anlegen und am Rechner anmelden: `hf auth login`
2. Dieses Repository klonen und als **privaten** Space veröffentlichen:
   ```bash
   pip install reachy-mini
   reachy-mini-app-assistant publish . --private
   ```
3. Weil der Space privat ist, braucht der Roboter Zugriff darauf: Im Reachy-Mini-Dashboard zuerst einen
   Hugging-Face-Token (unter huggingface.co → Settings → Access Tokens, Leserechte reichen) hinterlegen.
4. Danach im Dashboard die App aus dem privaten Space installieren und starten.

`reachy-mini-app-assistant check .` prüft vorher, ob die App korrekt aufgebaut ist.

## Entwicklung

```bash
pip install -e ".[dev]"
pytest                                        # Tests ohne Roboter
reachy-mini-daemon --mockup-sim --no-media    # Simulation ohne Hardware
python -m tanz_reachy.main                    # App gegen die Simulation starten
```

Aufbau:

- `tanz_reachy/songs.py` – Lieder als Notenlisten
- `tanz_reachy/synth.py` – Spieluhr-Synthesizer (WAV, im Cache `~/.cache/tanz_reachy`)
- `tanz_reachy/dances.py` – Tänze als Funktionen des Taktschlags, Sicherheitsgrenzen
- `tanz_reachy/buttons.py` – Antennen als Knöpfe
- `tanz_reachy/controller.py` – Ablauf: Warten → Lied → Warten → … → Gute Nacht → Schlafen
- `tanz_reachy/main.py` – App-Einstieg und Eltern-API
- `tanz_reachy/static/` – Eltern-Webseite

## Feinabstimmung am echten Roboter

Zwei Werte lassen sich erst am echten Gerät gut einstellen:

- `audio_latency_s` in `controller.py` (Standard 0,15 s): Wenn der Tanz vor oder nach der Musik läuft, diesen Wert anpassen.
- `threshold_rad` in `buttons.py` (Standard 0,35 rad ≈ 20°): Wenn leichte Berührungen nicht erkannt werden, kleiner machen.
  Wenn Reachy von selbst startet, größer machen.

## Geplant (Phase 2)

- Klatschen erkennen (Mikrofon): Reachy „klatscht“ mit den Antennen zurück
- Kamera: Reachy schaut das Kind an, Kuckuck-Spiel
