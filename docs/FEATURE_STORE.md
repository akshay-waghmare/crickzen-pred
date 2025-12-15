# Feature Store Documentation

## Active Models & Feature Stores

### BBL v8 (Big Bash League)
- **Model Path**: `models/bbl_v8`
- **Feature Store**: `data/bbl_feature_store_v2/`
- **Architecture**: XGBLogRegEnsemble (50% XGBoost + 50% Logistic Regression)
- **Calibration**: CV-OOF Isotonic Regression
- **Performance**: Brier Score = 0.1809, ECE = 0.0000

### ILT20 v4 (International League T20)
- **Model Path**: `models/ilt20_v4`
- **Feature Store**: `data/ilt_feature_store_v3/`
- **Architecture**: XGBLogRegEnsemble (50% XGBoost + 50% Logistic Regression)
- **Calibration**: CV-OOF Isotonic Regression
- **Performance**: Brier Score = 0.0714, ECE = 0.0000

---

## BBL v8 Feature Store Schema

### Location: `data/bbl_feature_store_v2/`

#### 1. `team_ratings.parquet`
**Purpose**: Historical team performance metrics by situation

**Schema**:
| Column | Type | Description |
|--------|------|-------------|
| team | string | BBL team name (8 teams total) |
| win_rate | float | Overall win rate across all matches |
| matches | int | Total matches played |
| bat_first_wr | float | Win rate when batting first (offensive) |
| bowl_first_wr | float | Win rate when bowling first (defensive) |

**Example Data** (Melbourne Renegades):
```
team: Melbourne Renegades
win_rate: 0.4082 (41 wins in 147 matches)
matches: 147
bat_first_wr: 0.3433 (batting first is weaker for them)
bowl_first_wr: 0.4625 (defending is their strength)
```

**Usage in Inference**:
- **Innings 1**: Uses `bat_first_wr` (team batting first in match)
- **Innings 2**: Uses `bowl_first_wr` (team defending a score)
- **Feature**: `situation_advantage = batting_team.bowl_first_wr - bowling_team.bat_first_wr` (Innings 2)

---

#### 2. `player_stats.parquet`
**Purpose**: Aggregated rolling statistics for all players

**Schema** (indexed by player name):
| Column | Type | Description |
|--------|------|-------------|
| batsman_rolling_avg | float | Rolling average from recent innings |
| batsman_rolling_sr | float | Rolling strike rate (%) |
| bowler_rolling_econ | float | Rolling economy rate (runs/over) |
| bowler_rolling_sr | float | Rolling strike rate (balls/wicket) |

**Total Records**: 508 players (batsmen and bowlers combined)

**Usage in Inference**:
- Look up by player name (with fuzzy matching)
- Use as fallback when player-venue/player-vs-team stats unavailable
- Default: 25.0 for batting avg, 125.0 for SR, 7.5 for economy

---

#### 3. `venue_stats.parquet`
**Purpose**: Venue-specific historical performance

**Schema** (indexed by venue name):
| Column | Type | Description |
|--------|------|-------------|
| venue_avg_score | float | Average first-innings score at venue |
| venue_avg_wickets | float | Average wickets lost by batting team |
| venue_bat_first_win_rate | float | Historical win rate for teams batting first |

**Total Records**: 31 venues across BBL seasons

**Example** (MCG):
```
venue_avg_score: 167.96
venue_avg_wickets: 12.29
venue_bat_first_win_rate: 0.5789 (teams batting first win 57.9% at MCG)
```

**Usage in Inference**:
- Score vs Par calculation (compare projected score against venue average)
- Venue advantage assessment
- Resource calculator calibration

---

## ILT20 v4 Feature Store Schema

### Location: `data/ilt_feature_store_v3/`

**Identical structure to BBL v8**:
- `team_ratings.parquet` (6 ILT20 teams)
- `player_stats.parquet` (international T20 players)
- `venue_stats.parquet` (UAE venues: Dubai, Abu Dhabi, Sharjah)

---

## Advanced Feature Lookup Tables

The feature stores support advanced lookups through the `InMemoryFeatureStore` class:

### Player-Venue Lookups
- `get_player_venue_batting_stats(player, venue)` → avg, SR at specific venue
- `get_player_venue_bowling_stats(player, venue)` → economy, SR at specific venue

### Player-vs-Team Lookups
- `get_player_vs_team_batting_stats(player, opponent)` → avg against team
- `get_player_vs_team_bowling_stats(player, opponent)` → economy against team

**Matching Strategy** (in order):
1. Exact match
2. Case-insensitive match
3. Fuzzy match (80% similarity cutoff for venues, 60% for others)
4. Default fallback values

---

## Feature Store Generation Pipeline

### Command
```bash
bbl-pipeline process \
  --input-dir data/bbl_raw/matches \
  --output-dir data/bbl_features_v2 \
  --feature-store-dir data/bbl_feature_store_v2
```

### Process
1. **Ingestion**: Convert Cricsheet JSON → Parquet (ball-by-ball data)
2. **Processing**: Calculate rolling stats for all players, teams, venues
3. **Feature Store**: Save aggregated stats for fast inference lookup
4. **Training Data**: Generate feature vectors for model training

