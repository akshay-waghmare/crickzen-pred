# Scraper Architecture

## File Organization

The scraper consists of TWO distinct components with clear separation of concerns:

### 1. URL Discovery Scraper
**Location**: `crex_scraper_python/src/crex_scraper.py` (294 lines)  
**Purpose**: Discovers live match URLs from the main cricket website  
**Function**: `scrape(url)` / `fetchData(url)` (alias)  
**Returns**: List of live match URLs  
**Does NOT**: Handle match data, localStorage, or ball-by-ball updates

### 2. Match Data Scraper  
**Location**: `crex_match_data_scraper.py` (1376 lines)  
**Purpose**: Scrapes detailed ball-by-ball match data using Playwright  
**Function**: `fetchData(url, context)`  
**Handles**: 
- Browser automation with Playwright
- localStorage extraction for player/team data
- Ball-by-ball score updates via API interception
- Data transformation and backend submission

## Import Structure

```python
# In crex_scraper_python/src/crex_main_url.py:
from src.crex_scraper import scrape  # URL discovery (NEW)
from crex_match_data_scraper import fetchData  # Match data scraping (OLD but ACTIVE)
```

## Why Two Files with Similar Names?

**Historical Context**: 
- `crex_match_data_scraper.py` was originally named `crex_scraper.py`
- When the codebase was reorganized, a NEW `src/crex_scraper.py` was created for URL discovery
- Both files coexisted with the same name causing confusion
- **Solution**: Renamed the match data scraper to `crex_match_data_scraper.py` for clarity

## Data Flow

```
1. crex_main_url.py (Flask app)
   ↓
2. src/crex_scraper.scrape() 
   → Discovers live match URLs
   ↓
3. crex_match_data_scraper.fetchData()
   → Opens Playwright browser
   → Extracts localStorage (player names, team data)
   → Intercepts sC4 API for ball-by-ball data
   → Sends data to backend
```

## Key Modules

| Module | Purpose | Technology |
|--------|---------|------------|
| `crex_main_url.py` | Flask API, orchestration | Flask, threading |
| `crex_info_url.py` | Match info scraping | Playwright |
| `crex_match_data_scraper.py` | Ball-by-ball data | Playwright, API interception |
| `src/crex_scraper.py` | URL discovery | Playwright, structured logging |
| `cricket_data_service.py` | Backend API client | Requests, JWT auth |

## Known Issues

### Scorecard Incomplete Data (Active Investigation)
**Branch**: `investigate-scorecard-incomplete-data`  
**Issue**: Player names showing as codes instead of names (e.g., "D7O" instead of "Player Name")  
**Root Cause**: localStorage only contains 6/22 player codes when sC4 data is decoded  
**Fix Location**: Needs to be applied to `crex_match_data_scraper.py` (the match data scraper)  
**Documentation**: `openspec/changes/investigate-scorecard-incomplete-data/`

## Development Notes

- The `crex_scraper_python/` package uses modern Python patterns (context managers, dataclasses)
- The root-level `crex_match_data_scraper.py` uses older patterns but is critical for data extraction
- Both are actively used and maintained
- Future work: Migrate match data scraping to the modern architecture

## Docker Build

The Dockerfile explicitly copies specific files to avoid confusion:
```dockerfile
COPY crex_match_data_scraper.py crex_info_url.py ... ./
COPY crex_scraper_python/ ./
```

This ensures:
- `/app/crex_match_data_scraper.py` (match data scraper)
- `/app/src/crex_scraper.py` (URL discovery)
- No naming conflicts or ambiguity
