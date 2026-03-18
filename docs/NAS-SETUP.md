# Setting up Pointify on a NAS

This guide matches the **production Docker** setup you use locally: same stack (Docker Compose, nginx, FastAPI, React), with persistent data and optional reverse proxy.

## What you need on the NAS

- **Docker** and **Docker Compose** (Synology, QNAP, TrueNAS Scale, etc. usually provide these).
- A place to put the project and persistent data (e.g. `/volume1/docker/pointify` on Synology).
- **Ollama** reachable by the API container (on the NAS or another machine on your LAN).

## 1. Get the app onto the NAS

Clone or copy the repo to a folder on the NAS, e.g.:

```bash
cd /volume1/docker   # or your preferred path
git clone <your-pointify-repo-url> pointify
cd pointify
```

Or copy the project (including `backend/`, `frontend/`, `docker-compose.yml`, both Dockerfiles, `nginx.conf`, `run-prod.sh`) from your Mac.

## 2. Create the root `.env` file

From the **project root** on the NAS (same directory as `docker-compose.yml`):

```bash
cp backend/.env.example .env
```

Edit `.env` and set at least:

| Variable | Example / notes |
|----------|------------------|
| `DATA_PATH` | **Absolute path** on the NAS for DB and audio, e.g. `/volume1/docker/pointify` (no trailing slash). The compose file will put DB and audio under `$DATA_PATH/data`. |
| `WHISPER_CACHE_PATH` | **Absolute path** for Whisper model cache (large; survives rebuilds), e.g. `/volume1/docker/pointify/whisper_cache`. |
| `OLLAMA_URL` | If Ollama runs on the NAS host: `http://host.docker.internal:11434` (Docker Desktop) or `http://<NAS-LAN-IP>:11434`. If on another PC: `http://<that-PC-IP>:11434`. |
| `OLLAMA_MODEL` | Same as locally, e.g. `gpt-oss:20b`. |
| `JWT_SECRET` | Same as local: use a long random string (e.g. `openssl rand -hex 32`). |
| `CORS_ORIGINS` | The URL(s) you use to open the app in the browser, e.g. `https://pointify.myhome.local` or `http://192.168.1.10:8080` (comma-separated if multiple). |

You can leave `DB_PATH` unset; the app defaults to `data/pointify.db`, which lives inside the mounted `DATA_PATH/data` volume.

Create the directories so the containers can use them:

```bash
mkdir -p "$(grep DATA_PATH .env | cut -d= -f2)/data"
mkdir -p "$(grep WHISPER_CACHE_PATH .env | cut -d= -f2)"
```

(Or create them manually from the paths you put in `.env`.)

## 3. Run with Docker Compose

From the project root:

```bash
chmod +x run-prod.sh
./run-prod.sh
```

Or manually:

```bash
docker-compose build
docker-compose up -d
```

This starts:

- **pointify-api** — FastAPI backend (port 8000 inside the network only).
- **pointify-frontend** — nginx serving the React app and proxying `/api/` to the API (port 80 inside the network).

## 4. Expose the app (choose one)

The compose file does **not** publish ports by default; it assumes a reverse proxy in front.

### Option A: Reverse proxy (recommended)

Use Nginx Proxy Manager, Traefik, or the NAS’s built-in reverse proxy. Point your subdomain (e.g. `pointify.myhome.local`) at the **pointify-frontend** container, port **80**.

- If the proxy runs in Docker on the same host, put it on the same network as Pointify (`pointify_internal`) or use the container name `pointify-frontend` as upstream host.
- If the proxy runs on the NAS host (not in Docker), publish the frontend port (see Option B) and point the proxy at `localhost:8080` (or whatever port you choose).

### Option B: Publish the frontend port

To open the app directly as `http://<NAS-IP>:8080` without a reverse proxy, add a port mapping for the frontend. Edit `docker-compose.yml`:

```yaml
  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    container_name: pointify-frontend
    restart: unless-stopped
    ports:
      - "8080:80"   # host:container — use a free port on the NAS
    depends_on:
      - api
    # ... rest unchanged
```

Then:

```bash
docker-compose up -d
```

Use `http://<NAS-IP>:8080` in the browser and set `CORS_ORIGINS=http://<NAS-IP>:8080` (and/or your reverse-proxy URL) in `.env`.

## 5. Ollama on or next to the NAS

- **Ollama on the NAS:** Install Ollama (package or Docker) and expose port 11434. Use `OLLAMA_URL=http://host.docker.internal:11434` or `http://<NAS-IP>:11434` so the API container can reach it. Pull the model there: `ollama pull <OLLAMA_MODEL>`.
- **Ollama on another machine:** Run `ollama serve` on that machine and set `OLLAMA_URL=http://<that-machine-IP>:11434` in `.env`. Ensure the NAS can reach that IP (firewall/LAN).

## 6. Same as local

- **Data:** SQLite DB and audio files live under `$DATA_PATH/data` (same layout as local `backend/data/`).
- **First login:** Default credentials are `admin` / `admin` — change them on first login.
- **Logs:** `docker-compose logs -f`
- **Stop:** `docker-compose down`
- **Rebuild after git pull:** `docker-compose build && docker-compose up -d`

## Summary

| Local (your Mac) | NAS (Docker) |
|------------------|--------------|
| `./start.sh` (venv + npm dev) | `./run-prod.sh` (Docker Compose) |
| Backend :8000, frontend :5173 | Frontend :80 (and optionally :8080 on host), API only on internal network |
| `backend/.env`, `DB_PATH=data/pointify.db` | Root `.env`, `DATA_PATH` + `WHISPER_CACHE_PATH`, `DB_PATH` default |
| Ollama on localhost | Ollama on NAS or another host; set `OLLAMA_URL` accordingly |
| Open http://localhost:5173 | Open via reverse proxy or http://&lt;NAS-IP&gt;:8080 |

Once `.env` is set with NAS paths and Ollama URL, running `./run-prod.sh` gives you the same app as production Docker locally, with data and Whisper cache persisted on the NAS.
