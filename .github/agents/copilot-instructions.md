````chatagent
# machine_learning Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-02-18

## Active Technologies
- Local Filesystem (Parquet, JSON/YAML) (001-bbl-data-pipeline)
- Python 3.10+ + scikit-learn, xgboost, pandas (002-bbl-model-training)
- Python 3.10+ (from pyproject.toml) + NumPy, Pandas, joblib, existing bbl_pipeline (004-monte-carlo-engine)
- N/A in-memory simulation, optional pickle caching (004-monte-carlo-engine)
- Python 3.11+ + pandas, pyarrow, numpy, scikit-learn, structlog, click, playwright (001-match-state-logging)
- Apache Parquet (snappy) at data/match_states/<league>/ (001-match-state-logging)
- Python 3.10+ (001-bbl-data-pipeline)
- Python 3.12 + FastAPI 0.115, uvicorn, PyJWT 2.11, pwdlib[argon2] 0.3, SQLModel 0.0.34, slowapi 0.1.9, Jinja2 3.1 (001-saas-prediction-dashboard)
- SQLite WAL mode — users + refresh_tokens tables (001-saas-prediction-dashboard)
- Alpine.js 3.14, Chart.js 4.4.7, Tailwind CSS 4 CLI (001-saas-prediction-dashboard)
- Docker Compose: api (python:3.12-slim) + caddy (caddy:2.9-alpine) (001-saas-prediction-dashboard)

## Project Structure

```text
src/            ← ML pipeline (bbl_pipeline package)
dashboard/      ← SaaS web dashboard (FastAPI app)
tests/
```

## Commands

cd src; pytest; ruff check .
docker compose -f docker-compose.dev.yml up --build   # dashboard dev
docker compose up --build -d                          # dashboard prod

## Code Style

Python 3.10+: Follow standard conventions. Python 3.12 for dashboard/.

## Recent Changes
- 001-saas-prediction-dashboard: Added FastAPI 0.115, PyJWT 2.11, pwdlib[argon2] 0.3, SQLModel 0.0.34, slowapi 0.1.9, SQLite WAL, Alpine.js 3.14, Chart.js 4.4.7, Tailwind CSS 4, Docker Compose + Caddy 2.9
- 001-match-state-logging: Added Python 3.11+ + pandas, pyarrow, numpy, scikit-learn, structlog, click, playwright
- 004-monte-carlo-engine: Added Python 3.10+ + NumPy, Pandas, joblib, existing bbl_pipeline


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->

````