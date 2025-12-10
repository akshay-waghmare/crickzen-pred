# File Reorganization Plan - 004-scraper-resilience

## Current Issues
1. Resilience modules scattered between `crex_scraper_python/` root and `crex_scraper_python/src/`
2. Duplicate `config.py` files
3. Imports inconsistent (some use `crex_scraper_python.X`, others use `src.X`)

## Target Structure

```
apps/scraper/crex_scraper_python/
├── src/
│   ├── core/                    # NEW: Core resilience modules
│   │   ├── __init__.py
│   │   ├── circuit_breaker.py   # MOVE from crex_scraper_python/
│   │   ├── retry_utils.py       # MOVE from crex_scraper_python/
│   │   ├── scraper_context.py   # MOVE from crex_scraper_python/
│   │   ├── scraper_state.py     # MOVE from crex_scraper_python/
│   │   └── cleanup_orphans.py   # MOVE from crex_scraper_python/
│   ├── persistence/
│   │   ├── __init__.py
│   │   ├── db_pool.py           # MOVE from crex_scraper_python/
│   │   └── batch_writer.py      # EXISTS
│   ├── monitoring/
│   │   ├── __init__.py
│   │   ├── monitoring.py        # MOVE from crex_scraper_python/
│   │   └── metrics.py           # If needed later
│   ├── logging/
│   │   ├── __init__.py
│   │   ├── adapters.py          # EXISTS
│   │   └── diagnostics.py       # EXISTS
│   ├── config.py                # EXISTS - keep this one
│   ├── crex_main_url.py         # EXISTS
│   ├── crex_scraper.py          # EXISTS
│   ├── cricket_data_service.py  # EXISTS
│   ├── shared.py                # EXISTS
│   └── __init__.py
├── tests/
│   ├── unit/
│   │   ├── test_circuit_breaker.py      # EXISTS
│   │   ├── test_scraper_state.py        # EXISTS
│   │   ├── test_scraper_context.py      # EXISTS
│   │   ├── test_cleanup_orphans.py      # EXISTS
│   │   └── ...
│   └── integration/
│       ├── test_us1_integration.py      # EXISTS
│       └── ...
├── monitoring/                  # Config files only
│   ├── prometheus.yml           # EXISTS
│   └── prometheus.rules.yml     # EXISTS
├── run_server.py                # EXISTS
├── requirements.txt             # EXISTS
└── ...

## Files to DELETE (duplicates at root)
- crex_scraper_python/config.py (keep src/config.py)
- crex_scraper_python/monitoring/ directory (if empty after move)

## Import Changes Needed

### Before:
```python
from crex_scraper_python.circuit_breaker import CircuitBreaker
from crex_scraper_python.scraper_context import ScraperContext
```

### After:
```python
from src.core.circuit_breaker import CircuitBreaker
from src.core.scraper_context import ScraperContext
from src.persistence.db_pool import get_connection
from src.monitoring.monitoring import start_metrics_server
```

## Migration Steps
1. Create new subdirectories under src/
2. Move files to proper locations
3. Update all import statements
4. Delete duplicate/empty directories
5. Run all tests to verify

## Files to Update Imports In:
- src/cricket_data_service.py (uses circuit_breaker)
- src/crex_main_url.py (uses scraper_context, monitoring)
- src/crex_scraper.py (may use circuit_breaker, retry_utils)
- tests/unit/*.py (all test files)
- tests/integration/*.py (all integration tests)
