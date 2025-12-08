# BBL Data Pipeline

A modular data ingestion and processing pipeline for Big Bash League (BBL) cricket data.

## Features

- **Ingestion**: Parse Cricsheet JSON files and convert to Parquet.
- **Processing**: Flatten ball-by-ball data, separate Super Overs.
- **Entity Resolution**: Normalize player, team, and venue names using fuzzy matching and a canonical registry.
- **Validation**: Enforce strict schemas using Pandera.
- **CLI**: Unified command-line interface for all operations.

## Installation

```bash
pip install -e .
```

## Usage

### Ingest Data

```bash
bbl-pipeline ingest --input-dir /path/to/json --output-dir /path/to/output
```

### Resolve Entities

```bash
bbl-pipeline resolve --input-dir /path/to/json
```

### Validate Data

```bash
bbl-pipeline validate --data-dir /path/to/output
```

## Configuration

Configuration is loaded from `config/config.yaml` or passed via `--config`.

## Development

Run tests:

```bash
pytest
```
