# Quickstart: Match State Logging System

**Feature**: `001-match-state-logging`

## Record a Match

```bash
# Record match states during live prediction (add --record-states flag)
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "CREX_MATCH_URL" \
  --model-dir models/t20_male_v2 \
  --feature-store-dir data/t20_male_feature_store_v2 \
  --league bbl \
  --output-json data/live_state.json \
  --record-states

# Custom output directory
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "CREX_MATCH_URL" \
  --model-dir models/t20_male_v2 \
  --feature-store-dir data/t20_male_feature_store_v2 \
  --league sa20 \
  --output-json data/live_state.json \
  --record-states \
  --states-dir data/match_states/sa20
```

## Post-Match Analysis

```bash
# Process completed match: compute volatility, signal events, price reversion labels
bbl-pipeline analyze-states \
  --match-file data/match_states/bbl/<match_id>.parquet \
  --outcome "Team A"

# Consolidate all matches for a league
bbl-pipeline analyze-states \
  --league bbl \
  --consolidate

# Compute calibration metrics for recorded matches
bbl-pipeline analyze-states \
  --league bbl \
  --calibration-report
```

## Query Recorded Data (Python)

```python
import pandas as pd

# Load all recorded ball states for a league
df = pd.read_parquet("data/match_states/bbl/all_matches.parquet")

# 1. Calibration check: Brier score on recorded matches
from sklearn.metrics import brier_score_loss
meta = pd.read_parquet("data/match_states/bbl/match_metadata.parquet")
df_with_outcome = df.merge(meta[['match_id', 'winner']], on='match_id')
df_with_outcome['actual_win'] = (df_with_outcome['batting_team'] == df_with_outcome['winner']).astype(int)
brier = brier_score_loss(df_with_outcome['actual_win'], df_with_outcome['model_final_prob'])
print(f"Brier Score: {brier:.4f}")

# 2. Return by deviation bucket
signals = pd.read_parquet("data/match_states/bbl/signal_events.parquet")
bucket_analysis = signals.groupby('deviation_bucket').agg(
    count=('match_id', 'count'),
    win_rate=('model_team_won', 'mean'),
    avg_deviation=('deviation', 'mean')
)
print(bucket_analysis)

# 3. Volatility comparison
vol = pd.read_parquet("data/match_states/bbl/volatility_profiles.parquet")
print(f"Avg volatility ratio: {vol['volatility_ratio'].mean():.2f}")
print(f"Model overreacts {vol['volatility_ratio'].mean():.1f}x vs market")

# 4. Strong-team recovery premium
stress = signals[
    (signals['batting_team_tier'] == 'top') &
    (signals['wickets'] >= 3) &
    (signals['match_phase'] == 'powerplay')
]
print(f"Top-team recovery rate: {stress['model_team_won'].mean():.1%}")
print(f"Model predicted: {stress['model_prob'].mean():.1%}")
print(f"Recovery premium: {stress['model_team_won'].mean() - stress['model_prob'].mean():.1%}")
```

## Data Layout

```
data/match_states/
├── bbl/
│   ├── 1234567.parquet          # Per-match ball states
│   ├── 1234568.parquet
│   ├── match_metadata.parquet   # Match-level metadata + outcomes
│   ├── all_matches.parquet      # Consolidated ball states
│   ├── volatility_profiles.parquet  # Per-match volatility metrics
│   └── signal_events.parquet    # Deviation events for edge analysis
├── sa20/
│   └── ...
├── ilt20/
│   └── ...
└── ssm/
    └── ...
```
