# Web showcase: FastAPI + React dashboard

`server.py` is a thin HTTP layer over `src/` (no allocation or scoring logic of its own).
`frontend/` is a Vite + React + Tailwind + Recharts + Lucide dashboard.

## Setup

```bash
# 1. Backend (Python 3.10+)
pip install -r requirements-web.txt          # add requirements-web-dev.txt to run the tests
uvicorn server:app --port 8000            # note: "server:app", not "server.py"
#   API docs: http://localhost:8000/docs

# 2a. Frontend, development (hot reload on :5173, /api proxied to :8000)
cd frontend && npm install && npm run dev

# 2b. Frontend, production (FastAPI serves it at http://localhost:8000)
cd frontend && npm install && npm run build   # creates frontend/dist, then (re)start uvicorn
```

Environment variables: `CORS_ORIGINS` (comma-separated, default `localhost:5173,3000`),
`VITE_API_BASE` (API origin if the frontend is hosted separately), `VITE_API_TARGET` (dev proxy target).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/dataset/generate` | seeded dataset via `generate_dataset` (students, halls, courses, seed) |
| POST | `/api/dataset/upload` · `/load` · `/sample` | CSV upload, JSON body, bundled sample |
| GET | `/api/algorithms` | algorithms the backend really has (+ unavailable ones, default weights) |
| POST | `/api/allocate` | run the pipeline: seats, metrics, soft breakdown, per-seat heat |
| POST | `/api/benchmark` | `mode: density` (time vs graph density) or `size` |
| GET | `/api/export/{csv,html,md,svg}` | downloads from `src/reporting/` (`?plot=` for svg) |
| GET · DELETE | `/api/session` | what this session holds · wipe my dataset, allocation and benchmark |
| GET | `/healthz` | liveness probe (never creates a session; used by Docker) |

An allocation Phase 2 cannot complete returns HTTP 200 with `status: "infeasible"`.

## Deliberate differences from the original brief

* **DSatur is not offered**: it does not exist in `src/algorithms` (the API answers 422 and the UI shows it disabled).
* **LDF = Welsh-Powell** (largest-degree-first order); `ldf` is accepted as an alias. **Exact** = bounded backtracking.
* **Sliders use the four real weights** (`w_same_branch`, `w_consecutive_roll`, `w_distance_two_conflict`, `w_wasted_seat`).
  "Buffer distance" maps to `w_distance_two_conflict`; there is no "aisle preference" in the engine.
* **χ(G)** is shown as exact only when proven (search completed, or colors = largest-course lower bound); otherwise "colors used (upper bound)".
* **Heatmap** values are the backend's pair penalties spread over seats; `soft.heat_reconciles` proves they sum to the backend score.
* The browser re-checks adjacency from raw seat data (the "0 conflicts" banner), independently of the server.

## Sessions (multi-user)

Each browser gets an opaque random `exam_session` cookie (HttpOnly, SameSite=Lax; `Secure` when
`COOKIE_SECURE=1`). The cookie only selects a server-side session; the dataset, last allocation and
last benchmark live in that session and are invisible to everyone else. Exports always return *your*
latest result.

| Variable | Default | Meaning |
|---|---|---|
| `SESSION_TTL_SECONDS` | `7200` | idle time before a session (and its data) is deleted |
| `MAX_SESSIONS` | `200` | hard cap; the least recently used session is evicted beyond it |
| `MAX_CONCURRENT_JOBS` | `4` | simultaneous allocations/benchmarks; extra requests wait `JOB_WAIT_SECONDS` (20) then get `503` + `Retry-After` |
| `COOKIE_SECURE` | `0` | set to `1` when served over HTTPS |
| `CORS_ORIGINS` | localhost dev ports | only needed if the UI is hosted on a different origin (cookies then require this explicit list) |

**Limits you should know about**
* Sessions live in the memory of **one process**. Run a single worker (the Dockerfile does). With several
  workers or replicas, users would randomly land on a process that has never seen their session. Scale out
  only after adding sticky sessions or a shared store (e.g. Redis).
* A server restart drops all sessions. The UI notices ("No dataset loaded") and returns to its empty state.
* Sessions separate users, they do not authenticate them: anyone holding a valid cookie has that session.
  There is no login, rate limiting per IP, or TLS in this app. Put it behind a reverse proxy for those.

## Docker

```bash
docker build -t exam-seating .
docker run --rm -p 8000:8000 exam-seating          # http://localhost:8000
# or
docker compose up --build
```

Two-stage image: Node builds the dashboard, then a slim Python image runs `uvicorn --workers 1` as an
unprivileged user with a `/healthz` healthcheck. Over HTTPS add `-e COOKIE_SECURE=1`.

## Tests

```bash
python -m unittest discover -s tests -v   # original 16 + tests/test_server.py (35 API) + tests/test_sessions.py (20 session)
python scripts/check_imports.py
```
