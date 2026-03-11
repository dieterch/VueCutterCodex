# VueCutter Frontend – UI Orchestrator Specification

## Rolle
Das Frontend stellt eine UI zur Steuerung von Plexdata und CutterInterface bereit.
Es hält den gesamten UI- und Interaktionszustand lokal.

## Architektur

- Keine zentrale Store-Library
- Global exportierte Refs
- Direkte HTTP-Kommunikation via Axios
- Keine lokale Persistenz außer Cookies


---

## 2.2 Globale Umgebungsdaten

```md
## Environment

- host = window.location.host
- protocol = window.location.protocol


---

## 2.3 Theme & Cookies

```md
## Theme

- Vuetify Theme
- Persistenz via Cookie "theme"
- Default: LightTheme


---

# 3. Positions- & Playback-Logik (zentral!)

```md
## Position State

- lpos: aktuelle Position (Sekunden)
- pos: computed HH:MM:SS

Nebenwirkung:
- pos.get → triggert get_frame()


---

## 3.1 Positionsfunktionen

```md
pos2str(pos)    -> "HH:MM:SS"
str2pos(str)    -> Sekunden
pos_from_end()  -> Position relativ zum Filmende
posvalid(val)   -> Validierung / Clamp


---

# 4. Timeline-System

```md
## Timeline

toggle_timeline: Aktiv/Inaktiv

ltimeline:
- basename
- larray (Positionsmarker)
- l, r (Offsets)
- step
- size

1. Timeline aktivieren
2. POST /timeline
3. Backend generiert Frames
4. Frontend rekonstruiert Bildpfade

- Backend ist schneller als UI-Refresh
- Frames werden asynchron erzeugt

## Cutting State

- t0 / t1 (Cut-Grenzen)
- cutlist
- inplace
- useffmpeg
- cutterdialog

b.type:
- rel   → relative Bewegung
- abs   → absolute Bewegung
- t0    → Start setzen
- t1    → Ende setzen


---

# 6. Progress & Status

```md
## Progress State

progress_status:
- title
- cut_progress
- apsc_progress
- started
- status


---

# 7. Plex-bezogener UI-State

```md
## Plex State

sections
section
section_type
series
serie
seasons
season
movies
movie

movie.get:
- setzt lpos = 0
- triggert load_movie_info()


---

# 8. Frame-Loading

```md
## Frame Loading

POST /frame
Input:
- pos_time
- movie_name

Output:
- frame URL


---

# 9. Kritische implizite Annahmen (jetzt explizit)

```md
## Implizite Annahmen

1. Ein Benutzer
2. Ein aktiver Film
3. Keine parallelen Aktionen
4. Backend antwortet schnell
5. Getter dürfen Side-Effects haben
6. UI-Consistency wichtiger als Reaktivitäts-Purismus

[ Vue Frontend ]
   |
   |  HTTP
   v
[ Quart Adapter ]
   |
[ Plexdata ]  ← zentraler State
   |        \
   v         v
[PlexInterface]   [CutterInterface]
