# CrickenZen Prediction Dashboard

A SaaS web dashboard for real-time T20 cricket win-probability predictions.
Subscribers get live ball-by-ball updates powered by the `XGBLogRegEnsemble` model with Monte Carlo simulations.

---

## Quick Start (Local Dev)

### 1 — Create a virtual environment and install Python dependencies
```bash
cd dashboard
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt     # Windows
# .venv/bin/pip install -r requirements.txt       # Linux/Mac
```

### 2 — Install JS dependencies & build CSS
```bash
npm install
npm run build:css    # produces static/css/app.css
```

### 3 — Create `.env`
```bash
copy .env.example .env   # then edit values
```

Minimum required:
```
JWT_SECRET=<random 32+ chars>
ADMIN_EMAIL=admin@crickenzen.com
ADMIN_PASSWORD=<strong password>
```

### 4 — Start the server
```bash
.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 in a browser.

---

## Architecture

```
Browser ←→ FastAPI (dashboard/app/) ←→ PredictionManager
                     ↓                        ↓
               SQLite (auth)     crex_live_predictor subprocesses
                                              ↓
                                       JSON state files
```

The dashboard reads prediction state from JSON files written by `crex_live_predictor` subprocesses. Each subscriber can start/stop their own match predictions.

---

## Features

- **JWT Authentication** — Secure login with access + refresh tokens
- **Subscriber Management** — Admin can create, suspend, reactivate users
- **Multi-Match Support** — Up to 6 concurrent predictions, 2 per user
- **Automatic Match Startup** — Optional CREX discovery/direct URL scheduler for deployed runs
- **Live Updates** — Polling every 3s for ball-by-ball win probability
- **League Auto-Detection** — Paste a CREX URL and the league is auto-detected
- **Session Capacity** — Configurable session cap (default: 50)
- **Rate Limiting** — Per-IP rate limiting via SlowAPI
- **Dark Theme** — Cricket-themed UI with Tailwind CSS

---

## Supported Leagues

| League | Code | Model |
|--------|------|-------|
| Indian Premier League | `ipl` | ipl_v6 |
| Pakistan Super League | `psl` | t20_male_v2 |
| Big Bash League | `bbl` | bbl_v12 |
| SA20 | `sa20` | t20_male_v2 |
| International League T20 | `ilt20` | ilt20_v5 |
| Women's Premier League | `wpl` | wpl_v2 |
| T20 World Cup | `t20i_male` | t20_international_male_v2 |
| Super Smash | `ssm` | t20_male_v2 |
| Bangladesh Premier League | `bpl` | t20_male_v2 |

---

## API Endpoints

### Auth
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/login` | Get JWT + refresh token |
| `POST` | `/auth/register` | Self-registration (if enabled) |
| `POST` | `/auth/refresh` | Rotate refresh token |
| `POST` | `/auth/logout` | Revoke refresh token |
| `GET`  | `/auth/me` | Current user profile |

### Predictions
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/matches/start` | Start a live prediction |
| `GET`  | `/api/matches` | List your predictions |
| `GET`  | `/api/matches/all` | List all active predictions |
| `GET`  | `/api/matches/{id}/state` | Get current match state |
| `DELETE` | `/api/matches/{id}/stop` | Stop a prediction |
| `GET`  | `/api/matches/{id}/stream` | SSE stream of match state |
| `GET`  | `/api/matches/leagues` | Available leagues |
| `GET`  | `/api/matches/detect-league` | Auto-detect league from URL |
| `GET`  | `/api/matches/auto/status` | Auto scheduler status |

### Admin
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/admin/subscribers` | Add subscriber |
| `GET`  | `/admin/subscribers` | List subscribers |
| `PATCH`| `/admin/subscribers/{id}/suspend` | Suspend account |
| `PATCH`| `/admin/subscribers/{id}/reactivate` | Reactivate account |

