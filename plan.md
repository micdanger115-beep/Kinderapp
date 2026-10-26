# Plan: „Tanz-Reachy" – Kinderlieder-App für Reachy Mini

Stand: 26.10.2026 · Status: **freigegeben am 26.10.2026, Phase 1 umgesetzt**

## 1. Was ich verstanden habe

Reachy Mini soll für ein 1,5-jähriges Kind Kinderlieder abspielen und sich rhythmisch dazu bewegen. Das Kind spricht noch nicht, also gibt es **keine Spracheingabe**. Alles muss über einfache Berührung, Bewegung und Geräusche funktionieren, sanft, ruhig und sicher sein.

## 2. Kindgerechtes Konzept

### Leitidee: „Der Roboter ist ein Spielkamerad, kein Bildschirm"
Das Kind soll nicht auf ein Handy schauen. Es spielt direkt mit dem Roboter. Das Handy/Tablet ist nur die **Fernbedienung für die Eltern**.

### Wie das Kind interagiert (ohne Sprache)
| Aktion des Kindes | Reaktion von Reachy |
|---|---|
| **Antenne antippen/drücken** (die Antennen sind dafür gebaut und weich gelagert) | „Oh!" – kurzes Wackeln, dann startet das nächste Lied mit Tanz |
| **Antenne drücken, während ein Lied läuft** | Reachy macht einen fröhlichen Extra-Hüpfer (Ursache → Wirkung, das lieben Kleinkinder) |
| **Nichts tun** nach dem Lied | Reachy „wartet" freundlich: wiegt leicht, Antennen winken langsam, schaut sich um – lädt zum Antippen ein |
| *(Phase 2)* **Klatschen** (Mikrofon erkennt lautes Geräusch) | Reachy klatscht mit den Antennen zurück |
| *(Phase 2)* **Kind ist im Bild** (Kamera) | Reachy schaut das Kind an, „Kuckuck"-Spiel |

Diese Muster folgen dem, was Kinder mit 18 Monaten gut können: Ursache-Wirkung, Wiederholung, Nachahmen, kurze Aufmerksamkeitsspannen.

### Lieder
Gemeinfreie (public domain) deutsche Kinderlieder, **selbst erzeugt** als sanfte Instrumentalversion (Spieluhr/Xylophon-Klang). Vorteil: keine Urheberrechtsprobleme, und weil wir die Musik selbst erzeugen, kennen wir **jeden Taktschlag exakt** – der Tanz ist perfekt synchron.

Vorschlag für die erste Liste (alle traditionell, gemeinfrei):
1. Alle meine Entchen
2. Hänschen klein
3. Kuckuck, Kuckuck, ruft's aus dem Wald
4. Summ, summ, summ
5. Backe, backe Kuchen
6. Häschen in der Grube
7. *(Abschluss / ruhig)* Weißt du, wie viel Sternlein stehen

