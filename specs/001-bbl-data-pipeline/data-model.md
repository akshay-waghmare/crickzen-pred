# Data Model: BBL Data Pipeline

**Feature**: Initial Data Ingestion & Processing Pipeline
**Date**: 2025-12-09

## 1. Entity Registry (YAML/JSON)
**Purpose**: Canonical mapping for Players, Teams, and Venues.
**Format**: JSON/YAML
**Location**: `config/entity_registry.yaml`

### Schema
```yaml
players:
  <cricsheet_id>:
    name: "Canonical Name"
    other_names: ["Alias 1", "Alias 2"]
    teams: ["Team A", "Team B"]

teams:
  <cricsheet_id>:
    name: "Canonical Team Name"
    code: "BBL_TEAM_CODE"

venues:
  <cricsheet_id>:
    name: "Canonical Venue Name"
    city: "City Name"
```

## 2. Processed Match Data (Parquet)
**Purpose**: The primary dataset for ML training.
**Format**: Parquet (Partitioned by `season`)
**Compression**: `zstd`
**Metadata**:
*   `schema_version`: "1.0.0"
*   `source_files`: List of JSON files or hash
*   `ingestion_timestamp`: ISO8601

### Schema (Ball-by-Ball)

| Column Name | Type | Description | Constraints |
| :--- | :--- | :--- | :--- |
| `match_id` | `string` | Unique Cricsheet Match ID | Not Null |
| `season` | `string` | Season Year (e.g., "2023/24") | Partition Key |
| `date` | `date` | Match Date | Not Null |
| `venue_id` | `string` | Canonical Venue ID | FK to Registry |
| `batting_team_id` | `string` | Canonical Team ID | FK to Registry |
| `bowling_team_id` | `string` | Canonical Team ID | FK to Registry |
| `innings` | `int` | Innings Number (1 or 2) | 1 <= x <= 4 |
| `over` | `int` | Over Number (0-19) | 0 <= x <= 19 |
| `ball` | `int` | Ball Number within Over | 1 <= x <= 10 |
| `batter_id` | `string` | Canonical Batter ID | FK to Registry |
| `bowler_id` | `string` | Canonical Bowler ID | FK to Registry |
| `non_striker_id` | `string` | Canonical Non-Striker ID | FK to Registry |
| `runs_batter` | `int` | Runs off bat | >= 0 |
| `runs_extras` | `int` | Extra runs | >= 0 |
| `runs_total` | `int` | Total runs for the ball | >= 0 |
| `wicket_type` | `string` | Type of dismissal (if any) | Nullable |
| `player_out_id` | `string` | ID of player dismissed | Nullable |
| `is_super_over` | `bool` | Flag for Super Over | Default False |

## 3. Ingestion Summary Report
**Purpose**: Audit log of the ingestion process.
**Format**: JSON

### Schema
```json
{
  "timestamp": "ISO8601",
  "source_directory": "path/to/data",
  "files_processed": 100,
  "files_skipped": 5,
  "files_error": 0,
  "matches_ingested": 95,
  "processing_time_seconds": 45.2,
  "errors": [
    {
      "file": "bad_match.json",
      "error": "SchemaValidationError: Missing 'toss' field"
    }
  ],
  "schema_version": "1.0.0"
}
```
