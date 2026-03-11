# PlexInterface – Plex Domain Adapter Specification

## Rolle
PlexInterface kapselt den Zugriff auf einen Plex Media Server
und stellt normalisierte Daten für höhere Schichten bereit.

Er enthält keine Anwendungslogik, aber domänenspezifisches Wissen.

## Abhängigkeiten

- Plex Media Server
- python-plexapi
- HTTP Zugriff

## Erweiterungen

- Eigene Client-Implementierung (MyPlexClient)
- Eigene Server-Implementierung (MyPlexServer)

## MyPlexClient

Erweiterung von PlexClient mit:
- robusterer XML-Verarbeitung
- Workarounds für ungültige Antworten
- stabilerem Timeline-Polling

1. HTTP Status ≠ 200/201/204 → Exception
2. XML Parse Errors werden teilweise toleriert
3. seekTo arbeitet immer in Millisekunden


## MyPlexServer

Erweiterung von PlexServer mit:
- zuverlässiger Client-Erkennung
- Fallback über plex.tv bei fehlenden Ports

## Lebensdauer

- Eine Instanz pro Backend-Prozess
- Erzeugt beim Start von Plexdata

## Interner Zustand

- _sectioncache: Cache für Section-Inhalte
- _key / _reverse: Sortierparameter


---

## 5.2 Öffentliche API

```md
## Properties

- sections: Liste aller Library Sections
- clients: Liste aktiver Clients
- server: PlexServer Instanz

## Methoden

- content(section, cache=False)
- sorted_content(section)
- movie_rec(movie)

## MovieData

Reduziertes, serialisierbares Movie-Objekt:
- title
- locations
- duration
- summary


---

# 6. Daten-Normalisierung (`movie_rec`)

```md
## movie_rec(movie)

Liefert normalisierte Metadaten:

- title
- locations
- summary
- addedAt
- duration_ms
- duration (Minuten)
- Restsekunden
- year
- guid
- streamURL


---

# 7. Caching & Sorting

```md
## Caching

- Sections werden bei Bedarf geladen
- Cache invalidiert sich nicht selbst
- cache=True erzwingt Wiederverwendung

## Sorting

- Sortierung erfolgt dynamisch
- basiert auf Attributnamen


---

# 8. Spezialfunktion: Double Movies

```md
## Double Movies Detection

Ziel:
- Finden identischer Filme in mehreren Movie-Sections

Vorgehen:
1. Lade alle Movie-Sections
2. Filtere "keep"-Liste aus keep.json
3. Vergleiche Titel case-insensitive
4. Liefere Kombinationen


---

# 8. Spezialfunktion: Double Movies

```md
## Double Movies Detection

Ziel:
- Finden identischer Filme in mehreren Movie-Sections

Vorgehen:
1. Lade alle Movie-Sections
2. Filtere "keep"-Liste aus keep.json
3. Vergleiche Titel case-insensitive
4. Liefere Kombinationen

## Implizite Annahmen

1. Plex API liefert konsistente Daten
2. Titles sind stabil
3. Movie.locations enthält gültige Pfade
4. Cache-Konsistenz ist unwichtig
5. Ein Plex Server pro Instanz

## Integration

- PlexInterface wird ausschließlich von Plexdata verwendet
- CutterInterface erhält nur MovieData
- PlexInterface kennt keine Queue, kein HTTP


---

# 11. Gesamtbild (jetzt explizit)

Du hast faktisch dieses System gebaut:

[ Quart HTTP ]
|
v
[ Plexdata ] ←—— globaler Zustand
|
v v
[PlexInterface] [CutterInterface]
| |
[ Plex Server ] [ SMB / ffmpeg ]
