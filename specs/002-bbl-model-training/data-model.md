# Data Model: BBL Model Training

**Feature**: `002-bbl-model-training`

## Entities

### 1. Training Dataset (`X_train`, `y_train`)
Derived from the processed ball-by-ball data. Aggregated to the **ball** or **over** level depending on model granularity. (Assuming **ball-by-ball** for granular win probability).

| Field Name | Type | Description | Source |
| :--- | :--- | :--- | :--- |
| `match_id` | String | Unique Match ID | Raw Data |
| `season` | String | Season Year (e.g., "2023/24") | Raw Data |
| `start_date` | Date | Match Date | Raw Data |
| `venue` | String | Venue Name (Normalized) | Raw Data |
| `batting_team` | String | Name of batting team | Raw Data |
| `bowling_team` | String | Name of bowling team | Raw Data |
| `innings` | Int | 1 or 2 | Raw Data |
| `over` | Int | Current over number (0-19) | Raw Data |
| `ball` | Int | Current ball number (1-6+) | Raw Data |
| `runs_to_date` | Int | Runs scored so far in innings | Feature Eng |
| `wickets_to_date` | Int | Wickets lost so far | Feature Eng |
| `balls_remaining` | Int | Balls remaining in innings | Feature Eng |
| `target_runs` | Int | Target score (for 2nd innings, else -1) | Feature Eng |
| `required_run_rate` | Float | Required RR (for 2nd innings) | Feature Eng |
| `batsman_1` | String | Striker Name | Raw Data |
| `batsman_2` | String | Non-striker Name | Raw Data |
| `bowler` | String | Current Bowler Name | Raw Data |
| `batsman_1_avg` | Float | Rolling Batting Avg (Last 10) | Feature Store |
| `batsman_1_sr` | Float | Rolling Strike Rate (Last 10) | Feature Store |
| `bowler_econ` | Float | Rolling Economy Rate (Last 10) | Feature Store |
| `team_win_rate` | Float | Rolling Win Rate (Last 10) | Feature Store |
| `venue_avg_score` | Float | Avg 1st Innings Score at Venue | Feature Store |
| `is_winner` | Int | Target: 1 if batting team won, 0 else | Derived |

### 2. Match State (Inference Input)
The object passed to the `predict()` function.

```python
@dataclass
class MatchState:
    match_id: str
    venue: str
    batting_team: str
    bowling_team: str
    innings: int
    over: int
    ball: int
    current_score: int
    wickets_lost: int
    batsman_1: str  # Striker
    batsman_2: str  # Non-striker
    bowler: str
    target_runs: Optional[int] = None  # None for 1st innings
```

### 3. Feature Store Schema
The structure of the persisted historical stats.

**Player Stats (`player_stats.parquet`)**
| Field | Type | Description |
| :--- | :--- | :--- |
| `player_name` | String | Canonical Name |
| `matches_played` | Int | Count |
| `total_runs` | Int | Career Runs |
| `balls_faced` | Int | Career Balls |
| `runs_last_10` | List[Int]| Rolling window |
| `balls_last_10` | List[Int]| Rolling window |
| `wickets_last_10` | List[Int]| Rolling window |
| `runs_conceded_last_10`| List[Int]| Rolling window |

**Venue Stats (`venue_stats.parquet`)**
| Field | Type | Description |
| :--- | :--- | :--- |
| `venue` | String | Canonical Name |
| `avg_first_innings_score` | Float | |
| `avg_wickets_per_match` | Float | |
| `bat_first_win_rate` | Float | |
