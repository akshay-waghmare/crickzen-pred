# Research: SaaS Prediction Dashboard

**Branch**: `001-saas-prediction-dashboard` | **Date**: 2026-02-18  
**Status**: Complete — all NEEDS CLARIFICATION resolved

---

## Auth Stack

**Decision:** `PyJWT` (HS256) + `pwdlib[argon2]` + manual FastAPI endpoints (~100 lines)

**Rationale:**
- PyJWT is the FastAPI-official recommendation since 2024; `python-jose` has a CVE history and is stale (last release May 2025).
- `pwdlib[argon2]` replaces the unmaintained `passlib` (broken on Python 3.13+); same Argon2id algorithm under the hood.
- Manual endpoints over `fastapi-users` — fastapi-users adds OAuth, email verification, role management. For 50 users gating a dashboard it is pure bloat.

**Alternatives rejected:** `python-jose` (CVEs), `passlib` (unmaintained, Python 3.13 breaks), `fastapi-users` (too heavy).

**Packages:** `PyJWT>=2.11`, `pwdlib[argon2]>=0.3`

---

## Refresh Token Design

**Decision:** Opaque random token (`secrets.token_urlsafe(32)`) stored as `sha256(token)` in SQLite; rotated on every use (old token deleted, new token issued atomically).

**Rationale:** JWTs cannot be revoked server-side without a blocklist. An opaque token stored in SQLite is trivially revocable (`DELETE FROM refresh_tokens WHERE token_hash = ?`), survives server restarts (unlike an in-memory dict), and adds zero ops overhead for 50 users.

**Critical detail:** Store `sha256(raw_token)` in the DB — treat refresh tokens like passwords. If the DB leaks, hashed tokens cannot be used directly.

**Alternatives rejected:** In-memory dict (data lost on restart, catastrophic during a live match), Redis (ops overhead for 50 users), JWT refresh tokens (not revocable without extra blocklist table).

---

## Session Lifetime (client-side)

**Decision:** Proactive `setTimeout`-based silent refresh triggering 5 minutes before access token expiry. No idle timeout. Zero visible interruption to a user watching a live match.

**Rationale:** Reactive (401-triggered) refresh causes a brief request failure visible to the polling loop. Proactive refresh runs before expiry, keeping the access token perpetually valid while the tab is open.

**Cricket-specific gotcha:** Chrome throttles background timers but does not kill them for tabs with active network connections. A tab open for 6+ hours (a full T20 match) will refresh correctly.

**Client code:** `setTimeout(silentRefresh, tokenLifetimeMs - 5*60*1000)` called on login and after every refresh.

---

## Database

**Decision:** SQLite (WAL mode) via `SQLModel`. Two tables: `users`, `refresh_tokens`. No separate DB container.

**Rationale:** 50 users × ≤5 sessions = 250 refresh token rows maximum. SQLite handles thousands of concurrent reads; the rare login write is serialized but negligible. WAL mode (`PRAGMA journal_mode=WAL`) prevents reads from blocking during writes.

**Schema:**
- `users`: `id (uuid)`, `email (unique, indexed)`, `hashed_password`, `is_active`, `created_at`
- `refresh_tokens`: `id`, `token_hash (sha256, unique, indexed)`, `user_id (FK)`, `expires_at`, `created_at`, `revoked`

**Alternatives rejected:** PostgreSQL (ops overhead for 50 users), Redis (no persistence, ops overhead), in-memory (non-persistent).

**Packages:** `sqlmodel>=0.0.34`

---

## Rate Limiting

**Decision:** `slowapi` in-memory backend, `@limiter.limit("5/minute")` on `POST /auth/login` only.

**Rationale:** Single decorator, zero config, no Redis dependency. In-memory backend resets on restart — acceptable because a restart clears the failed-attempt window, which is a minor security trade-off justified by the operational simplicity for a 50-user system.

**Gotcha:** `slowapi` requires `request: Request` as an explicit parameter in the endpoint function signature — omitting it silently disables rate limiting.

**Packages:** `slowapi>=0.1.9`

---

## Frontend Framework

**Decision:** Alpine.js 3.14 + Tailwind CSS 4 CLI build.

**Rationale:** Alpine.js provides reactive `x-data`/`x-bind` directives (15 KB gzipped) that wire score, wickets, and win-probability values into the HTML template without framework overhead. Tailwind CLI produces a single purged CSS file (~10–15 KB) at Docker image build time.

