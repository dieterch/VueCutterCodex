# Plexdata – Domain Orchestrator Specification

## Rolle
Plexdata ist der zentrale Orchestrator zwischen:
- Plex Server
- Cutter (Dateisystem + ffmpeg)
- Redis/RQ Job Queue
- HTTP Adapter (Quart)

Er enthält den gesamten fachlichen Zustand der Anwendung.

## Lebensdauer
- Eine Instanz pro Backend-Prozess
- Initialisierung beim App-Start
- Kein Restart während Laufzeit vorgesehen

## Abhängigkeiten

- Plex Server (HTTP)
- Redis (RQ Queue)
- Fileserver (Cutter)
- Lokales Filesystem (dist/static)

## Persistenter Zustand

_selection enthält den aktuell ausgewählten Kontext:

- section_type: movie | show
- section: Plex Section Objekt
- series: Liste von Serien (optional)
- serie: aktuelle Serie
- seasons: Liste von Seasons
- season: aktuelle Season
- movies: Liste von Movies/Episodes
- movie: aktuelles Movie
- pos_time: aktuelle Zeitposition
- eta: geschätzte Dauer (optional)

## Initialisierung

Beim Start:
1. config.toml wird geladen
2. Host-Verfügbarkeit wird geprüft
3. PlexInterface und CutterInterface werden erzeugt
4. Initiale Auswahl wird gesetzt:
   - erste Section
   - erstes Movie
5. Redis Queue wird verbunden


---

# 4. Zustandsänderungen (kanonische Regeln)

## 4.1 Update-Kaskade (extrem wichtig)

```md
## Update-Kaskade

_update_section →
  setzt section →
    setzt serie/season/movie (Default)

_update_serie →
  setzt serie →
    setzt season →
      setzt movies →
        setzt movie

_update_season →
  setzt season →
    setzt movies →
      setzt movie

_update_movie →
  setzt movie

## Streaming

- streamsectionall: alle Filme der Section
- streamsection: aktuelle Movies
- streamurl: aktueller Movie

Eigenschaften:
- XSPF via Jinja2
- BytesIO
- Escape von &

## Timeline

Input:
- basename
- pos, l, r, step
- size

Verhalten:
- Timeline wird synchron erzeugt
- Dateien werden unter dist/static abgelegt

## Frame

- erzeugt einzelnes Frame
- Fehler → error.png
- Host-Ausfall → Re-Init

## Cutting

_cut2:
1. Update section + movie
2. Erzeuge MovieData
3. Enqueue Cutter.cut Job
4. Liefere Metadaten zurück

Queue:
- Name: VueCutter
- Timeout: 600s


---

# 8. Progress-Reporting

```md
## Progress

- liest Worker-Status
- liest Queue-Zustand
- aggregiert Job-Fortschritt
- liefert UI-freundliches Statusobjekt

## Implizite Annahmen

1. Nur ein Benutzer
2. Nur eine aktive Selektion
3. Keine parallelen Schnittjobs pro Movie
4. Keine konkurrierenden HTTP-Requests
5. Kein horizontaler Scale
6. Kein Persistenzlayer für State
