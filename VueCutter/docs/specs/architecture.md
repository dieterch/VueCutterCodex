# VueCutter – Gesamtarchitektur

## Zweck dieses Dokuments
Dieses Dokument ist die **kanonische Beschreibung** der gesamten Anwendung.
Es dient als:
- gemeinsame Referenz für Mensch und KI
- Schutz vor unbeabsichtigten Refactorings
- Grundlage für Bugfixes, Migrationen und Erweiterungen

Alles, was hier steht, gilt als **bindend**.

---

## 1. Systemüberblick

VueCutter ist eine **Single-User‑Anwendung** zur Analyse und zum Schneiden von Plex‑Videos.

Sie besteht aus vier klar getrennten Schichten:

```
[ Vue Frontend ]
      |
      |  HTTP (JSON / Files)
      v
[ Quart HTTP Adapter ]
      |
[ Plexdata – zentraler Orchestrator ]
   |                         |
   v                         v
[PlexInterface]        [CutterInterface]
   |                         |
[Plex Server]        [SMB / ffmpeg / mcut]
```

---

## 2. Zentrale Designentscheidungen

### 2.1 Kein verteiltes System
- genau **ein Backend‑Prozess**
- genau **ein aktiver Benutzer**
- kein horizontaler Scale

### 2.2 Zustand ist bewusst zentralisiert
- Backend‑State lebt in `Plexdata`
- Frontend‑State lebt in globalen Vue‑Refs
- kein Event‑Sourcing, keine History

### 2.3 Orchestrierung statt Business‑Logik
- Quart: HTTP‑Adapter
- Plexdata: Zustands‑ und Ablaufsteuerung
- PlexInterface / CutterInterface: reine Adapter

---

## 3. Frontend (Vue + Vuetify)

### Rolle
UI‑Orchestrator zur direkten Steuerung des Backends.

### Architekturprinzipien
- **kein Store (kein Pinia/Vuex)**
- global exportierte `ref`s
- direkte Axios‑Calls
- Computed Getter **dürfen Side‑Effects haben**

### Kritische Invarianten
- `pos`‑Getter triggert `get_frame()`
- Movie‑Wechsel setzt Position immer auf 0
- Timeline ist optional und blockierend
- UI‑Konsistenz > Reaktivitäts‑Purismus

### Persistenz
- nur Cookies (Theme)
- kein LocalStorage für App‑State

---

## 4. Quart Backend (HTTP Adapter)

### Rolle
Dünner HTTP‑Adapter zwischen Frontend und `Plexdata`.

### Eigenschaften
- async‑only
- keine Business‑Logik
- keine Authentifizierung
- Redirects statt Status‑APIs

### Invarianten
- jede Route delegiert 1:1 an `Plexdata`
- Fehler → 500 oder Fallback‑Response
- kein eigener Persistenz‑State

---

## 5. Plexdata (zentraler Orchestrator)

### Rolle
Zentraler **Singleton‑State** und Ablaufcontroller.

### Verantwortlichkeiten
- hält aktuelle Auswahl (`_selection`)
- koordiniert PlexInterface & CutterInterface
- verwaltet Redis/RQ Queue

### Persistenter Zustand (`_selection`)
- section / serie / season / movie
- movies / series / seasons
- pos_time
- eta (optional)

### Update‑Kaskade (bindend)
```
_update_section → serie → season → movies → movie
_update_serie   → season → movies → movie
_update_season  → movies → movie
_update_movie   → movie
```

### Invarianten
- `_selection` ist immer konsistent
- höhere Updates invalidieren niedrigere Ebenen
- kein paralleler State

---

## 6. PlexInterface (Plex‑Domänenadapter)

### Rolle
Adapter um `python‑plexapi` mit Normalisierung und Workarounds.

### Eigenschaften
- read‑only
- optionales Caching
- keine Kenntnis von HTTP oder Queue

### Invarianten
- duration_ms ist Quelle der Wahrheit
- Cache wird nicht automatisch invalidiert
- Titles gelten als stabil

---

## 7. CutterInterface (Execution Layer)

### Rolle
Dateisystem‑naher Ausführungscontroller für Video‑Schnitt.

### Verantwortlichkeiten
- SMB‑Mount / Umount
- ffmpeg / mcut Aufrufe
- Timeline‑Frames
- Progress‑Berechnung

### Kritische Invarianten
- **nicht thread‑safe**
- genau ein aktiver Schnittjob
- genau ein gemountetes Share
- Movie.locations enthält genau **eine Datei**

### Nebenwirkungen
- erzeugt und löscht Dateien
- mountet Netzlaufwerke
- blockierende System‑Calls

---

## 8. Queue & Asynchronität

### Mechanismus
- Redis + RQ
- Queue‑Name: `VueCutter`
- Jobs laufen **außerhalb** des HTTP‑Requests

### Invarianten
- Backend wartet nie auf Job‑Abschluss
- Progress wird gepollt
- maximal ein relevanter Worker

---

## 9. Fehler‑ & Fallback‑Strategie

- Plex nicht erreichbar → Re‑Init oder leere Antworten
- IO‑Fehler → Weiterreichen oder Fallback
- keine Retries
- kein Rollback

**Prinzip:**
> *Lieber inkonsistent anzeigen als blockieren.*

---

## 10. Explizite Nicht‑Ziele

- kein Multi‑User
- keine Rechteverwaltung
- keine Transaktionen
- keine Historie
- kein Event‑System

---

## 11. Regeln für KI‑Agenten (verbindlich)

Agenten dürfen **nicht**:
- State‑Management einführen
- Computed‑Side‑Effects entfernen
- Update‑Kaskaden ändern
- Mount‑Strategie verändern
- Parallelisierung einführen

Agenten dürfen:
- Bugs fixen **im bestehenden Ablauf**
- Logging ergänzen
- Fehlerfälle robuster machen

---

## 12. Zusammenfassung

VueCutter ist ein **bewusst einfaches, zustandsreiches, sequenzielles System**.

Seine Stärke ist:
- Klarheit
- Kontrolle
- Vorhersagbarkeit

Diese Architektur ist kein Zufall, sondern Ergebnis der Anforderungen.

Alles Weitere baut **darauf** auf.

