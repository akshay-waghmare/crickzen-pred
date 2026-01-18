# Data Model: Unified T20 Pipeline

## 1. Entities

### Match
Represents a single T20 match.
- **Source**: Cricsheet JSON
- **Storage**: Parquet (Ingestion layer)
- **Key Fields**:
  - `match_id` (string): Unique Cricsheet ID
  - `date` (date): Match date
  - `venue` (string): Venue name (raw)
  - `team1` (string): Team 1 name (raw)
  - `team2` (string): Team 2 name (raw)
  - `winner` (string): Winner name
  - `league` (string): League slug (e.g., 'bbl', 'ipl') **[NEW]**
  - `gender` (string): 'male' or 'female' **[NEW]**

### TrainingSample (Feature Layer)
Represents a single ball/state for model training.
- **Storage**: Parquet (Feature layer)
- **Key Features**:
  - `balls_remaining`: 120 down to 0
  - `runs_required`: Target - current score
  - `wickets_lost`: 0-10
  - `run_rate`: Current run rate
  - `req_run_rate`: Required run rate
  - `resource_win_prob`: Duckworth-Lewis resource-based baseline
  - `league_avg_run_rate`: League-specific baseline **[NEW]**

## 2. Directory Structure

```
data/
├── t20_male_json/          # Raw JSONs
│   ├── bbl/
│   ├── ipl/
│   └── ...
├── t20_female_json/        # Raw JSONs
├── t20_male_raw/           # Ingested Parquet (Unified)
├── t20_female_raw/         # Ingested Parquet (Unified)
├── t20_male_features_v1/   # Training Features
└── t20_female_features_v1/ # Training Features
```

## 3. Schema Changes

### `matches.parquet`
| Column | Type | Description |
|--------|------|-------------|
| match_id | string | PK |
| league | string | e.g., 'ipl' |
| gender | string | 'male', 'female' |
| ... | ... | Existing match columns |

### `feature_store/team_stats.parquet`
| Column | Type | Description |
|--------|------|-------------|
| team_id | string | Unified Team ID |
| matches | int | Total matches |
| win_rate | float | Overall win rate |
| league_primary | string | Most frequent league |

