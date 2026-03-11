# Quart Backend – HTTP Interface Specification

## Rolle
Dieses Backend stellt ein HTTP-Interface für eine zentrale Domänenklasse (`Plexdata`) bereit.
Es enthält keine eigene Business-Logik.

## Architekturprinzipien
- Thin Controller
- Keine State-Mutation außerhalb von Plexdata
- Async-only
- Single-Process

## Globale Invarianten
1. Alle fachlichen Entscheidungen liegen in `Plexdata`
2. Backend-Routen delegieren ohne Interpretation
3. Fehler führen zu:
   - HTTP 500 oder
   - Fallback-Response
4. Kein Authentifizierungs- oder Session-Handling

## Frontend-Integration
- Vue/Vuetify SPA
- Statische Assets aus `dist/`
- Template: `index.html`
- Backend liefert initialen State via Template-Rendering

## Fehlerstrategie
- Unbekannte Fehler → 500
- Keine detaillierten Fehlermeldungen
- Fehler werden nicht geloggt außer via `print`

## Routen
### GET /streamall.xspf
Liefert eine XSPF-Playlist aller Filme.

Delegation:
- plexdata.streamsectionall()

Response:
- Datei (text/xspf+xml)

### GET /streamsection.xspf
Liefert XSPF für aktuelle Section.

Delegation:
- plexdata.streamsection()

### GET /streamurl.xspf
Liefert XSPF für aktuell selektierten Film.

Delegation:
- plexdata.streamurl()

### GET /selection
Liefert aktuellen Auswahlzustand.

Delegation:
- plexdata.get_selection()

Fehler:
- Exception → HTTP 500

### POST /update_section
Body:
- { section }

Delegation:
- plexdata._update_section(section)

Response:
- Redirect /

### GET /force_update_section
Delegation:
- plexdata._update_section(current_section, force=True)

### POST /movie_info
Delegation:
- plexdata._movie_info(req)

Fehler:
- Exception → { error: "error" }

### GET /movie_cut_info
Delegation:
- plexdata._movie_cut_info()

### POST /timeline
Delegation:
- plexdata._timeline(req)

### POST /frame
Delegation:
- plexdata._frame(req)

Fallback:
- error.png

### POST /cut2
Delegation:
- plexdata._cut2(req)

### GET /progress
Delegation:
- plexdata._doProgress()

### GET /restart
Sendet SIGTERM an den eigenen Prozess.

### GET /wakeonlan
Sendet Magic Packet an Fileserver.

### GET /wolserver
Delegation:
- plexdata.wolserver()

## Kritische Invarianten

1. Plexdata ist singleton
2. Backend ist zustandslos außer plexdata
3. Requests dürfen Reihenfolgeabhängigkeit haben
4. Backend ist nicht horizontal skalierbar
5. Async Context darf nicht verlassen werden
6. Frontend erwartet Redirects statt JSON-Status
