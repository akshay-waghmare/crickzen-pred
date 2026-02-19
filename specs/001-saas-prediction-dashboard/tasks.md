---
description: "Task list for SaaS Prediction Dashboard"
---

# Tasks: SaaS Prediction Dashboard

**Input**: Design documents from `/specs/001-saas-prediction-dashboard/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/api.yaml ✅, quickstart.md ✅

**Organization**: Tasks are grouped by phase (Setup → Foundation → User Stories → Polish). Each user-story phase is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to ([US1]–[US5])

---

## Phase 1: Setup

**Purpose**: Create the `dashboard/` top-level package structure, pin dependencies, and scaffold the project so all subsequent phases can begin.

- [X] T001 Create `dashboard/` directory tree: `app/`, `app/routers/`, `templates/`, `static/css/`, `static/js/` per plan.md Project Structure
- [X] T002 [P] Create `dashboard/requirements.txt` pinning FastAPI==0.115.*, uvicorn[standard], PyJWT==2.11.*, pwdlib[argon2]==0.3.*, SQLModel==0.0.34, slowapi==0.1.9, jinja2==3.1.*, python-multipart, pydantic-settings, httpx, pytest, pytest-anyio
- [X] T003 [P] Create `dashboard/package.json` with `tailwindcss` CLI devDependency and `dashboard/.env.example` documenting all env vars: JWT_SECRET, DOMAIN, ADMIN_EMAIL, ADMIN_PASSWORD, POLL_INTERVAL_MS, STATE_FILE, DATABASE_URL, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
- [X] T004 [P] Create `dashboard/tailwind.config.js` scanning `templates/**/*.html` and `static/js/*.js`; create `dashboard/static/css/input.css` with Tailwind @tailwind directives
- [X] T005 [P] Create `tests/dashboard/__init__.py` and `tests/dashboard/conftest.py` with a FastAPI TestClient fixture using an in-memory SQLite database URL

**Checkpoint**: `dashboard/` directory exists with all subdirectories, `requirements.txt` is present, `tests/dashboard/conftest.py` is ready.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core auth infrastructure that MUST be complete before any user-story work can begin. Provides `User`, `RefreshToken` models, the SQLite database engine, and the auth utility layer that every route depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 Create `dashboard/app/config.py` using `pydantic-settings BaseSettings` reading `JWT_SECRET`, `DOMAIN`, `POLL_INTERVAL_MS` (default 3000), `STATE_FILE` (default `data/live_state.json`), `DATABASE_URL`, `ACCESS_TOKEN_EXPIRE_MINUTES` (default 55), `REFRESH_TOKEN_EXPIRE_DAYS` (default 30), `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `SESSION_CAP` (default 50)
- [X] T007 Create `dashboard/app/models.py` with SQLModel `User` (id UUID4 PK, email UNIQUE, hashed_password, is_active bool default True, created_at) and `RefreshToken` (id int PK autoincrement, token_hash UNIQUE, user_id FK, expires_at, created_at, revoked bool default False) per data-model.md
- [X] T008 Create `dashboard/app/database.py` with SQLite engine (WAL mode via `PRAGMA journal_mode=WAL`), `get_session` dependency, `create_db_and_tables()` startup function, and `seed_admin_user()` that creates admin from `ADMIN_EMAIL`/`ADMIN_PASSWORD` env vars if not exists
- [X] T009 Create `dashboard/app/auth.py` implementing: `hash_password(plain)`, `verify_password(plain, hashed)` via pwdlib Argon2id; `create_access_token(user_id, expires_minutes)` returning HS256 JWT; `verify_access_token(token)` raising 401 on bad signature/expiry; `create_refresh_token(user_id, session, expires_days)` storing sha256-hashed opaque token; `rotate_refresh_token(raw_token, session)` atomically deletes old + inserts new, replay → revoke all user tokens; `purge_expired_tokens(session)` deleting rows where expires_at < now
- [X] T010 Create `dashboard/app/main.py` as FastAPI app factory: register lifespan (calls `create_db_and_tables`, `seed_admin_user`, `purge_expired_tokens`); mount `StaticFiles` at `/static`; attach Jinja2 `templates/`; include all routers; attach slowapi `Limiter` middleware

**Checkpoint**: `pytest tests/dashboard/test_models.py` passes (schema validation). App starts without errors (`uvicorn dashboard.app.main:app`).

---

## Phase 3: User Story 5 — Access Control / Subscription Gate (Priority: P3 but foundational)

> **Note**: US5 is listed P3 in spec.md but must be implemented **before** US1 because the live endpoint depends on JWT auth. US5 tasks complete the auth router layer.

**Goal**: Enforce login gate so unauthenticated users cannot access any prediction data. Enable owner to add/deactivate subscribers.

**Independent Test**: `pytest tests/dashboard/test_auth.py` — covers: successful login returns JWT + sets cookie; invalid password returns 401; inactive user returns 403; refresh rotation returns new pair; logout invalidates token; replay attack revokes all user tokens; 6th login attempt returns 429.

- [X] T011 [US5] Create `dashboard/app/routers/auth.py`: `POST /auth/login` (rate-limited `5/minute` via slowapi, validates email+password, checks `is_active`, enforces SESSION_CAP, issues JWT body + HttpOnly refresh cookie); `POST /auth/refresh` (reads cookie, calls `rotate_refresh_token`, issues new pair); `POST /auth/logout` (revokes refresh token, clears cookie); `POST /auth/users` (admin-only: creates new subscriber user) per contracts/api.yaml
- [X] T012 [P] [US5] Create `dashboard/app/routers/pages.py`: `GET /login` renders `templates/login.html`; `GET /` redirects unauthenticated requests to `/login`, renders `templates/dashboard.html` for authenticated users
- [X] T013 [P] [US5] Create `dashboard/app/health.py`: `GET /health` returns `{"status": "ok", "version": APP_VERSION}` — no auth required (used by Caddy probe + Docker healthcheck)
- [X] T014 [US5] Create `tests/dashboard/test_auth.py` with pytest cases: login success/fail, inactive user 403, refresh rotation, logout + cookie clear, replay attack revokes all tokens, rate-limit (6 rapid calls → 429), SESSION_CAP enforcement, admin creates subscriber

**Checkpoint**: `pytest tests/dashboard/test_auth.py` fully green. `GET /login` returns 200. `GET /` without token redirects to `/login`.

---

## Phase 4: User Story 1 — Live Match Win Probability View (Priority: P1) 🎯 MVP

**Goal**: Authenticated subscribers see current win probability, live scorecard, and auto-refreshing data from the backend JSON state file.

**Independent Test**: `pytest tests/dashboard/test_live.py` + manual test by placing a sample `live_state.json` and opening `GET /` in a browser with a valid JWT — verify score, win probability values, and stale indicator all render correctly.

- [X] T015 [US1] Create `dashboard/app/routers/live.py`: `GET /api/live-state` — requires Bearer JWT via `verify_access_token` dependency; reads `STATE_FILE` via `Path.read_text()`; computes ETag as `str(mtime)`; returns 304 if `If-None-Match` matches; appends `"stale": true` if `timestamp` field in JSON is >60s old; returns 404 with JSON error if file missing; injects `poll_interval_ms` from config into response per contracts/api.yaml
- [X] T016 [P] [US1] Create `tests/dashboard/test_live.py` with cases: 401 no token, 200 with valid token + file present, `stale:true` when file >60s old, 304 on matching ETag, 404 when file absent, `poll_interval_ms` present in response body
- [X] T017 [US1] Create `dashboard/templates/base.html`: dark slate-900 HTML shell; `<link>` to `static/css/app.css`; vendor script tags for `alpine.min.js` and `chart.umd.min.js`; Alpine.js `x-data` root store initialised with `accessToken`, `pollIntervalMs`, `matchState`; `{% block content %}` slot
- [X] T018 [US1] Create `dashboard/templates/login.html` extending base.html: centered card; email + password `<input>`s; submit calls `POST /auth/login` via fetch, stores JWT in memory (`accessToken`), redirects to `/`; displays error message on 401/403
- [X] T019 [US1] Create `dashboard/templates/dashboard.html` extending base.html: score panel with Alpine `x-text` bindings (`score`, `wickets`, `overs`, `target`, `runs_needed`); win-probability section (populated via JS — canvas placeholders for Chart.js gauges); probability timeline canvas; "Waiting for live data" spinner shown when `matchState.stale` is true or state is null; "Match Over" banner shown when `matchState.match_over` is true

**Checkpoint**: User Story 1 fully functional: log in → dashboard → live data polls every 3s → score and probability visible → stale state shows spinner.

---

## Phase 5: User Story 2 — Attractive, Professional UI (Priority: P2)

**Goal**: The dashboard is visually polished, dark-themed, branded, and mobile-responsive — nothing resembling raw Streamlit widgets.

**Independent Test**: Load `dashboard.html` with sample match data in a browser at 1280px and 375px. Confirm: dark theme, branded header, smooth visual updates, no Streamlit chrome, no horizontal overflow on mobile.

- [X] T020 [P] [US2] Download and vendor `alpine.min.js` v3.14 to `dashboard/static/js/alpine.min.js` and `chart.umd.min.js` v4.4.7 to `dashboard/static/js/chart.umd.min.js` (no CDN dependency at runtime)
- [X] T021 [US2] Update `dashboard/static/css/input.css` with custom Tailwind theme: slate-900/800/700 surface colours; emerald-500 / rose-500 team accent classes; custom font stack (Inter/system-ui); animation utilities for gauge transitions
- [X] T022 [US2] Update `dashboard/templates/base.html` with branded header (app name, league badge, live indicator dot), nav, and responsive grid (`grid-cols-1 sm:grid-cols-2 lg:grid-cols-3`) wrapping content blocks
- [X] T023 [US2] Update `dashboard/templates/dashboard.html` with full mobile-responsive layout: stacked single-column on 375px, 2-col gauges on sm, 3-col full layout on lg; score panel styled with large typography; animated transitions via Tailwind `transition-all duration-300`; team colour variables resolved from league in match state; "Innings Break" status label when `match_state.innings_break` is true

**Checkpoint**: Visual quality check: dark theme consistent, no horizontal scroll at 375px, score panel readable, gauges visible, branded header present.

---

## Phase 6: User Story 3 — Win Probability Timeline Chart (Priority: P2)

**Goal**: Ball-by-ball win probability chart with phase boundary markers, wicket markers, innings 2 start indicator, and smooth live updates.

**Independent Test**: Feed a pre-recorded 20-over `history` array (with wickets) to the chart component via `matchState.history` and verify phase lines at over 6/16, red wicket scatter points, team-coloured probability line, and smooth animation on `chart.update('active')`.

- [X] T024 [US3] Create `dashboard/static/js/dashboard.js`: Alpine.js component `dashboardApp()` with: `init()` setting up Chart.js line chart on `#prob-chart` canvas with team-colour dataset, phase boundary vertical annotations, wicket scatter overlay; `startPollLoop()` calling `GET /api/live-state` every `pollIntervalMs` ms with `If-None-Match` ETag header, updating chart data on 200, skipping on 304; `scheduleRefresh()` setting `setTimeout` for `(ACCESS_TOKEN_EXPIRE_MS - 5*60*1000)` ms then calling `POST /auth/refresh` and rescheduling; CRR/RRR bar chart update; stale/match-over state handlers
- [X] T025 [P] [US3] Update `dashboard/templates/dashboard.html` to add: `<canvas id="prob-chart">` for probability timeline; `<canvas id="gauge-home">` and `<canvas id="gauge-away">` for half-donut win-prob gauges; `<canvas id="rr-chart">` for CRR vs RRR bar; all wired to Alpine `x-init` calling `dashboardApp()` init methods
- [X] T026 [US3] Update `dashboard/static/js/dashboard.js` to complete gauge charts: Chart.js doughnut config (half-donut via `rotation: -90, circumference: 180`), team-colour fill, percentage label in centre via custom plugin; gauges update on each poll with `chart.update('active')` for smooth transition; wicket markers rendered as a separate scatter `dataset` layered on the probability line chart

**Checkpoint**: Timeline chart shows full match history with phase lines and wicket dots. Gauges animate smoothly between polls. CRR/RRR bar visible in second innings.

---

## Phase 7: User Story 4 — Multi-League & Calibration Selector (Priority: P3)

**Goal**: Power users can select the active league from a dropdown; the dashboard displays the correct league-calibrated probability from the JSON state, with a fallback notice for leagues without a dedicated calibrator.

**Independent Test**: Manually switch the league in the dropdown and verify the displayed probability reflects the `league` field in `live_state.json`; when the league has no calibrator, a notice "Using global T20 model" is shown.

- [X] T027 [US4] Update `dashboard/templates/dashboard.html` to add a league selector `<select>` populated from `matchState.available_leagues` (or a hardcoded list from config); bind selection to Alpine `selectedLeague`; display calibration chain notice (raw → phase → per-over → league) or "Using global T20 model" fallback badge
- [X] T028 [P] [US4] Update `dashboard/app/routers/live.py` to: read `league` from query param (optional, defaults to `matchState.league`); pass `selected_league` through to response JSON; add `calibration_chain` field to response when league calibrator is available (read from config or filesystem probe on `models/t20_male_v2/league_calibrators/<league>/`)
- [X] T029 [US4] Update `dashboard/static/js/dashboard.js` to re-include `selectedLeague` as a query param on each `GET /api/live-state?league=<value>` poll call; display calibration chain badge from `response.calibration_chain`; show "Using global T20 model" notice when chain only shows raw probability

**Checkpoint**: League selector visible; switching league changes calibration chain badge; fallback notice appears for unsupported leagues.

---

## Phase 8: Docker Compose + Caddy (FR-008, DC-001–DC-009)

**Goal**: The entire dashboard is deployable on a fresh Linux VPS with `docker compose up --build -d`. HTTPS is automatic via Caddy Let's Encrypt.

**Independent Test**: Run `docker compose up --build -d` locally (with `DOMAIN=localhost` or self-signed), then `curl http://localhost/health` → 200, `curl http://localhost/` → 301 redirect to https (or 200 with local override). Verify `auth_db` and `caddy_data` named volumes exist.

- [X] T030 Create `dashboard/Dockerfile`: `FROM python:3.12-slim`; install `nodejs` + `npm`; `COPY requirements.txt` + `pip install`; `COPY package.json` + `npm ci`; build Tailwind CSS (`npx tailwindcss -i static/css/input.css -o static/css/app.css --minify`); `COPY . .`; `HEALTHCHECK` via `curl /health`; `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]`
- [X] T031 [P] Create `Caddyfile` at repo root: `{$DOMAIN}` block with `encode gzip`, `reverse_proxy api:8000`, automatic HTTPS (Let's Encrypt); HTTP→HTTPS redirect handled by Caddy default
- [X] T032 [P] Create `docker-compose.yml` with services: `api` (build `./dashboard`, env_file `.env`, volumes `auth_db:/app/auth.db`, `./data:/app/data:ro`); `caddy` (image `caddy:2.9-alpine`, volumes `caddy_data:/data`, bind-mount `./Caddyfile`); ports `80:80`, `443:443`; named volumes `auth_db`, `caddy_data`; inter-service network `dashboard_net`
- [X] T033 [P] Create `docker-compose.dev.yml` overriding: `api` on `ports: ["8000:8000"]`; no caddy service; `STATE_FILE` pointing to local `data/live_state.json`; `DATABASE_URL=sqlite:///./auth_dev.db`; hot-reload via `uvicorn --reload`

**Checkpoint**: `docker compose up --build -d` starts both services. `curl https://DOMAIN/health` returns `{"status":"ok"}`. HTTP port 80 redirects to HTTPS.

---

## Phase 9: Security Hardening (FR-014–FR-018, SC-008)

**Goal**: All security requirements verified by automated tests. No plaintext secrets in source or images.

**Independent Test**: `pytest tests/dashboard/test_auth.py` security-specific cases all pass. `docker compose config` output has no `JWT_SECRET` value visible (confirms env_file sourcing). `grep -r "JWT_SECRET\|ADMIN_PASSWORD" dashboard/` returns only `.env.example`.

- [X] T034 Update `tests/dashboard/test_auth.py` to add security-specific cases: Argon2id cost factor ≥ 12 verified on stored hash; bad JWT signature returns 401; expired JWT returns 401; `POST /auth/refresh` with already-consumed token revokes all user tokens and returns 401; `POST /auth/login` 6th attempt within 1 min returns 429; `POST /auth/users` without admin JWT returns 403
- [X] T035 [P] Update `dashboard/app/database.py` to add `purge_expired_tokens()` called on startup lifespan and as a scheduled background task (using `asyncio.create_task` with a 1-hour sleep loop)
- [X] T036 [P] Update `dashboard/app/auth.py` to add `enforce_session_cap(user_id, session)` check before issuing tokens in login — counts non-expired, non-revoked tokens for all users; if count ≥ `SESSION_CAP` raises 503 with `{"detail": "capacity_reached"}`
- [X] T037 Add `.dockerignore` to `dashboard/` excluding `.env`, `auth*.db`, `__pycache__`, `node_modules`, `.git`; add `.gitignore` entries for `dashboard/.env`, `dashboard/auth*.db`, `dashboard/static/css/app.css`, `dashboard/node_modules/`

**Checkpoint**: All 14+ `test_auth.py` cases green. No secrets in Docker image layers (`docker history dashboard-api` shows no env vars). `.env` excluded from git.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Final touches that span multiple user stories.

- [X] T038 [P] Run `quickstart.md` validation: follow the local dev quick-start steps exactly on a clean environment; fix any steps that fail
- [X] T039 [P] Add `pyproject.toml` or `pytest.ini` under `tests/dashboard/` setting `asyncio_mode = "auto"` and `testpaths`; ensure `pytest tests/dashboard/` runs clean with no warnings
- [X] T040 [P] Add type annotations to all Python files in `dashboard/app/`; run `mypy dashboard/app/` and fix any errors (or add `# type: ignore` with justification comments for SQLModel dynamic attrs)
- [X] T041 [P] Create `dashboard/tests/dashboard/test_models.py` with SQLModel schema validation: User requires email uniqueness, RefreshToken FK enforced, UUID4 generated on User creation, `created_at` is UTC
- [X] T042 Update `README.md` at repo root with a new "## SaaS Dashboard" section linking to `specs/001-saas-prediction-dashboard/quickstart.md` and documenting the `docker compose up` command

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user story phases
- **Phase 3 (US5 Auth)**: Depends on Phase 2 — must complete before Phase 4 (live endpoint needs JWT middleware)
- **Phase 4 (US1 Live View)**: Depends on Phase 3 — first independently testable MVP increment
- **Phase 5 (US2 UI)**: Depends on Phase 4 (templates exist) — can be parallelised with Phase 6
- **Phase 6 (US3 Chart)**: Depends on Phase 4 (canvas scaffolding exists) — can be parallelised with Phase 5
- **Phase 7 (US4 League)**: Depends on Phase 4 — can start after MVP is confirmed
- **Phase 8 (Docker)**: Depends on Phase 4 — can be done once core app is functional
- **Phase 9 (Security)**: Depends on Phase 3 (auth.py complete) — can run alongside Phases 5–7
- **Phase 10 (Polish)**: Depends on all prior phases

### User Story Dependencies

- **US5 (Auth)** → must complete before US1 (live endpoint requires JWT)
- **US1 (Live View)** → no dependency on US2, US3, US4 — independently testable
- **US2 (UI)** → no dependency on US3, US4 — independently testable
- **US3 (Chart)** → no dependency on US2, US4 — independently testable (shares canvas scaffold from US1)
- **US4 (League)** → no dependency on US2, US3 — independently testable

### Parallel Opportunities

- **Within Phase 1**: T002, T003, T004, T005 all operate on different files → run in parallel
- **Within Phase 2**: T006–T010 are sequential (each builds on the previous)
- **Within Phase 3**: T012, T013 can run in parallel with T011; T014 runs after T011
- **After Phase 4 is done**: Phases 5, 6, 7, 8, 9 can all start in parallel

---

## Parallel Example: Phase 4 (US1 MVP)

```bash
# Run these simultaneously (different files):
Task T016: tests/dashboard/test_live.py
Task T017: templates/base.html

# Then run T015 (live.py router) — depends on T016 test cases written
# Then run T018, T019 in parallel (login.html + dashboard.html)
```

---

## Implementation Strategy

### MVP First (US5 + US1 Only — Phases 1–4)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all)
3. Complete Phase 3: US5 Auth gate (login works, JWT middleware works)
4. Complete Phase 4: US1 Live view (score + probability polling)
5. **STOP and VALIDATE**: Log in, see live match data updating every 3s
6. Deploy to VPS with `docker compose -f docker-compose.dev.yml up`

### Incremental Delivery

1. **Phases 1–4 complete** → Functional but plain MVP (auth + live data)
2. **Phase 5** → Professional UI (commercial quality, mobile-ready)
3. **Phase 6** → Chart (probability timeline with wicket markers — "WOW" feature)
4. **Phase 7** → League selector (multi-league calibration)
5. **Phases 8–9** → Production-ready (Docker + Caddy + security hardening)
6. **Phase 10** → Polish + documentation

### Task Count Summary

| Phase | Story | Tasks | Notes |
|-------|-------|-------|-------|
| 1 Setup | — | T001–T005 | 5 tasks |
| 2 Foundational | — | T006–T010 | 5 tasks |
| 3 US5 Auth Gate | US5 | T011–T014 | 4 tasks |
| 4 US1 Live View | US1 | T015–T019 | 5 tasks — MVP |
| 5 US2 UI Polish | US2 | T020–T023 | 4 tasks |
| 6 US3 Chart | US3 | T024–T026 | 3 tasks |
| 7 US4 League | US4 | T027–T029 | 3 tasks |
| 8 Docker+Caddy | — | T030–T033 | 4 tasks |
| 9 Security | — | T034–T037 | 4 tasks |
| 10 Polish | — | T038–T042 | 5 tasks |
| **Total** | | **T001–T042** | **42 tasks** |

---

## Notes

- `[P]` tasks operate on different files and have no incomplete-task dependencies — safe to run simultaneously
- `[Story]` label maps each task to its user story for independent traceability
- **MVP scope**: Phases 1–4 (22 tasks, T001–T019) — delivers a working auth-gated live dashboard
- Stop at each Phase Checkpoint to validate the increment independently before proceeding
- Commit after each logical task group; avoid cross-story file conflicts
- The `dashboard/` package is entirely new code — zero risk of breaking the existing ML pipeline in `src/bbl_pipeline/`
