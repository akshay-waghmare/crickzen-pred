# Implementation Plan: SaaS Prediction Dashboard

**Branch**: `001-saas-prediction-dashboard` | **Date**: 2026-02-18 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-saas-prediction-dashboard/spec.md`

## Summary

Build a commercially-attractive, JWT-gated SaaS web dashboard that replaces the Streamlit prototype. The dashboard reads from the existing prediction backend's JSON state file and presents live win probabilities, scorecard, and a ball-by-ball probability timeline chart in a polished dark-themed UI. Auth is minimal: email + password, PyJWT HS256, opaque refresh tokens in SQLite, ~100 lines of hand-written code. Deployed as a 2-service Docker Compose stack (FastAPI + Caddy) on a Linux VPS.

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: FastAPI 0.115, uvicorn, PyJWT 2.11, pwdlib[argon2] 0.3, SQLModel 0.0.34, slowapi 0.1.9, Jinja2 3.1; Alpine.js 3.14 + Chart.js 4.4.7 (vendored JS); Tailwind CSS 4 CLI (build-time)  
**Storage**: SQLite (WAL mode) — `users` + `refresh_tokens` tables. No external DB service.  
**Testing**: pytest + httpx (FastAPI TestClient)  
**Target Platform**: Linux VPS, Docker Compose (2 services: `api` + `caddy:2.9-alpine`)  
**Project Type**: Web application — separate `dashboard/` top-level package  
**Performance Goals**: ≤200ms p95 on `GET /api/live-state`; ≤5s first-paint on dashboard page  
**Constraints**: 50 concurrent users max, 3s poll interval, HTTPS enforced, JWT bearer on all API routes  
**Scale/Scope**: 1 live match at a time, ≤50 subscribers, 1 VPS, 1 domain

## Constitution Check

*GATE: Must pass before proceeding. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| **I. Tournament-agnostic** | ✅ PASS | Dashboard reads `league` from JSON state; no league-specific logic in dashboard code |
| **II. Pipeline-driven / rapid retraining** | ✅ N/A | Dashboard is read-only consumer; no training pipeline changes |
| **III. Reproducibility & Versioning** | ✅ PASS | Docker image is the versioned artefact; `requirements.txt` pins all deps |
| **IV. Data integrity & entity consistency** | ✅ PASS | Dashboard never writes match data; auth DB completely separate from match data |
| **V. Calibration & Observability (ECE < 0.0021)** | ✅ N/A | Probabilities displayed as-received from backend; dashboard does not compute or modify them |
| **Code quality** | ✅ PLANNED | All Python typed; pytest unit tests for auth + live endpoints |

**No violations detected. No Complexity Tracking entries required.**

## Project Structure

### Documentation (this feature)

```text
specs/001-saas-prediction-dashboard/
├── plan.md              ← This file
├── spec.md              ← Feature specification
├── research.md          ← Phase 0: library decisions + rationale
├── data-model.md        ← Phase 1: entity schemas + access control
├── quickstart.md        ← Phase 1: dev + prod setup guide
├── contracts/
│   └── api.yaml         ← Phase 1: OpenAPI 3.1 contract (5 endpoints)
└── checklists/
    └── requirements.md  ← Spec quality checklist
```

### Source Code (repository root)

```text
dashboard/
  app/
    main.py              ← FastAPI app factory: mounts routers, StaticFiles, Jinja2
    config.py            ← pydantic-settings: JWT_SECRET, DOMAIN, POLL_INTERVAL_MS, etc.
    database.py          ← SQLite engine (WAL), session factory, startup table creation
    models.py            ← SQLModel: User, RefreshToken
    auth.py              ← create_access_token, create_refresh_token, verify_token,
                           rotate_refresh_token, hash/verify password, purge_expired_tokens
    health.py            ← GET /health (Docker healthcheck + Caddy probe)
    routers/
      auth.py            ← POST /auth/login, /auth/refresh, /auth/logout, POST /auth/users
      live.py            ← GET /api/live-state (JWT-gated, ETag, stale detection)
      pages.py           ← GET / (dashboard shell), GET /login (login page)
  templates/
    base.html            ← Dark layout, Tailwind, Alpine.js init, Chart.js script
    dashboard.html       ← Score panel, win-prob gauges, RR bar, probability chart
    login.html           ← Email/password form, error display
  static/
    css/
      input.css          ← Tailwind @tailwind directives
      app.css            ← CLI output (generated, gitignored)
    js/
      alpine.min.js      ← Alpine.js 3.14 (vendored, committed)
      chart.umd.min.js   ← Chart.js 4.4.7 (vendored, committed)
      dashboard.js       ← Poll loop, chart update, silent refresh (setTimeout)
  Dockerfile             ← python:3.12-slim, Tailwind CLI build, uvicorn CMD
  requirements.txt
  tailwind.config.js
  package.json           ← devDep: tailwindcss CLI only
  .env.example

docker-compose.yml       ← Production: api + caddy services, named volumes
docker-compose.dev.yml   ← Local dev: api only (port 8000, no TLS)
Caddyfile                ← 8-line: auto-HTTPS, gzip, proxy to api:8000

tests/
  dashboard/
    conftest.py          ← TestClient fixture with in-memory SQLite
    test_auth.py         ← login, refresh rotation, logout, replay detection, rate limit
    test_live.py         ← live-state auth, stale detection, 304 ETag, 404 no-file
    test_models.py       ← User + RefreshToken schema validation
