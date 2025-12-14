# Model Registry

This directory contains the active champion models for each league.
Older models are archived in the `archive/` directory.

## Active Models

The current active models are tracked in `model_registry.json`.

| League | Model Version | Path | Description |
|--------|---------------|------|-------------|
| **BBL** | v3 | `models/bbl_v3` | XGBoost model with WBBL v3 hyperparameters + Isotonic Calibration (Brier: 0.1514, ECE: 0.0087) |
| **WBBL** | v3 | `models/wbbl_champion_v3` | XGBoost Tuned model with deduplicated data |
| **ILT20** | v3 | `models/ilt20_v3` | Ensemble model |
| **NPL** | v1 | `models/npl_v1` | Ensemble model |
| **T20I** | v3 | `models/t20i_champion_v3` | Ensemble model |
| **SMA** | v1 | `models/sma_champion_v1` | Ensemble model |

## Usage

To load the latest model for a league, refer to `model_registry.json` to get the correct path.

```python
import json
import joblib
from pathlib import Path

def load_champion_model(league):
    with open('models/model_registry.json') as f:
        registry = json.load(f)
    
    if league not in registry['active_models']:
        raise ValueError(f"No active model for league: {league}")
        
    model_info = registry['active_models'][league]
    model_path = Path(model_info['path']) / 'champion_model.joblib'
    
    return joblib.load(model_path)
```
