# Quickstart: Scraper Logging Recovery

## Prerequisites
- Python 3.10 environment with dependencies from `requirements.txt`
- Playwright browsers installed (`playwright install chromium`)
- Writable `artifacts/` directory for diagnostic captures
- Access to log aggregation sink (stdout collector or Fluent Bit)

## 1. Enable Structured Logging
1. Set environment variable `SCRAPER_LOG_FORMAT=json` (defaults to JSON when absent).
2. Optionally configure log file rotation via `.env`:
   ```env
   SCRAPER_LOG_DIR=logs
   SCRAPER_LOG_ROTATION_MB=250
   SCRAPER_LOG_BACKUPS=7
   ```
3. Launch the scraper:
   ```bash
   python -m src.crex_scraper --job ipl_ingest
   ```
4. Verify logs emit JSON objects with keys `timestamp`, `level`, `correlation_id`, `component`, `event`, `metadata`.

## 2. Capture Diagnostics in Debug Mode
1. Toggle debug mode for incident replication:
   ```env
   SCRAPER_DEBUG_MODE=1
   SCRAPER_ARTIFACT_RETENTION_DAYS=14
   ```
2. Re-run the failing scrape. Inspect generated artifacts under `artifacts/<correlation_id>/`:
   - `page.html` – sanitized DOM snapshot
   - `page.png` – screenshot captured before failure
   - `state.json` – serialized scraper state machine
3. Upload artifacts to S3 by setting `SCRAPER_ARTIFACT_S3_BUCKET` (optional); sync occurs post-run.

## 3. Query Health & Logs
1. Start the Flask API (if not already running):
   ```bash
   python -m src.cricket_data_service
   ```
2. Retrieve job health:
   ```bash
   curl http://localhost:5000/api/v1/scraper/jobs/ipl_ingest/health | jq
   ```
3. Inspect recent log events:
   ```bash
   curl "http://localhost:5000/api/v1/scraper/runs/<correlation_id>/logs?level=ERROR" | jq
   ```
4. Enumerate diagnostic artifacts:
   ```bash
   curl http://localhost:5000/api/v1/scraper/runs/<correlation_id>/artifacts | jq
   ```

## 4. Testing Checklist
- Run unit tests: `pytest tests/unit/test_logging_adapters.py`
- Run integration flow: `pytest tests/integration/test_scraper_logging_flow.py`
- Confirm log redaction by asserting absence of `token=` substrings in captured logs
- Validate retention cleanup with `python -m src.logging.diagnostics --prune`
