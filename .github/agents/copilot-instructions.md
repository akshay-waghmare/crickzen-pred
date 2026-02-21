# machine_learning Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-12-09

## Active Technologies
- Local Filesystem (Parquet, JSON/YAML) (001-bbl-data-pipeline)
- [e.g., Python 3.11, Swift 5.9, Rust 1.75 or NEEDS CLARIFICATION] + [e.g., FastAPI, UIKit, LLVM or NEEDS CLARIFICATION] (002-bbl-model-training)
- [if applicable, e.g., PostgreSQL, CoreData, files or N/A] (002-bbl-model-training)
- Python 3.10+ + scikit-learn, xgboost, pandas, (002-bbl-model-training)
- Python 3.10+ (from pyproject.toml) + NumPy (vectorization), Pandas (data), joblib (serialization), existing bbl_pipeline (004-monte-carlo-engine)
- N/A (in-memory simulation, optional pickle caching) (004-monte-carlo-engine)
- Python 3.11+ + pandas, pyarrow, numpy, scikit-learn (brier_score_loss), structlog, click (CLI), playwright (CREX scraping — existing) (001-match-state-logging)
- Apache Parquet (snappy compression) at `data/match_states/<league>/` (001-match-state-logging)

- Python 3.10+ (001-bbl-data-pipeline)

## Project Structure

```text
src/
tests/
```

## Commands

cd src; pytest; ruff check .

## Code Style

Python 3.10+: Follow standard conventions

## Recent Changes
- 007-odi-female-model: Added [e.g., Python 3.11, Swift 5.9, Rust 1.75 or NEEDS CLARIFICATION] + [e.g., FastAPI, UIKit, LLVM or NEEDS CLARIFICATION]
- 001-match-state-logging: Added Python 3.11+ + pandas, pyarrow, numpy, scikit-learn (brier_score_loss), structlog, click (CLI), playwright (CREX scraping — existing)
- 001-match-state-logging: Added [e.g., Python 3.11, Swift 5.9, Rust 1.75 or NEEDS CLARIFICATION] + [e.g., FastAPI, UIKit, LLVM or NEEDS CLARIFICATION]


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
