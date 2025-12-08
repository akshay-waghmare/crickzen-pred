# Quickstart: BBL Data Pipeline

## Prerequisites
*   Python 3.10+
*   `pip` or `uv`

## Installation

1.  Clone the repository:
    ```bash
    git clone <repo-url>
    cd ml_predictions
    ```

2.  Install dependencies:
    ```bash
    pip install -e .
    ```

## Usage

### 1. Ingest Data
Process the raw Cricsheet JSON files into a Parquet dataset.

```bash
bbl-pipeline ingest \
  --input-dir ./big_bash_model/bbl_male_json_dataset \
  --output-dir ./data/processed/bbl \
  --incremental
```

### 2. Update Entity Registry
Scan for new players or teams and update the registry.

```bash
bbl-pipeline resolve \
  --input-dir ./big_bash_model/bbl_male_json_dataset
```

### 3. Validate Dataset
Verify the integrity of the processed data.

```bash
bbl-pipeline validate --data-dir ./data/processed/bbl
```

## Development

Run tests:
```bash
pytest tests/
```