Jedes Lied bekommt einen eigenen kleinen Tanz, der zum Inhalt passt (Entchen: Kopf „taucht" ins Wasser; Kuckuck: Kopf schaut links/rechts; Summ summ: Antennen flattern wie Bienenflügel; Häschen: Hüpfen mit dem Kopf).

### Sicherheit & Ruhe (fest eingebaut)
- **Langsame Tempi** (ca. 80–100 Schläge/Minute), weiche Bewegungen (min-jerk-Interpolation), keine ruckartigen Starts/Stopps.
- **Kleine Ausschläge**: Kopfneigung max. ca. ±12°, Drehung max. ca. ±20° (Hardware-Limit wäre ±40°/±160°).
- **Lautstärke gedeckelt** (Standard 40 %, maximal 60 %), sanftes Ein- und Ausblenden.
- **Sitzungsdauer begrenzt** (Standard 15 Minuten), danach ein ruhiges Gute-Nacht-Lied und Reachy „schläft ein".
- **Not-Aus für Eltern**: großer Stopp-Knopf in der Eltern-Ansicht; beim Beenden fährt Reachy immer sanft in die Ruheposition.
- Hinweis: Nur unter Aufsicht benutzen, Roboter stabil auf den Boden/Tisch stellen, Kabel außer Reichweite.

### Eltern-Ansicht (Handy)
Einfache Seite mit großen Knöpfen: Start/Stopp, Lied wählen, Lautstärke, Sitzungsdauer, „Kind-Modus" (nur Antennen-Steuerung).

## 3. Technischer Ansatz

**Empfehlung: Python-App, die direkt auf dem Roboter läuft**, mit kleiner Eltern-Webseite (`static/`).

Warum Python statt der von Pollen standardmäßig empfohlenen JS-App: Eine JS-App läuft nur, solange ein Browser-Tab offen ist, und braucht bei jeder Nutzung Internet und ein Hugging-Face-Konto. Für ein Kleinkind-Spielzeug ist es besser, wenn Reachy **ohne Bildschirm, offline und zuverlässig** läuft und das Kind nur über die Antennen steuert. Genau dafür sieht `AGENTS.md` Python vor („must run unattended … without internet").

Bausteine:
- `songs/`: Melodien als Notenlisten (Tonhöhe + Dauer); ein Synthesizer erzeugt daraus WAV-Dateien mit Spieluhr-Klang.
- `dances/`: Tänze als mathematische Funktionen des Taktschlags (Muster aus `skills/symbolic-motion.md`), pro Lied ein Tanz.
- Steuer-Schleife: spielt Audio über `mini.media.play_sound()`, bewegt den Roboter taktgenau mit `set_target()`, prüft Antennen als Knöpfe (`skills/interaction-patterns.md`).
- Zustände: *Warten → Lied + Tanz → Pause/Warten → … → Schlafen*.
- Getestet zuerst in der Simulation, dann am echten Roboter.

## 4. Offene Fragen (bitte direkt hier oder im Chat beantworten)

1. **Welches Modell hast du?** Reachy Mini **Lite** (per USB am Laptop) oder **Wireless** (WLAN, eigener Akku)?
   Antwort: Wireless

2. **App-Art:** Einverstanden mit der **Python-App auf dem Roboter** (offline, Kind steuert per Antenne)? Oder lieber eine **Web-App (JS)**, die man per Link im Handy öffnet?
   Antwort: Python ist okay

3. **Wo soll der Code liegen?** Hast du ein **Hugging-Face-Konto** (Pollen veröffentlicht Apps dort) und/oder möchtest du ein **GitHub-Repository**? Falls GitHub: bitte ein leeres Repo anlegen und mir den Namen sagen.
   Antwort: GitHub, micdanger115-beep/Kinderapp

4. **Lieder:** Passt die Liste oben? Lieber rein instrumental (mein Vorschlag) oder soll Reachy die Melodie mit einer Stimme „singen" (z. B. „la la la")?
   Antwort: Vorschlag übernommen (instrumental). Liste angepasst, siehe unten.

5. **Interaktion:** Ist Antennen-Antippen für euer Kind okay? Sollen Klatschen und Kamera („Kuckuck") gleich mit rein oder erst in Phase 2?
   Antwort: Antennen ja; Klatschen und Kamera erst später (Phase 2)

6. **Grenzen:** Passen 40 % Lautstärke und 15 Minuten Sitzungsdauer als Standard?
   Antwort: Standard übernommen (40 %, 15 Minuten), in der Eltern-Webseite änderbar

## 5. Änderungen bei der Umsetzung

- Liederliste: „Summ, summ, summ“, „Backe, backe Kuchen“, „Häschen in der Grube“ und „Kuckuck“ wurden durch „Bruder Jakob“ und „Blinke, blinke, kleiner Stern“ ersetzt, weil deren Melodien sicher korrekt nachgebaut werden konnten. Schlaflied ist „Guten Abend, gut' Nacht“ (Brahms) statt „Weißt du, wie viel Sternlein stehen“.
- Lautstärke wird in die erzeugte Musik eingerechnet (Anteil der Systemlautstärke des Roboters).
