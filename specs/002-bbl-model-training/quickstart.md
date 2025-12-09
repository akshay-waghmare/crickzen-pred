# Quickstart: BBL Model Training

**Feature**: `002-bbl-model-training`

## Prerequisites
- Python 3.10+
- `bbl_pipeline` installed (`pip install -e .`)
- Processed Parquet data in `data/processed/` (from Feature 001)

## Commands

### 1. Feature Engineering
Generate the training dataset and historical stats.
```bash
bbl-pipeline features generate --input data/processed --output data/training
```

### 2. Train Model
Train the XGBoost model with time-series CV and calibration.
```bash
bbl-pipeline train --input data/training/dataset.parquet --output models/v1
```

### 3. Evaluate
Run evaluation on the hold-out test set.
```bash
bbl-pipeline evaluate --model models/v1 --test-data data/training/test.parquet
```

### 4. Inference (CLI)
Predict win probability for a specific state.
```bash
bbl-pipeline predict --venue "MCG" --batting "Stars" --bowling "Renegades" --score 120/3 --over 14.2
```

## Python API

```python
from bbl_pipeline.inference import Predictor, MatchState

# Load model
predictor = Predictor.load("models/v1")

# Create state
state = MatchState(
    venue="MCG",
    batting_team="Melbourne Stars",
    bowling_team="Melbourne Renegades",
    innings=1,
    over=14,
    ball=2,
    current_score=120,
    wickets_lost=3,
    batsman_1="Glenn Maxwell",
    batsman_2="Marcus Stoinis",
    bowler="Kane Richardson"
)

# Predict
prob = predictor.predict(state)
print(f"Win Probability: {prob:.2%}")
```
