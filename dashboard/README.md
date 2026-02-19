# CrickenZen Prediction Dashboard

A SaaS web dashboard for real-time T20 cricket win-probability predictions.  
Subscribers get live ball-by-ball updates powered by the `XGBLogRegEnsemble` model.

---

## Quick Start (Local Dev)

### 1 — Install Python dependencies
```bash
cd dashboard
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

> **Important:** pin scikit-learn to 1.7.2 to avoid pickle-compatibility errors with existing models:
> ```bash
> dashboard/.venv/bin/pip install scikit-learn==1.7.2
> ```

### 2 — Install JS dependencies & build CSS
```bash
npm install
npm run build:css    # produces static/css/app.css
```

### 3 — Create `.env`
```bash
cp .env.example .env   # then edit values
```

Minimum required:
```
JWT_SECRET=<random 32+ chars>
ADMIN_EMAIL=admin@crickenzen.com
ADMIN_PASSWORD=<strong password>
STATE_FILE=../data/live_state.json
```

### 4 — Start the server
```bash
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Open <http://localhost:8000> in a browser.

---

## Running a Live Match

The dashboard reads from `data/live_state.json`.  Start the predictor in a separate terminal, and the dashboard will update automatically every 5 seconds.

### Global model (recommended) — any T20 league
```bash
.venv/bin/python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "https://crex.live/scoreboard/<match-slug>" \
  --model-dir models/t20_male_v2 \
  --feature-store-dir data/bbl_feature_store_v2 \
  --league <league>          \  # bbl | sa20 | ilt20 | ssm | wpl | t20i …
  --output-json data/live_state.json \
  --record-states
```

### League-specific examples
| League | `--league` | `--feature-store-dir` |
|--------|-----------|----------------------|
| Big Bash (BBL) | `bbl` | `data/bbl_feature_store_v2` |
| SA20 | `sa20` | `data/bbl_feature_store_v2` |
| ILT20 | `ilt20` | `data/bbl_feature_store_v2` |
| T20 International | `t20i` | `data/bbl_feature_store_v2` |
| NTQ / SSM | `ssm` | `data/bbl_feature_store_v2` |
| WPL | `wpl` | `data/bbl_feature_store_v2` |

---

## Authentication & Subscriber Management

Default admin account (set in `.env`):
- **Email:** `admin@crickenzen.com`
- **Password:** `CrickenZen2026!` (change before going live!)

### API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/login` | Get JWT token |
| `GET`  | `/auth/me` | Current user profile |
| `POST` | `/admin/subscribers` | Add subscriber |
| `GET`  | `/admin/subscribers` | List subscribers |
| `PATCH`| `/admin/subscribers/{id}/suspend` | Suspend account |
| `PATCH`| `/admin/subscribers/{id}/reactivate` | Reactivate account |
| `GET`  | `/health` | Health check |

### Add a subscriber (curl)
```bash
curl -s -X POST http://localhost:8000/admin/subscribers \
  -H "Authorization: Bearer <ADMIN_JWT>" \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"Pass1234!","plan":"monthly"}'
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JWT_SECRET` | ✅ | — | Secret key for signing JWTs |
| `ADMIN_EMAIL` | ✅ | — | Bootstrap admin e-mail |
| `ADMIN_PASSWORD` | ✅ | — | Bootstrap admin password |
| `STATE_FILE` | ✅ | `../data/live_state.json` | Path to predictor output |
| `DATABASE_URL` | ❌ | `sqlite:///./auth.db` | SQLAlchemy connection string |
| `JWT_EXPIRE_MINUTES` | ❌ | `60` | Token lifetime in minutes |
| `RATE_LIMIT_PER_MINUTE` | ❌ | `60` | Requests / minute per IP |
| `CORS_ORIGINS` | ❌ | `*` | Comma-separated allowed origins |
| `PORT` | ❌ | `8000` | Uvicorn listen port |

---

## Project Structure

```
dashboard/
├── app/
│   ├── main.py              # FastAPI app factory + module-level app = create_app()
│   ├── auth/                # JWT auth, user model, login endpoints
│   ├── admin/               # Subscriber CRUD (admin-only)
│   ├── prediction/          # Live state reader + SSE/polling endpoint
│   └── middleware/          # Rate limiter, CORS, request logging
├── static/
│   ├── css/app.css          # Built by Tailwind (do not edit directly)
│   └── js/                  # Alpine.js + htmx bundles
├── templates/               # Jinja2 HTML templates
├── tests/                   # pytest suite (32 tests)
├── .env                     # Local secrets (gitignored)
├── .env.example             # Template for new devs
├── package.json             # Tailwind / npm config
├── tailwind.config.js       # Tailwind v3 config
└── requirements.txt         # Python deps
```

---

## Running Tests

```bash
cd dashboard
.venv/bin/pytest tests/ -v
```

All 32 tests should pass. If you see sklearn errors, re-pin:
```bash
.venv/bin/pip install scikit-learn==1.7.2
```

---

## Production Deploy

See [`docs/DASHBOARD_DEPLOY.md`](../docs/DASHBOARD_DEPLOY.md) for full server + Docker + HTTPS (Caddy) setup.
