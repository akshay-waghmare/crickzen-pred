# Research & Technical Decisions: BBL Data Pipeline

**Feature**: Initial Data Ingestion & Processing Pipeline
**Date**: 2025-12-09
**Status**: Approved

## 1. Fuzzy Matching Library
**Decision**: **`rapidfuzz`**
**Rationale**:
*   **Performance**: Significantly faster than `thefuzz` (formerly `fuzzywuzzy`) due to C++ backing, which is critical when processing thousands of player names.
*   **License**: MIT license is more permissive than `thefuzz`'s GPL.
*   **Accuracy**: Fixes known algorithmic bugs in `thefuzz`.
**Alternatives Considered**:
*   `thefuzz`: Slower, restrictive license.
*   `difflib` (Stdlib): Too basic, lacks sophisticated scoring metrics (e.g., token sort ratio).

## 2. Data Validation Framework
**Decision**: **`pandera`**
**Rationale**:
*   **Vectorized Validation**: Designed specifically for Pandas DataFrames, allowing efficient column-level checks without slow row-iteration.
*   **Statistical Checks**: Supports checks like `Check(lambda x: x >= 0)` which are essential for cricket stats (runs, wickets).
*   **Integration**: Can infer schemas from existing DataFrames and export to various formats.
**Alternatives Considered**:
*   `pydantic`: Excellent for object validation but too slow for large DataFrames (row-wise iteration).
*   `cerberus`: Dictionary-based, less type-safe than class-based schemas.

## 3. Storage Format & Partitioning
**Decision**: **Parquet (partitioned by `season`) with `zstd` compression**
**Rationale**:
*   **Performance**: Columnar storage is ideal for analytical queries (e.g., "average runs per over").
*   **Partitioning**: Partitioning by `season` aligns with common query patterns ("get stats for 2023") and simplifies incremental updates (rewrite only the current season's folder).
*   **Compression**: `zstd` offers a better balance of compression ratio and speed compared to `snappy`.
**Alternatives Considered**:
*   `CSV`: No schema enforcement, slow to read/write, no compression.
*   `SQLite`: Good for relational queries but harder to integrate into a distributed/cloud-native ML pipeline later.

## 4. Project Structure
**Decision**: **`src` Layout**
**Rationale**:
*   **Standardization**: Modern Python best practice.
*   **Isolation**: Prevents "import parity" issues where local files mask installed packages.
*   **Testing**: Ensures tests run against the installed version of the package.
**Structure**:
```text
src/
└── bbl_pipeline/
    ├── __init__.py
    ├── cli.py
    ├── ingestion/
    ├── processing/
    └── validation/
```