### System
| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Health check |

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JWT_SECRET` | ✅ | — | Secret key for signing JWTs |
| `ADMIN_EMAIL` | ✅ | — | Bootstrap admin email |
| `ADMIN_PASSWORD` | ✅ | — | Bootstrap admin password |
| `DOMAIN` | ❌ | `localhost` | Domain for HTTPS (Caddy) |
| `STATE_DIR` | ❌ | `data/dashboard_states` | Where prediction JSON files are written |
| `DATABASE_URL` | ❌ | `sqlite:///./auth.db` | SQLAlchemy connection string |
| `POLL_INTERVAL_MS` | ❌ | `3000` | Live update frequency in ms |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ❌ | `55` | JWT lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | ❌ | `30` | Refresh token lifetime |
| `SESSION_CAP` | ❌ | `50` | Max concurrent sessions |
| `MAX_USER_MATCHES` | ❌ | `2` | Max predictions per user |
| `MAX_TOTAL_MATCHES` | ❌ | `6` | Max system-wide predictions |
| `AUTO_PREDICTIONS_ENABLED` | ❌ | `false` | Enable deployed auto-start scheduler |
| `AUTO_LEAGUE_KEY` | ❌ | `IPL` | League to discover from CREX (`IPL`, `PSL`, etc.) |
| `AUTO_MATCH_URLS` | ❌ | — | CREX URLs to auto-start directly, separated by spaces or commas |
| `AUTO_DISCOVERY_URLS` | ❌ | — | Extra CREX pages to scan for match links |
| `AUTO_DISCOVER_FROM_CREX` | ❌ | `true` | Scan configured/default CREX pages for league match links |
| `AUTO_DISCOVERY_RENDER_JS` | ❌ | `true` | Use Playwright fallback when CREX links are client-rendered |
| `AUTO_DISCOVERY_INTERVAL_SECONDS` | ❌ | `300` | Scheduler polling frequency |
| `AUTO_START_NOT_BEFORE_LOCAL` | ❌ | `17:00` | Earliest local time for non-live discovered matches |
| `AUTO_START_NOT_AFTER_LOCAL` | ❌ | `23:59` | Latest local time for non-live discovered matches |
| `AUTO_TIMEZONE` | ❌ | `Asia/Kolkata` | Local timezone for auto-start window |
| `REGISTRATION_OPEN` | ❌ | `true` | Allow self-registration |

### Automatic CREX startup

For IPL deployment, set:

```env
AUTO_PREDICTIONS_ENABLED=true
AUTO_LEAGUE_KEY=IPL
```

The scheduler scans CREX's IPL 2026 series page and live-score pages. It starts live matches immediately, and starts scheduled discovered matches only inside the configured local evening window.

For the current PSL test URL, set:

```env
AUTO_PREDICTIONS_ENABLED=true
AUTO_MATCH_URLS=https://crex.com/cricket-live-score/lhq-vs-qtg-30th-match-pakistan-super-league-2026-match-updates-10XH
```

That URL is auto-detected as PSL and launches with `models/t20_male_v2` plus `data/psl_feature_store_v1`.

---

## Running Tests

```bash
cd dashboard
.venv\Scripts\pip install pytest httpx
.venv\Scripts\pytest tests/ -v
```

---

## Production Deploy (Docker)

```bash
# From project root
cp dashboard/.env.example dashboard/.env  # edit values
docker compose up -d
```

This starts:
- **dashboard** — FastAPI app on port 8000
- **caddy** — Reverse proxy with auto HTTPS on ports 80/443

---

## Project Structure

```
dashboard/
├── app/
│   ├── main.py              # FastAPI app factory
│   ├── config.py            # Settings + league configs
│   ├── models.py            # SQLModel ORM (User, RefreshToken, MatchPrediction)
│   ├── auth.py              # JWT, password hashing, token rotation
│   ├── database.py          # SQLite engine + session management
│   ├── health.py            # Health endpoint
│   ├── prediction_manager.py # Subprocess manager for predictions
│   └── routers/
│       ├── auth.py          # Login, register, refresh, logout
│       ├── admin.py         # Subscriber CRUD (admin-only)
│       ├── live.py          # Start/stop/poll/stream predictions
│       └── pages.py         # HTML page routes
├── templates/               # Jinja2 HTML templates
├── static/                  # CSS (Tailwind) + JS (Alpine.js, htmx)
├── tests/                   # pytest test suite
├── .env.example             # Environment variable template
├── Dockerfile               # Multi-stage Docker build
├── requirements.txt         # Python dependencies
├── package.json             # Tailwind/npm config
└── tailwind.config.js       # Tailwind config
```
