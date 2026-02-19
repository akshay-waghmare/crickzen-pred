# Data Model: SaaS Prediction Dashboard

**Branch**: `001-saas-prediction-dashboard` | **Date**: 2026-02-18

---

## Entities

### User

Represents a registered subscriber who can access the dashboard.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `str` (UUID4) | PK | Generated on creation |
| `email` | `str` | UNIQUE, NOT NULL, indexed | Login identity |
| `hashed_password` | `str` | NOT NULL | Argon2id hash via pwdlib |
| `is_active` | `bool` | NOT NULL, default `True` | Owner can deactivate without deleting |
| `created_at` | `datetime` | NOT NULL, UTC | Immutable after creation |

**State transitions:**
- `is_active=True` → user can log in and receive access tokens
- `is_active=False` → login returns 403; existing valid access tokens still pass (short-lived ≤60 min), but refresh is rejected immediately → session dies naturally within 60 min of deactivation

**Validation rules:**
- `email` must be a valid RFC 5321 address
- `hashed_password` must never be stored as plaintext; raw password never logged

---

### RefreshToken

Tracks long-lived refresh tokens for session continuity and revocation.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `int` | PK, auto-increment | Internal only |
| `token_hash` | `str` | UNIQUE, NOT NULL, indexed | `sha256(raw_token)` — raw token never stored |
| `user_id` | `str` | FK → `users.id`, NOT NULL | Owner of this token |
| `expires_at` | `datetime` | NOT NULL, UTC | Login time + 30 days |
| `created_at` | `datetime` | NOT NULL, UTC | Immutable after creation |
| `revoked` | `bool` | NOT NULL, default `False` | Set to True on explicit logout; OR deleted on rotation |

**State transitions:**
- Created on successful login
- **Consumed (deleted)** on successful `/auth/refresh` — new token pair issued atomically
- **Revoked (revoked=True)** on `/auth/logout` or owner deactivating user
- **Purged** when `expires_at` passes (background cleanup task)

**Security note:** If a `token_hash` is presented but already consumed (deleted) or revoked, it is treated as a replay attack. All remaining tokens for that `user_id` are revoked immediately.

---

### MatchState (Read-only, no DB table)

A snapshot of live match data, read from `data/live_state.json` written by the existing prediction backend. Never written by the dashboard — it is read-only from the dashboard's perspective.

| Field | Type | Source | Notes |
|---|---|---|---|
| `batting_team` | `str` | predictor | Team code e.g. `"SYS"` |
| `bowling_team` | `str` | predictor | |
| `score` | `int` | predictor | Runs scored |
| `wickets` | `int` | predictor | Wickets fallen |
| `overs` | `float` | predictor | e.g. `14.3` |
| `target` | `int \| None` | predictor | Second innings only |
| `bat_win_prob` | `float` | predictor | 0.0–1.0 |
| `bowl_win_prob` | `float` | predictor | 0.0–1.0 |
| `current_run_rate` | `float` | predictor | |
| `required_run_rate` | `float \| None` | predictor | Second innings only |
| `is_second_innings` | `bool` | predictor | |
| `phase` | `str` | predictor | `"powerplay"`, `"middle"`, `"death"` |
| `league` | `str` | predictor | e.g. `"bbl"`, `"sa20"` |
| `history` | `list[HistoryPoint]` | predictor | Ball-by-ball history |
| `timestamp` | `str` | predictor | ISO8601, written by backend |

---

### HistoryPoint (embedded in MatchState.history)

One entry per delivery in the match, used to render the probability timeline chart.

| Field | Type | Notes |
|---|---|---|
| `ball` | `str` | e.g. `"14.3"` |
| `over` | `int` | 0-indexed |
| `bat_win_prob` | `float` | 0.0–1.0 |
| `is_wicket` | `bool` | For wicket marker on chart |
| `is_boundary` | `bool` | For boundary marker (optional) |
| `phase` | `str` | For phase-boundary markers |
| `innings` | `int` | 1 or 2 |

---

## Relationships

```
User (1) ──────< RefreshToken (*)   one user has many refresh tokens
                                    (one per active session/device)

MatchState  ──embedded──> HistoryPoint (*)   read from JSON, no DB relationship
```

---

## Stale Data Detection

The dashboard must detect when `data/live_state.json` is stale (backend has stopped writing):

| Condition | Dashboard behaviour |
|---|---|
| File does not exist | Show "Waiting for live data" state |
| File exists, `timestamp` age ≤ 60 s | Show live data normally |
| File exists, `timestamp` age > 60 s | Show "Data may be delayed" warning badge; continue showing last known values |
| JSON parse error | Show "Waiting for live data" state; log server-side warning |

---

## Access Control Summary

| Resource | Rule |
|---|---|
| `GET /` (dashboard page) | Valid HTTP-only session cookie required; redirect to `/login` otherwise |
| `GET /api/live-state` | Valid `Authorization: Bearer <access_token>` required |
| `POST /auth/login` | Public; rate-limited 5/min per IP |
| `POST /auth/refresh` | Valid `refresh_token` HTTP-only cookie required |
| `POST /auth/logout` | Valid `refresh_token` HTTP-only cookie required (to revoke it) |
| `GET /static/*` | Public (CSS, JS, images) |
| `GET /health` | Public (Docker healthcheck) |