```

**Structure Decision**: Option 2 (web application) — new `dashboard/` top-level package for frontend + API, distinct from `src/bbl_pipeline/` ML package. Keeps deployable artefacts independent and preserves the tournament-agnostic principle.

## Implementation Phases

### Phase A — Auth & API skeleton (P1 prerequisite)

Deliverables: `models.py`, `database.py`, `auth.py`, `config.py`, `health.py`, `routers/auth.py`, `main.py`, `tests/dashboard/test_auth.py`

Key decisions:
- `POST /auth/login` → issues JWT access token (body) + opaque refresh token (HttpOnly cookie); rate-limited 5/min via `slowapi`
- `POST /auth/refresh` → validates refresh token hash from DB, deletes it, issues new pair atomically (rotation)
- `POST /auth/logout` → sets `revoked=True` on refresh token row
- Replay detection: consumed token presented again → revoke ALL tokens for that user
- Startup: seeds admin user from `ADMIN_EMAIL`/`ADMIN_PASSWORD` env vars; creates SQLite tables; runs WAL pragma; purges expired tokens

Acceptance: `pytest tests/dashboard/test_auth.py` green. `GET /health` → `{"status":"ok"}`.

---

### Phase B — Live state endpoint (P1 core)

Deliverables: `routers/live.py`, `tests/dashboard/test_live.py`

Key decisions:
- Reads `STATE_FILE` (env var, default `data/live_state.json`) via `Path.read_text()` — no DB, no Redis
- ETag = `str(file.stat().st_mtime)` — 304 on match
- Stale detection: if `timestamp` in JSON is >60s old, append `"stale": true` to response
- Bind-mounted `:ro` from host → container; prediction backend writes; dashboard reads

Acceptance: 401 without token, 200 with valid token + `live_state.json` present, 304 on re-poll with same ETag, 404 when file missing, `stale:true` when file >60s old.

---

### Phase C — Dashboard UI (P1 + P2)

Deliverables: `templates/base.html`, `templates/dashboard.html`, `templates/login.html`, `static/js/dashboard.js`, `routers/pages.py`, `tailwind.config.js`, `static/css/input.css`

Key decisions:
- Dark cricket theme via Tailwind utility classes (slate-900 background, emerald/red team accents)
- Win-probability gauges: Chart.js doughnut charts (half-donut style), one per team, team colour fill
- Probability timeline: Chart.js line chart; `chart.update('active')` on each poll for smooth animation; vertical annotation lines at phase boundaries (over 6, over 16, innings 2 start); wicket events rendered as red scatter points layered on the line
- Score panel: Alpine.js `x-text` bindings updating score, wickets, overs from JSON
- Run-rate bar: side-by-side CRR vs RRR bar chart (Chart.js bar, green/red colouring)
- Silent refresh: `scheduleRefresh()` sets `setTimeout` for `(TOKEN_EXPIRE_MS - 5*60*1000)` ms; on fire → `POST /auth/refresh` → update `accessToken` in memory → reschedule
- Mobile: Tailwind `sm:` breakpoints collapse gauges to stacked layout at 375px

Acceptance: Login → dashboard. Score panel updates every 3s. Timeline chart extends on each poll with smooth animation. Mobile layout at 375px has no horizontal scroll. "Match Over" banner renders when backend reports match result. "Waiting for live data" spinner shown when no file / stale.

---

### Phase D — Docker Compose + Caddy (FR-008, DC-001–DC-009)

Deliverables: `Dockerfile`, `docker-compose.yml`, `docker-compose.dev.yml`, `Caddyfile`, `dashboard/.env.example`

Key decisions:
- `api` service: `python:3.12-slim`; Tailwind CLI build (`npm ci && npx tailwindcss ...`) at image build time; `uvicorn app.main:app --workers 4`
- `caddy` service: `caddy:2.9-alpine`; auto-provisions Let's Encrypt cert for `DOMAIN`; HTTP → HTTPS 301; gzip; proxies to `api:8000`
- Named volume `caddy_data` persists TLS certs across Caddy restarts
- Named volume `auth_db` persists `auth.db` SQLite across API restarts
- `./data:/app/data:ro` bind-mount: host prediction backend writes JSON; `api` container reads it
- Only ports 80 and 443 exposed to host; `api:8000` internal only

Acceptance: `docker compose up --build -d` on a VPS starts both services. `curl https://DOMAIN/health` → 200. HTTP requests redirect to HTTPS.

---

### Phase E — Security hardening (FR-014–FR-018, SC-008)

Deliverables: updates to `routers/auth.py`, `database.py`; confirmed by `test_auth.py` cases

| Requirement | Implementation |
|---|---|
| FR-014: bcrypt/argon2 hashing | `pwdlib` Argon2id, cost verified in test |
| FR-015: JWT sig + expiry validation | `jwt.decode(..., algorithms=["HS256"])` raises on bad sig / expiry; tested |
| FR-016: refresh token rotation + revocation | Atomic DB delete + insert; replay → revoke all; tested |
| FR-017: login rate limiting | `@limiter.limit("5/minute")` via slowapi; tested with 6 rapid requests |
| FR-018: HTTPS | Caddy Caddyfile enforces redirect; confirmed in Phase D |

Acceptance: All `test_auth.py` security cases pass. `docker compose config` shows no plaintext secrets.

---

## Post-Phase 1 Constitution Re-check

| Principle | Status |
|---|---|
| I. Tournament-agnostic | ✅ PASS — `league` read from JSON, zero hardcoding |
| IV. Data integrity | ✅ PASS — dashboard never writes match data |
| V. Calibration | ✅ N/A — probabilities displayed as-received |
| Code quality | ✅ PLANNED — typed + tested |

**All gates pass. Safe to proceed to `/speckit.tasks`.**

## Complexity Tracking

No constitution violations. No entries required.
