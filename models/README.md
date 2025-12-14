# Model Registry

This directory contains the active champion models for each league.
Older models are archived in the `archive/` directory.

## Active Models

The current active models are tracked in `model_registry.json`.

| League | Model Version | Path | Description |
|--------|---------------|------|-------------|
| **BBL** | v8 | `models/bbl_v8` | XGBLogRegEnsemble (25 features) + CV-OOF Isotonic Calibration (Brier: 0.1809, ECE: 0.0000) |
| **WBBL** | v3 | `models/wbbl_champion_v3` | XGBoost Tuned model with deduplicated data |
| **ILT20** | v3 | `models/ilt20_v3` | Ensemble model |
| **NPL** | v1 | `models/npl_v1` | Ensemble model |
| **T20I** | v3 | `models/t20i_champion_v3` | Ensemble model |
| **SMA** | v1 | `models/sma_champion_v1` | XGBoost model with Isotonic Calibration (Brier: 0.1484) |

## BBL v8 - Champion Model (December 2025)

### Architecture
- **Model Type:** XGBLogRegEnsemble (50% XGBoost + 50% Logistic Regression)
- **Features:** 25 carefully selected features
- **Calibration:** Isotonic Regression with Cross-Validation Out-of-Fold (CV-OOF) fitting

### Performance
| Metric | Value |
|--------|-------|
| Brier Score | 0.1809 |
| ECE (Expected Calibration Error) | 0.0000 |

### Files
```
models/bbl_v8/
├── champion_model.joblib      # Base ensemble model
├── isotonic_calibrator.pkl    # CV-OOF fitted calibrator
└── champion_metadata.json     # Training metadata
```

### Documentation
See [docs/BBL_V8_MODEL.md](../docs/BBL_V8_MODEL.md) for full documentation including:
- Feature descriptions
- Training methodology
- Live prediction fixes
- Calibration approach

## Archived Models

Old BBL versions (v3-v7) have been archived to `archive/` with suffix `_dec2025`:
- `archive/bbl_v3_dec2025/` - Initial XGBoost with isotonic calibration
- `archive/bbl_v4_dec2025/` - XGBLogRegEnsemble first attempt
- `archive/bbl_v5_dec2025/` - Improved hyperparameters
- `archive/bbl_v6_dec2025/` - Better feature importance tuning
- `archive/bbl_v7_dec2025/` - Isotonic calibration (data leakage issue)

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

### BBL Live Prediction
```bash
python -m bbl_pipeline.inference.crex_live_predictor \
    --model-dir models/bbl_v8 \
    --feature-store-dir data/bbl_feature_store_v2 \
    --match-url "<CREX_MATCH_URL>"
```