### Runtime
- ~60 seconds for full BBL pipeline (141K+ ball records)
- Feature store fits in memory (~5MB)
- Inference lookup: <1ms per player/venue/team

---

## Venue Alias Mapping

The feature store uses fuzzy matching with a predefined alias map for venue resolution:

**Key Mappings**:
- `Simonds Stadium` → `Simonds Stadium, South Geelong, Victoria`
- `GMHBA Stadium` → `GMHBA Stadium, South Geelong, Victoria`
- `MCG` → `Melbourne Cricket Ground`
- `SCG` → `Sydney Cricket Ground`
- `The Gabba` → `Brisbane Cricket Ground`

**Rationale**: Live scrapers often use abbreviated or alternate venue names; aliases ensure consistent feature store lookups.

---

## Top 25 Features Used by Model

The BBL v8 and ILT20 v4 models use these 25 features:

| Rank | Feature | Source | Type |
|------|---------|--------|------|
| 1 | expected_final_score | Resource Calculator | Derived |
| 2 | resource_win_prob | Resource Calculator | Derived |
| 3 | score_vs_par | Feature Mapper | Derived |
| 4 | dls_pressure_index | Resource Calculator | Derived |
| 5 | projected_vs_venue_avg | Feature Mapper | Derived |
| 6 | projected_score | Feature Mapper | Derived |
| 7 | is_powerplay | Scraper | Categorical |
| 8 | score_per_wicket | Feature Mapper | Derived |
| 9 | run_rate_diff | Feature Mapper | Derived |
| 10 | required_run_rate | Scraper | Derived |
| 11 | chase_difficulty | Feature Mapper | Derived |
| 12 | wickets_times_balls | Feature Mapper | Derived |
| 13 | pressure_index | Feature Mapper | Derived |
| 14 | team_strength_diff | Feature Store (team_ratings) | Direct |
| 15 | rrr_times_wickets | Feature Mapper | Derived |
| 16 | overs_remaining | Feature Mapper | Derived |
| 17 | batting_team_win_rate | Feature Store (team_ratings) | Direct |
| 18 | bowling_team_win_rate | Feature Store (team_ratings) | Direct |
| 19 | batting_team_situation_wr | Feature Store (team_ratings) | Direct |
| 20 | situation_advantage | Feature Store (team_ratings) | Derived |
| 21 | boundary_pct_last_18 | Ball History | Derived |
| 22 | bowling_team_situation_wr | Feature Store (team_ratings) | Direct |
| 23 | runs_last_12 | Ball History | Derived |
| 24 | runs_last_18 | Ball History | Derived |
| 25 | wickets_last_12 | Ball History | Derived |

---

## Key Improvements (Latest Update - Dec 15, 2025)

### Situation-Specific Win Rates
Added `bat_first_wr` and `bowl_first_wr` to enable context-aware predictions:
- Teams often perform differently when batting first vs defending
- Perth Scorchers excel at batting first (0.6000) vs bowl first (0.6400)
- Melbourne Renegades stronger defending (0.4625) vs batting first (0.3433)

### Enhanced Venue Resolution
- Fixed venue alias mapping to use canonical feature store names
- Increased fuzzy match cutoff to 80% for stricter matching
- Handles scrapers that return abbreviated or alternate venue names

---

## Testing Feature Store Integrity

```bash
# Verify team ratings with new columns
python -c "
import pandas as pd
df = pd.read_parquet('data/bbl_feature_store_v2/team_ratings.parquet')
print(df[['team', 'win_rate', 'bat_first_wr', 'bowl_first_wr']])
"

# Check player coverage
python -c "
import pandas as pd
df = pd.read_parquet('data/bbl_feature_store_v2/player_stats.parquet')
print(f'Players: {len(df)}')
print(f'Batsmen: {(df[\"batsman_rolling_avg\"].notna()).sum()}')
print(f'Bowlers: {(df[\"bowler_rolling_econ\"].notna()).sum()}')
"

# Verify venues
python -c "
import pandas as pd
df = pd.read_parquet('data/bbl_feature_store_v2/venue_stats.parquet')
print(f'Venues: {len(df)}')
print(df.index.tolist())
"
```

---

## Regenerating Feature Stores

**When to regenerate**:
- After updating raw data (new season matches added)
- When team stats change significantly
- After modifying feature calculation logic

**Steps**:
```bash
# 1. Ingest latest raw data
bbl-pipeline ingest --input-dir data/raw_json/bbl --output-dir data/bbl_raw

# 2. Process and regenerate feature store
bbl-pipeline process \
  --input-dir data/bbl_raw/matches \
  --output-dir data/bbl_features_v2 \
  --feature-store-dir data/bbl_feature_store_v2

# 3. Update model registry with new stats
# (manual step - update model_registry.json if metrics change)

# 4. Commit changes
git add data/bbl_feature_store_v2/ docs/
git commit -m "chore: regenerated BBL feature store with latest season data"
```
