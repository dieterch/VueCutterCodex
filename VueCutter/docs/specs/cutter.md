# CutterInterface – Video Cutting Execution Specification

## Rolle
CutterInterface ist verantwortlich für:
- Mounten von Netzlaufwerken (SMB)
- Erzeugen von Frames und Timelines
- Schneiden von Videos
- Fortschrittsberechnung
- Aufräumen temporärer Dateien

Es kapselt externe Binaries und Dateisystemzugriffe.

## Lebensdauer

- Eine Instanz pro Backend-Prozess
- Wird durch Plexdata erzeugt
- Kein paralleler Einsatz vorgesehen

## Interner Zustand

- last_movie: Titel des zuletzt bearbeiteten Films
- target: aktuelles Timeline-Zielverzeichnis

Dieser Zustand beeinflusst:
- Dateilöschung
- Timeline-Generierung

## Abhängigkeiten

- SMB Server
- /etc/smbcredentials
- ffmpeg (Systembinary)
- mcut Binary
- reconstruct_apsc Binary
- Lokales Mount-Verzeichnis: dplexapi/mnt/

## Mounting

mount(movie):
- ermittelt SMB Share aus movie.locations
- mountet auf lokales mnt-Verzeichnis
- remountet, wenn Zielpfad nicht existiert

umount():
- lazy umount (-l)


---

## 2.4 Pfad- und Namenskonventionen

```md
## Dateinamen

Original:
- <filename>.ts

Cut:
- <filename> cut.ts

Temp (inplace):
- <filename>_.ts

Assistenzdateien:
- .ap
- .sc

## Timeline

timeline(movie, target, size, timelist):
- löscht alte Frames bei Movie-Wechsel
- filtert existierende Frames
- erzeugt Frames parallel (ThreadPool)
- speichert Frames unter target

## Frame

frame():
- synchron
- ffmpeg Screenshot mit Overlay-Text

aframe():
- async Wrapper
- erzeugt genau ein Frame


---

## 2.6 Schneiden (Hauptfunktion)

```md
## Schneiden – Ablauf

cut(movie, cutlist, inplace, useffmpeg):

1. Mount Movie
2. Entferne alte Cut-Dateien (falls vorhanden)
3. Falls useffmpeg:
   - ffmpegsplit
   - ffmpegjoin
4. Sonst (mcut):
   - ggf. reconstruct_apsc
   - mcut
5. Cleanup bei inplace
6. Entferne Timeline-Dateien
7. Liefere Ergebnis-Metadaten

## Progress

_movie_stats:
- berechnet Fortschritt über Dateigrößen
- berücksichtigt:
  - inplace
  - useffmpeg
  - part*.ts

_apsc_stats:
- Fortschritt der .ap-Datei
- bei ffmpeg immer 100%


---

## 2.8 Fehlerstrategie

```md
## Fehler

- subprocess.CalledProcessError wird weitergereicht
- FileNotFoundError teilweise abgefangen
- Kein Retry
- Kein Rollback

## Implizite Annahmen

1. Genau ein aktiver Schnittjob pro Prozess
2. Kein paralleles Schneiden mehrerer Movies
3. Dateisystem ist konsistent
4. SMB Mount ist stabil
5. ffmpeg/mcut liefern korrekte Exit-Codes
6. Movie.locations enthält genau einen Pfad

## Integration

- CutterInterface wird ausschließlich über Plexdata benutzt
- Plexdata ist Owner des Lifecycles
- CutterInterface speichert keinen eigenen Domänenzustand
