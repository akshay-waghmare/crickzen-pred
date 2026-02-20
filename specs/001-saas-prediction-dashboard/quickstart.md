# Quickstart: SaaS Prediction Dashboard

**Branch**: `001-saas-prediction-dashboard` | **Date**: 2026-02-18

This guide lets a developer run the full dashboard stack locally in under 5 minutes.

---

## Prerequisites

- Docker + Docker Compose installed
- The existing prediction backend (`crex_live_predictor`) already running and writing to `data/live_state.json`
- A domain name pointed at your VPS (for production HTTPS) — not required for local dev

---

## Local Development (no Docker needed)

### Terminal 1 — Dashboard server

```bash
# 1. Ensure you're on the feature branch
git checkout 001-saas-prediction-dashboard

# 2. Copy the env template and fill in values
cp dashboard/.env.example dashboard/.env
# Edit dashboard/.env:
#   JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
#   ADMIN_EMAIL=admin@yourapp.com
#   ADMIN_PASSWORD=YourPassword123!
#   STATE_FILE=../data/live_state.json   # relative to dashboard/ dir

# 3. Create a virtual environment and install deps
cd dashboard
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 4. Build Tailwind CSS (requires Node.js)
npm install
node_modules/.bin/tailwindcss -i static/css/input.css -o static/css/app.css --minify

# 5. Start the server (seeds admin user on first run)
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
# Open http://localhost:8000  — login with ADMIN_EMAIL / ADMIN_PASSWORD
```

### Terminal 2 — Live prediction engine

```bash
# From the repo root — uses the project's main .venv
# Install ML deps if needed:
python3 -m venv .venv && .venv/bin/pip install -e . && .venv/bin/pip install playwright
.venv/bin/playwright install chromium

# Start predictor for any live T20 match:
.venv/bin/python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "https://crex.com/scoreboard/.../live" \
  --model-dir models/t20_male_v2 \
  --feature-store-dir data/bbl_feature_store_v2 \
  --output-json data/live_state.json \
  --record-states
```

The dashboard polls `GET /api/live-state` every 3 s and shows "Waiting for live data" until the state file appears.

> **Scikit-learn version note:** Models were trained with scikit-learn 1.7.2. If you see `_fill_dtype` errors on startup, pin it: `.venv/bin/pip install "scikit-learn==1.7.2"`

---

## Production Deployment (VPS + HTTPS)

```bash
# 1. SSH into your VPS
ssh user@your.domain.com

# 2. Clone the repo
git clone https://github.com/akshay-waghmare/crickzen-pred.git
cd crickzen-pred
git checkout 001-saas-prediction-dashboard

# 3. Set up environment
cp dashboard/.env.example dashboard/.env
nano dashboard/.env
# Set:  JWT_SECRET (openssl rand -hex 32)
#       DOMAIN=your.domain.com
#       ADMIN_EMAIL, ADMIN_PASSWORD

# 4. Launch full stack (API + Caddy with auto-HTTPS)
docker compose up -d --build

# Caddy automatically provisions a Let's Encrypt cert for your domain.
# First startup takes ~30s for TLS provisioning.

# 5. Verify
curl https://your.domain.com/health
# → {"status": "ok"}

# 6. Start prediction backend on host (or in a screen/tmux session)
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "CREX_URL" \
  --model-dir models/t20_male_v2 \
  --feature-store-dir data/t20_male_feature_store_v2 \
  --league bbl \
  --output-json data/live_state.json
```

---

## Project Structure (New Code)

```
dashboard/                          ← new top-level package (this feature)
  app/
    main.py                         ← FastAPI app, mounts routers + static
    routers/
      auth.py                       ← POST /auth/login, /auth/refresh, /auth/logout
      live.py                       ← GET /api/live-state
      pages.py                      ← GET / (Jinja2 dashboard shell), GET /login
    models.py                       ← SQLModel User + RefreshToken
    database.py                     ← SQLite engine, session factory, WAL setup
    auth.py                         ← JWT encode/decode, password hashing, token store
    config.py                       ← Settings from env vars (pydantic-settings)
  templates/
    base.html                       ← Dark theme layout, Alpine.js init, Chart.js
    dashboard.html                  ← Live match view (score, gauges, chart)
    login.html                      ← Email + password form
  static/
    css/
      input.css                     ← Tailwind source (directives only)
      app.css                       ← Tailwind CLI output (generated, gitignored)
    js/
      alpine.min.js                 ← Alpine.js 3.14 (vendored)
      chart.umd.min.js              ← Chart.js 4.4.7 (vendored)
      dashboard.js                  ← Polling loop, chart update, silent token refresh
  Dockerfile
  requirements.txt
  tailwind.config.js
  package.json                      ← devDependency: tailwindcss CLI only
  .env.example

docker-compose.yml                  ← Production: api + caddy services
docker-compose.dev.yml              ← Local dev: api only, port 8000
Caddyfile                           ← 8-line reverse proxy + auto-HTTPS config

tests/
  dashboard/
    test_auth.py                    ← Unit: login, refresh, logout, rate limit
    test_live.py                    ← Unit: /api/live-state auth, stale detection
    test_models.py                  ← Unit: User, RefreshToken schema validation
```

---

## Key Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `JWT_SECRET` | ✅ | — | HS256 signing key. Generate: `openssl rand -hex 32` |
| `DOMAIN` | Production only | `localhost` | Your VPS domain (used by Caddy) |
| `ADMIN_EMAIL` | ✅ | — | Seeds the first user on startup |
| `ADMIN_PASSWORD` | ✅ | — | Seeds the first user on startup |
| `POLL_INTERVAL_MS` | No | `3000` | Browser poll interval in milliseconds |
| `STATE_FILE` | No | `data/live_state.json` | Path to prediction backend output |
| `DATABASE_URL` | No | `sqlite:///./auth.db` | SQLite DB path |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `60` | JWT access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | `30` | Refresh token lifetime |

---

## Adding a New Subscriber

Currently manual (no self-registration UI in scope):

```bash
# POST to the API with admin credentials to create a user
# (Owner uses the admin account to create subscriber accounts)
curl -X POST https://your.domain.com/auth/users \
  -H "Authorization: Bearer <admin_access_token>" \
  -H "Content-Type: application/json" \
  -d '{"email": "subscriber@example.com", "password": "SecurePass123!"}'
```

---

## Stopping / Updating

```bash
# Stop stack
docker compose down

# Update code + rebuild
git pull
docker compose up -d --build
```
