# Cricket Scraper Project (Async)

## Overview
High-reliability asynchronous scraper for live cricket match data. Built with Python, Playwright (Async), Redis, and Flask. Designed for continuous freshness, graceful degradation under load, and self-recovery.

## Features
- **Async Architecture**: Uses `asyncio` and `playwright` for high-concurrency scraping.
- **Freshness Guarantee**: Tracks data age (p50/p90/p99) and prioritizes live matches.
- **Resilience**:
  - **Rate Limiting**: Token bucket algorithm to respect upstream limits.
  - **Circuit Breaking**: Automatically pauses failing domains.
  - **Self-Recovery**: Detects stalls and recycles browser processes automatically.
- **Caching**: Redis-based snapshot caching with delta computation.
- **Observability**: Prometheus metrics (`/metrics`) and health status (`/status`).

## Installation
1. Clone the repository:
   ```bash
   git clone ...
   cd apps/scraper/crex_scraper_python
   ```

2. Set up a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

4. Configure environment:
   Copy `.env.example` to `.env` and set `REDIS_URL`.

## Usage

### Run Locally
```bash
python -m src.app
```

### Run with Docker
```bash
docker-compose up --build scraper
```

## API Endpoints
- **GET /status**: Service health, metrics, and state.
- **GET /metrics**: Prometheus metrics.
- **POST /submit-task**: Enqueue a URL for scraping.

## Monitoring
See `MONITORING_GUIDE.md` for Grafana dashboards and alert rules.

## License
MIT
