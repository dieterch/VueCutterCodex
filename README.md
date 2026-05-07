# VueCutter Docker Setup

This repository currently runs VueCutter as a Docker stack with:

- frontend on host port `8200`
- backend API on host port `5200`
- Redis + worker in the same Compose stack

## Default Installation Model

The default and recommended installation model is again the simple one:

- install Docker
- provide SMB credentials on the host under `/etc/smbcredentials`
- start the Docker stack

The backend and worker mount the needed NAS share themselves based on the currently selected movie or episode. You do **not** need to pre-mount every Plex share on the host.

Host-mounted media remains possible as an advanced optional mode, but it is no longer the default setup.

## 1. Install Docker

Make sure Docker and Docker Compose work on the host.

Quick check:

```bash
docker run hello-world
docker compose version
```

## 2. Install CIFS support on the host

The containers use the host kernel for CIFS mounts, so install `cifs-utils` on the host:

```bash
sudo apt update
sudo apt install -y cifs-utils
```

## 3. Create SMB credentials

Create the credentials path used by the app:

```bash
sudo mkdir -p /etc/smbcredentials
sudo nano /etc/smbcredentials/vuecutter
```

Content:

```ini
username=YOUR_SMB_USER
password=YOUR_SMB_PASSWORD
domain=WORKGROUP
```

Then secure it:

```bash
sudo chmod 600 /etc/smbcredentials/vuecutter
```

If your NAS does not require a domain, omit the `domain=` line.

Important:

- the Docker stack mounts the host file `/etc/smbcredentials/vuecutter` into the container as `/etc/smbcredentials`
- the current backend code mounts shares with `credentials=/etc/smbcredentials`
- if you want to keep the current code unchanged, the host credentials file should therefore exist exactly at `/etc/smbcredentials/vuecutter`

## 4. Prepare `.env`

Create the local env file:

```bash
cp .env.example .env
cp VueCutter/servers.example.json VueCutter/servers.json
```

Edit `.env` and set at least:

```bash
VUECUTTER_FRONTEND_PORT=8200
VUECUTTER_BACKEND_PORT=5200
VUECUTTER_REDIS_PORT=6379

REDIS_PASSWORD=change-me
HOST_CONFIG_PATH=./VueCutter/config.toml
HOST_SERVERS_PATH=./VueCutter/servers.json
```

`HOST_SERVERS_PATH` should point to your local, untracked server inventory file. The repo now ships [`VueCutter/servers.example.json`](/home/developer/projects/VueCutterCodex/VueCutter/servers.example.json) as a template, and `VueCutter/servers.json` is ignored by Git.

Edit `VueCutter/servers.json` and configure your Plex servers there:

```json
[
  {
    "id": "plex1",
    "name": "Main Plex",
    "url": "http://192.168.15.10:32400",
    "token": "replace-me",
    "fileserver": "192.168.15.10",
    "media_root": ""
  },
  {
    "id": "plex2",
    "name": "Homelab Plex",
    "url": "http://192.168.15.95:32400",
    "token": "replace-me-too",
    "fileserver": "192.168.15.95",
    "media_root": ""
  },
  {
    "id": "plex3",
    "name": "Third Plex",
    "url": "http://192.168.15.191:32400",
    "token": "replace-me-three",
    "fileserver": "replace-with-third-smb-host",
    "media_root": ""
  }
]
```

Notes:

- each Plex server needs its own Plex token
- all SMB-backed servers can reuse the same SMB credentials file under `/etc/smbcredentials`
- the third server at `192.168.15.191:32400` can therefore use the same credentials, but it still needs its own `fileserver` value for the SMB host
- all servers are expected to expose the same share structure, even if the SMB host differs

For the default SMB-in-container mode, leave `media_root` empty:

```json
"media_root": ""
```

That keeps `CutterInterface.mount()` active for that server.

## 5. Start the stack

```bash
cd /home/developer/projects/VueCutterCodex
docker compose -f docker-compose.yml down
docker compose -f docker-compose.yml up --build
```

The backend and worker run in privileged containers so they can perform CIFS mounts inside the container.

## 6. Verify the services

Frontend:

```bash
curl -i http://127.0.0.1:8200/
```

Backend API:

```bash
curl -i http://127.0.0.1:5200/
curl -i http://127.0.0.1:5200/api/selection
```

Expected:

- `8200` serves the Nuxt frontend
- `5200/` returns backend JSON status
- `5200/api/selection` returns Plex selection JSON
- if multiple servers are configured, the frontend shows a server picker and keeps sleeping servers visible but disabled

## 7. How SMB mounting works now

Plex provides file paths like:

```text
/share/plexrecords/Emma (2020)/Emma (2020).ts
```

At runtime, the backend extracts the share name from the Plex path:

```text
plexrecords
```

Then it mounts the corresponding NAS share:

```text
//<fileserver>/plexrecords
```

to the internal mount point:

```text
/app/dplexapi/mnt/
```

This is done on demand by the backend when you request:

- frame preview
- timeline
- cut info
- cutting

So installation does not require one mountpoint per share on the host.

## 8. Behavior when the NAS is offline

Current intended behavior:

- the frontend still loads
- Plex selection and movie metadata still load
- frame/timeline/cut operations fail fast
- the frontend shows a media unavailable warning

If the NAS is offline, frame requests should now return a clear error instead of hanging forever.

Example:

```bash
curl -i -X POST http://127.0.0.1:8200/api/frame \
  -H 'Content-Type: application/json' \
  -d '{"movie_name":"Emma","pos_time":"00:00:00"}'
```

Expected:

- with NAS available and mountable: `200 OK`
- with NAS unavailable: `503 Service Unavailable`

## 9. Optional advanced mode: host-mounted media

If you explicitly want host-managed mounts instead of container-managed SMB mounting, you can still do that later.

In that case:

- mount the NAS shares on the host yourself
- set `media_root` in the matching `servers.json` entry to the mounted path, for example `/media` or `/mnt/media`
- bind the host media root into the containers again

This mode is more infrastructure-heavy and is not the recommended default for your environment.

## 10. Troubleshooting

### Backend root works but preview fails

Check:

```bash
curl -i http://127.0.0.1:5200/api/selection
curl -i http://127.0.0.1:5200/api/movie
curl -i -X POST http://127.0.0.1:8200/api/frame \
  -H 'Content-Type: application/json' \
  -d '{"movie_name":"Emma","pos_time":"00:00:00"}'
```

If selection/movie work but frame returns `503`, then:

- Plex is reachable
- NAS media is not reachable or mountable

### SMB credentials are wrong or missing

The mount inside the backend container will fail.

Check backend logs:

```bash
docker compose -f docker-compose.yml logs --tail=150 backend
```

### Frontend works on `8200`, backend on `5200`

That is expected:

- `8200` is the UI
- `5200` is the API

Opening `5200/api/...` in the browser is fine for diagnostics, but normal use should go through `8200`.