**Why not HTMX:** HTMX polls DOM fragments (server-rendered HTML). For a live chart updating in-place, the chart library (Chart.js) owns its canvas state — HTMX would destroy and recreate the canvas every 3 seconds, losing animation continuity.

**Why not Vanilla JS alone:** `x-data` reactivity saves hundreds of `document.getElementById` lines that would otherwise be needed to bind live values into the template.

**Alternatives rejected:** React/Vue (overkill, violates no-framework constraint), HTMX-only (incompatible with chart state), Vanilla JS (viable but verbose).

---

## Charting Library

**Decision:** Chart.js 4.4.7 (UMD build, vendored in `static/js/`).

**Rationale:** 63 KB gzipped, `chart.update('active')` extends the probability line with smooth animation on each poll — exactly right for a live win-probability timeline. No build step required (UMD `<script>` tag). Supports phase-boundary annotations via `Chart.js` annotation plugin.

**Alternatives rejected:** Apache ECharts (~800 KB gzipped — too heavy for a simple line chart), Plotly.js (~3 MB — severe overkill), Lightweight-charts (purpose-built for financial OHLC, not general probability timelines).

---

## Backend Serving Strategy

**Decision:** Single FastAPI app: Jinja2 templates + `StaticFiles` mount. Tailwind CLI build runs at Docker image build time producing `static/css/app.css`.

**Auth layers:**
1. Page routes (`GET /`, `GET /login`) — HTTP-only session cookie checked by a Jinja2 dependency; redirect to `/login` if invalid.
2. API routes (`GET /api/live-state`) — `Authorization: Bearer <jwt>` validated by `HTTPBearer` dependency.

**Live state delivery:** `GET /api/live-state` reads `data/live_state.json` via `Path.read_text()` — sub-millisecond, no DB, no Redis. The file is bind-mounted read-only from the host into the API container.

---

## Docker Compose Architecture

**Decision:** 2 services — `api` (FastAPI/Uvicorn) + `caddy` (reverse proxy + TLS). SQLite lives as a file inside the `api` container's named volume. No separate DB container.

```
caddy:2.9-alpine  → TLS termination, HTTPS redirect, proxy to api:8000
api (python:3.12-slim) → FastAPI + Uvicorn (4 workers) + SQLite auth DB
```

**Data flow:** Host prediction backend writes `data/live_state.json` → bind-mounted `:ro` into `api` container → served at `GET /api/live-state`.

**Exposed ports:** 80 (HTTP → redirect) and 443 (HTTPS) only. All inter-service communication on the internal Docker network.

**Alternatives rejected:** Nginx (requires certbot sidecar + cron for TLS; ~40-line config vs Caddy's 8-line Caddyfile), separate PostgreSQL container (overkill for 50 users).

---

## Reverse Proxy

**Decision:** Caddy 2.9-alpine.

**Rationale:** Automatic Let's Encrypt provisioning and renewal with zero config. Full HTTPS with HTTP/2 in 8 lines of Caddyfile. Nginx requires a certbot sidecar container, renewal cron job, and a complex `nginx.conf`. JWT validation stays in FastAPI (not at the proxy) — Caddy's JWT plugin requires a custom build; Nginx's `auth_jwt` is NGINX Plus (paid).

---

## Summary: Resolved Clarifications

| Topic | Decision |
|---|---|
| JWT library | PyJWT 2.11 / HS256 |
| Password hashing | pwdlib Argon2id |
| Auth framework | Manual (~100 lines) |
| Refresh tokens | Opaque, sha256-hashed, SQLite-persisted, rotated on use |
| Session refresh | Proactive `setTimeout`, 5 min margin, no idle timeout |
| Database | SQLite WAL + SQLModel (no extra container) |
| Rate limiting | slowapi in-memory, 5/min on login endpoint |
| Frontend | Alpine.js 3.14 + Tailwind CSS 4 CLI |
| Charts | Chart.js 4.4.7 UMD vendored |
| Backend serving | FastAPI Jinja2 + StaticFiles, single app |
| Deployment | Docker Compose: `api` + `caddy` (2 services) |
| Reverse proxy | Caddy 2.9 (auto-HTTPS) |
