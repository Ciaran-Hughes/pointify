# Pointify

Voice-note app: record audio, get transcriptions (Whisper), and AI-generated bullet summaries (Ollama). Organize notes by pages and days with JWT auth and an optional Docker deployment.

## Features

- **Voice recording** — Record in the browser; uploads stored and transcribed with Whisper
- **Bullet digests** — Ollama turns transcripts into bullet points (configurable model)
- **Pages & days** — Group recordings by page and date; reorder bullets via drag-and-drop
- **Auth** — JWT login, refresh tokens, optional admin panel and user management
- **Production** — Docker Compose (API + React frontend behind nginx), healthchecks, non-root user

## Prerequisites

- **Local dev:** Python 3.13+, Node 22+, [Ollama](https://ollama.com) (for digests)
- **Docker:** Docker and Docker Compose (for production-style run)

## Local development

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Copy `backend/.env.example` to `backend/.env` and set at least:

- `JWT_SECRET` — random string for signing tokens
- `OLLAMA_URL` — e.g. `http://localhost:11434`
- `OLLAMA_MODEL` — e.g. your preferred model name
- `DB_PATH` — e.g. `data/pointify.db`
- `CORS_ORIGINS` — e.g. `http://localhost:5173`

Optional: `ENABLE_DOCS=true` for Swagger at `/docs` (local only).

### Frontend

```bash
cd frontend
npm install
```

### Run everything

From the project root:

```bash
./start.sh
```

- App: http://localhost:5173  
- API: http://localhost:8000  
- Docs: http://localhost:8000/docs (if `ENABLE_DOCS=true`)  
- Default login: `admin` / `admin` — **change on first login**

Ensure Ollama is running (`ollama serve`) and the digest model is pulled (e.g. `ollama pull <OLLAMA_MODEL>`).

## Production (Docker)

1. Copy **`.env.example`** (in project root) to **`.env`** and set values — especially `DATA_PATH`, `WHISPER_CACHE_PATH`, `JWT_SECRET`, `OLLAMA_URL`, and `CORS_ORIGINS`.
2. Run:

```bash
./run-prod.sh
```

Then point your reverse proxy (e.g. Nginx Proxy Manager) at the `pointify-frontend` container on port 80.

- Logs: `docker-compose logs -f`  
- Stop: `docker-compose down`

## Environment variables

| Variable | Description |
|----------|-------------|
| `OLLAMA_URL` | Ollama API base URL |
| `OLLAMA_MODEL` | Default model for bullet digests |
| `JWT_SECRET` | Secret for signing JWT tokens |
| `DB_PATH` | Path to SQLite database file |
| `CORS_ORIGINS` | Allowed origins (comma-separated) |
| `LOG_LEVEL` | Logging level (e.g. INFO) |
| `MAX_UPLOAD_MB` | Max upload size in MB |
| `MAX_RECORDING_MINUTES` | Max recording length in minutes |
| `ENABLE_DOCS` | Set true only for local dev (Swagger UI) |

For Docker, also set `DATA_PATH` and `WHISPER_CACHE_PATH` for persistent storage.

## Tests

- **Backend:** `cd backend && pytest`
- **Frontend:** `cd frontend && npm test`
- **Lint / format:** `ruff` and pre-commit in backend; ESLint/Prettier in frontend

## Stack

- **Backend:** FastAPI, SQLAlchemy (SQLite), Whisper (faster-whisper), Ollama (HTTP), JWT + bcrypt
- **Frontend:** React 19, Vite, React Router, @dnd-kit (drag-and-drop)
- **Deploy:** Docker (Python image + nginx for static frontend), docker-compose
