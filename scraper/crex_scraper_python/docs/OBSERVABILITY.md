# Observability Quick Reference

## Structured Logging

The scraper now emits JSON logs with correlation IDs for end-to-end tracing.

### Environment Variables

```bash
# Logging configuration
SCRAPER_LOG_FORMAT=json                    # Output format (default: json)
SCRAPER_DEBUG_MODE=False                   # Enable debug artifacts (default: False)
SCRAPER_ARTIFACT_ROOT=artifacts           # Artifact storage directory
SCRAPER_ARTIFACT_RETENTION_DAYS=14        # Artifact retention period
```

### Log Schema

Every log entry includes:
- `timestamp` - ISO8601 UTC timestamp
- `level` - Log severity (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `correlation_id` - Unique identifier per scraping job
- `component` - Source module (crex_main_url, crex_scraper, cricket_data_service)
- `event` - Event identifier (e.g., `navigation.start`, `dom.selector.missing`)
- `metadata` - Additional context (URLs, errors, timings, etc.)

### Key Events

**Navigation & DOM:**
- `navigation.start` / `navigation.complete` - Page loading
- `dom.check` / `dom.ready` - DOM validation
- `dom.selector.missing` - Missing selector with HTML snapshot captured

**Data Extraction:**
- `extraction.start` / `extraction.complete` - Data scraping with timings

**Performance:**
- All completion events include `duration_ms` and `stage_timings` metadata

**Errors:**
- `network.error` - Network failures
- `dom.change_error` - DOM structure changes
- `scrape.error` - General scraping errors

## Health Monitoring

Check scraper health via API:

```bash
curl http://localhost:5000/api/v1/scraper/health | jq
```

Response includes:
- Current status
- Active job count
- Per-job state (running/stopped)

## Diagnostic Artifacts

When DOM drift or errors occur, artifacts are captured in `artifacts/<correlation_id>/`:
- `page.html` - HTML snapshot at failure point
- `page.png` - Screenshot (when debug mode enabled)
- `state.json` - Scraper state dump

### Artifact Cleanup

Run retention cleanup manually:

```bash
python src/cleanup_artifacts.py
```

Or schedule via cron:

```bash
# Daily cleanup at 2 AM
0 2 * * * cd /path/to/project && python src/cleanup_artifacts.py
```

## Querying Logs

### Find DOM drift issues:
```bash
grep "dom.selector.missing" logs/*.log | jq
```

### Check performance metrics:
```bash
grep "extraction.complete" logs/*.log | jq '.metadata.total_duration_ms'
```

### Track correlation across events:
```bash
grep "correlation_id\":\"abc-123" logs/*.log | jq
```

## Troubleshooting

**No correlation IDs in logs:**
- Ensure `bind_correlation_id()` is called at job start
- Check that `configure_logging()` runs before first log

**Missing artifacts:**
- Verify `SCRAPER_ARTIFACT_ROOT` directory is writable
- Check retention settings haven't expired artifacts prematurely

**High artifact disk usage:**
- Reduce `SCRAPER_ARTIFACT_RETENTION_DAYS`
- Run cleanup script more frequently
- Enable artifact S3 sync (if configured)
