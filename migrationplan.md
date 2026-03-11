# Migration Plan: VueCutter to Nuxt 4 + Vuetify with Docker Stack

## Summary

VueCutter should migrate in phases to a Nuxt 4 + Vuetify frontend while keeping the existing Python/Quart + Plexdata + CutterInterface + Redis/RQ backend as the execution core in phase 1.

Target runtime is a Docker Compose stack with separate services for:

- `frontend`: Nuxt 4 app
- `backend`: Quart API
- `worker`: RQ worker for cutting and analysis jobs
- `redis`: queue backend

Media access default:

- use host-mounted volumes
- do not rely on CIFS/SMB mounts from inside containers in phase 1

This keeps the risky filesystem and media-processing behavior stable while modernizing the frontend and deployment model.

## Key Changes

### 1. Target architecture

Adopt this structure:

```text
[ Nuxt 4 + Vuetify ]
        |
        | HTTP/JSON
        v
[ Quart API ]
        |
[ Plexdata ]
   |          |
   v          v
[PlexInterface] [CutterInterface]
                    |
                    v
             [ ffmpeg / mcut ]
        |
        v
[ Redis ] <-> [ RQ Worker ]
```

Container boundaries:

- `frontend` serves the Nuxt UI
- `backend` exposes the application API and owns `Plexdata`
- `worker` runs queued cut and analysis jobs
- `redis` backs job queue and progress lookup

### 2. Docker stack first-class support

Add a `docker-compose.yml` in the repo root with:

- `frontend` depending on `backend`
- `backend` depending on `redis`
- `worker` depending on `redis`
- shared app network
- shared bind mounts for:
  - media library path from host
  - optional output path
  - config/secrets files where needed
- environment variables for:
  - backend base URL for Nuxt
  - Redis host/port/password
  - Plex connection settings
  - media root mapping

Operational defaults:

- backend and worker must see the same media path
- output files must land in a host-visible directory
- no privileged mount operations inside containers by default
- current CIFS mounting code remains only as a compatibility path, not the default deployment model

### 3. Backend contract cleanup before frontend rewrite

Preserve `Plexdata` and cutting logic, but expose a cleaner JSON API for the new frontend.

Public interface changes:

- `GET /api/health`
- `GET /api/selection`
- `POST /api/selection/section`
- `POST /api/selection/series`
- `POST /api/selection/season`
- `POST /api/selection/movie`
- `GET /api/movie`
- `GET /api/movie-cut-info`
- `POST /api/frame`
- `POST /api/timeline`
- `POST /api/cut`
- `GET /api/progress`

Rules:

- JSON responses only for app actions
- redirects removed from the Nuxt-facing API
- keep old routes temporarily during migration
- backend remains source of truth for selection state and job orchestration

### 4. Nuxt 4 frontend migration

Replace the current Vite SPA with Nuxt 4 and Vuetify.

Frontend implementation shape:

- `useSelection()` for section/series/season/movie cascade
- `usePlayback()` for current position, frame fetch, and validation
- `useTimeline()` for thumbnail strip requests and local timeline state
- `useCutting()` for cutlist, submit flow, and progress polling
- `useTheme()` for Vuetify theme persistence
- shared API client wrapper over backend endpoints

Migration slices:

1. Nuxt 4 shell, Vuetify plugin, runtime config, API client
2. selection flow and movie info
3. frame preview and playback position handling
4. timeline scrubbing UI
5. cut dialog and progress polling
6. remove old Vite frontend after parity is confirmed

Frontend rules:

- no computed getters with network side effects
- move side effects into explicit actions/watchers
- debounce frame requests during scrubbing
- cancel stale requests where possible

### 5. Media access and filesystem model

Use host-mounted media volumes as the primary deployment model.

Implementation changes needed:

- configure a host media root in backend config
- map Plex-reported file locations to the mounted host path visible inside backend/worker containers
- ensure cutter path resolution works without container-side CIFS mounting
- keep mount-related code isolated so CIFS support can remain optional for legacy/manual deployments

This is the key containerization change because it removes privileged mount requirements from normal operation.

### 6. Future feature foundations

#### Automatic movie start/end detection

Implement as a queued backend analysis job, not as frontend logic.

Output contract:

- `detected_start`
- `detected_end`
- `confidence_start`
- `confidence_end`
- analysis status and timestamp

Phase 1 heuristics:

- black-frame/fade detection
- silence or low-audio windows
- optional intro/outro heuristic thresholds
- no ML requirement for v1

#### Faster scrubbing

Implement as a media-preview pipeline improvement.

Phase 1 performance work:

- cache preview frames by movie, timestamp, and size
- debounce/cancel rapid frame requests
- prefetch neighboring frames around current position
- generate lightweight timeline strips or sprite sheets for browsing
- keep full frame extraction for precise inspection only

## Test Plan

### Container/runtime tests

- `docker compose up` starts `frontend`, `backend`, `worker`, and `redis`
- backend can connect to Redis
- worker can pick up queued jobs
- backend and worker both resolve the same mounted media paths
- cut output is written to the expected host-visible directory

### Backend/API tests

- selection cascade behaves exactly like current `Plexdata`
- `/api/frame` returns a valid preview path or fallback
- `/api/timeline` returns expected positions/assets
- `/api/cut` enqueues exactly one job
- `/api/progress` reports queue and worker state correctly

### Frontend tests

- selecting a movie resets playback position appropriately
- movie info loads on selection change
- scrubbing does not flood backend with uncancelled stale requests
- timeline thumbnails render correctly
- cutlist creation and validation match current behavior
- progress UI transitions through idle/running/completed states

### End-to-end scenarios

- browse section -> select movie -> inspect frames -> create cut -> submit -> observe completion
- restart stack and confirm selection/bootstrap still works

## Assumptions

- Nuxt 4 is the target version for the new frontend.
- Python/Quart, `Plexdata`, `PlexInterface`, `CutterInterface`, Redis, and RQ remain in place for phase 1.
- Docker Compose is the required local/dev runtime model.
- Docker must be installed on the machine before the stack can be started.
- Standard Docker is preferred over rootless Docker for this app.
- Media access default is host-mounted volumes, not container-managed SMB/CIFS mounts.
