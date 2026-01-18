# Research: Unified T20 Models

**Status**: Complete
**Date**: 2026-01-18

## 1. Data Ingestion Strategy

### Problem
The current `src/bbl_pipeline/ingestion/loader.py` uses `directory.glob("*.json")`, which scans only the top-level directory. The new requirement involves organizing data into `data/t20_male_json/{league}/` subfolders.

### Decision
Update `loader.iter_match_files` to use `directory.rglob("*.json")` (recursive glob). This allows for flexible directory structures (flat or nested) without breaking existing functionality.

### Alternatives Considered
- **Looping in CLI**: Have the CLI iterate through subdirectories and call the loader for each. 
  - *Cons*: Adds complexity to the CLI command code.
- **Flat directory**: Dump all 2000+ files into a single directory. 
  - *Cons*: Hard to manage, verify, or debug specific leagues.

## 2. Entity Resolution & Schema

### Problem
We are introducing 11+ new leagues with potentially hundreds of new team names and venues. The current `EntityResolver` relies on a pre-populated registry.

### Decision
- **Auto-Discovery**: During the "Process" phase, the pipeline should log unknown teams/venues rather than failing hard, or auto-assign a temporary ID.
- **Unified Registry**: Maintain a single `registry.json` (or split by type) that covers all leagues, rather than separate registries per league.
- **Schema Update**: Add `league` and `gender` columns to the main matches Parquet schema to allow for filtering and grouping in the unified model.

## 3. Cricsheet URLs

### Problem
Constructing download URLs for 15+ leagues reliably.

### Decision
Use the standard Cricsheet pattern: `https://cricsheet.org/downloads/{slug}_json.zip`.
- **Validation**: The download script will verify the URL returns 200 OK before downloading.
- **Retry Logic**: Implement exponential backoff for network stability.

## 4. Model Architecture

### Decision
Stick with `XGBLogRegEnsemble`.
- **Scalability**: XGBoost handles the increased row count (~500k-1M rows) easily.
- **Calibration**: The `brier_optimized` (per-over) strategy might be too granular if some leagues have sparse data. We will use the unified dataset for calibration but may fallback to "Innings x Phase" if per-over is too noisy for smaller leagues.

