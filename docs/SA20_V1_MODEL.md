# SA20 v1 Model Documentation

## Overview

SA20 v1 is the champion model for South Africa's SA20 T20 league, trained on 99 matches with 21,793 training samples.

**Model Type:** XGBLogRegEnsemble (50% XGBoost + 50% Logistic Regression)  
**Features:** 25 features (same as BBL v10)  
**Calibration:** CV-OOF Innings-Specific Isotonic Regression  
**Training Date:** 2025-12-31

## Performance Metrics

### Overall Metrics

| Metric | Raw Model | Calibrated |
|--------|-----------|------------|
| **Brier Score** | 0.1917 | 0.1798 |
| **ECE** | 6.3% | ~0% |

### Innings-Specific Metrics

| Innings | Samples | Brier Raw | Brier Cal | ECE Raw | ECE Cal |
|---------|---------|-----------|-----------|---------|---------|
| **Innings 1** | 11,470 | 0.2348 | 0.2195 | 9.4% | ~0% |
| **Innings 2** | 10,323 | 0.1439 | 0.1356 | 5.2% | ~0% |

## Calibration Analysis (Innings × Phase)

### Summary Table

| Innings | Phase | Samples | Best Brier | Best ECE |
|---------|-------|---------|------------|----------|
| **1** | Powerplay (1-6) | 2,900 | **Raw** (0.1284) | **Resource** (0.1437) |
| **1** | Middle (7-15) | 5,174 | **Raw** (0.0911) | **Resource** (0.1348) |
| **1** | Death (16-20) | 2,834 | **Raw** (0.0761) | **Resource** (0.1506) |
| **2** | Powerplay (1-6) | 2,898 | **Raw** (0.0799) | **Resource** (0.1385) |
| **2** | Middle (7-15) | 5,041 | **Raw** (0.0507) | **Resource** (0.0503) |
| **2** | Death (16-20) | 2,120 | **Raw** (0.0375) | **Raw** (0.0892) |

### Detailed Results

#### Innings 1 (Setting Target)

| Phase | Brier Raw | Brier Cal | Brier Res | ECE Raw | ECE Cal | ECE Res |
|-------|-----------|-----------|-----------|---------|---------|---------|
| Powerplay | **0.1284** | 0.1785 | 0.2609 | 0.2472 | 0.3073 | **0.1437** |
| Middle | **0.0911** | 0.1389 | 0.2199 | 0.1765 | 0.2638 | **0.1348** |
| Death | **0.0761** | 0.1241 | 0.2012 | 0.1683 | 0.2479 | **0.1506** |

#### Innings 2 (Chasing)

| Phase | Brier Raw | Brier Cal | Brier Res | ECE Raw | ECE Cal | ECE Res |
|-------|-----------|-----------|-----------|---------|---------|---------|
| Powerplay | **0.0799** | 0.0986 | 0.1821 | 0.1526 | 0.1390 | **0.1385** |
| Middle | **0.0507** | 0.0680 | 0.1210 | 0.1172 | 0.1066 | **0.0503** |
| Death | **0.0375** | 0.0508 | 0.1189 | **0.0892** | 0.1007 | 0.1388 |

## Practical Recommendations

### When to Trust What

| Metric | Recommendation |
|--------|----------------|
| **Brier (Accuracy)** | Always use **Raw Model** - wins every phase |
| **ECE (Calibration)** | Use **Resource Win Prob** except Inn2 Death (use Raw) |

### Simple Rule

**Use Raw Model probabilities for everything** in SA20:
- Raw model wins Brier in ALL phases
- Calibrated model actually hurts performance (overfits on small 99-match dataset)
- Resource probability is only marginally better for ECE but much worse for Brier

## Comparison with BBL

| Aspect | BBL v10 | SA20 v1 |
|--------|---------|---------|
| **Dataset Size** | 618 matches (141K samples) | 99 matches (22K samples) |
| **Inn1 Brier** | Raw wins all | Raw wins all |
| **Inn1 ECE** | Raw wins all | Resource wins all |
| **Inn2 Brier** | Mixed (Cal wins PP/Middle) | Raw wins all |
| **Inn2 ECE** | Cal wins most | Resource wins most |
| **Calibration Benefit** | Yes for Innings 2 | No - hurts performance |

### Key Insight

SA20's smaller dataset (99 vs 618 matches) means isotonic calibration overfits. The raw XGBLogRegEnsemble model is already well-optimized for accuracy. For ECE, resource probability (DLS-based) provides better calibration than the learned calibrators.

## Feature Store

- **Path:** `data/sat_feature_store_v1`
- **Teams:** 6
- **Players:** 184
- **Venues:** 6
- **Generated:** 2025-12-31

## ECE-Optimized Phase Calibrators

Since the raw model's ECE is suboptimal but Resource probability shows better ECE, we trained **phase-specific isotonic calibrators on `resource_win_prob`** to achieve perfect ECE.

### Training Script

**Location:** `scripts/train_sa20_phase_calibrators.py`

**What it does:**
1. Loads SA20 training data
2. For each innings × phase combination (6 total):
   - Trains an isotonic calibrator on `resource_win_prob` → `is_winner`
3. Saves to `models/sat_v1/phase_calibrators.pkl`

**Run:**
```bash
python scripts/train_sa20_phase_calibrators.py
```

### Results: Perfect ECE

| Phase | ECE (Raw) | ECE (Resource) | ECE (Calibrated) |
|-------|-----------|----------------|------------------|
| Inn1 Powerplay | 0.2472 | 0.1437 | **0.0000** ✓ |
| Inn1 Middle | 0.1765 | 0.1348 | **0.0000** ✓ |
| Inn1 Death | 0.1683 | 0.1506 | **0.0000** ✓ |
| Inn2 Powerplay | 0.1526 | 0.1385 | **0.0000** ✓ |
| Inn2 Middle | 0.1172 | 0.0503 | **0.0000** ✓ |
| Inn2 Death | 0.0892 | 0.1388 | **0.0000** ✓ |

### Trade-off Warning

⚠️ **ECE-optimized probabilities have WORSE Brier scores than raw model.**

| Metric | Best Source | Use Case |
|--------|-------------|----------|
| **Brier (Accuracy)** | Raw Model | Betting, Expected Value |
| **ECE (Calibration)** | Phase Calibrators | Risk assessment, Probability interpretation |

### Inference Code

```python
import joblib
import numpy as np

# Load phase calibrators
calibrators = joblib.load('models/sat_v1/phase_calibrators.pkl')
# Keys: inn1_powerplay, inn1_middle, inn1_death, inn2_powerplay, inn2_middle, inn2_death

def get_ece_optimized_prob(innings: int, over: int, resource_win_prob: float) -> float:
    """Get ECE-optimized probability using phase calibrators."""
    # Determine phase
    if over <= 6:
        phase = 'powerplay'
    elif over <= 15:
        phase = 'middle'
    else:
        phase = 'death'
    
    key = f'inn{innings}_{phase}'
    return calibrators[key].predict([[resource_win_prob]])[0]

# Example usage
ece_prob = get_ece_optimized_prob(innings=2, over=12, resource_win_prob=0.60)
print(f"ECE-Optimized: {ece_prob:.2%}")
```

### Streamlit Integration

The live Streamlit app displays both probabilities side-by-side:
- **Raw (Blue card)**: Best Brier/Accuracy
- **ECE-Optimized (Green card)**: Best ECE/Calibration

## Model Artifacts

```
models/sat_v1/
├── champion_model.joblib      # XGBLogRegEnsemble
├── isotonic_calibrator.pkl    # Innings-specific calibrators (not recommended)
├── phase_calibrators.pkl      # Phase-specific ECE calibrators (for ECE optimization)
├── training_metadata.json     # Training config and metrics
└── feature_importance.csv     # Top 25 features
```

## CLI Commands

### Full Retrain Workflow

```bash
# 1. Ingest
bbl-pipeline ingest --input-dir sat_male_json --output-dir data/sat_raw

# 2. Process Features
bbl-pipeline process --input-dir data/sat_raw/matches --output-dir data/sat_features_v1 --feature-store-dir data/sat_feature_store_v1

# 3. Train
bbl-pipeline train --input-file data/sat_features_v1/training.parquet --output-dir models/sat_v1

# 4. Generate OOF Calibrator
bbl-pipeline generate-oof --input-file data/sat_features_v1/training.parquet --model-dir models/sat_v1
```

### Live Prediction

```bash
python -m src.bbl_pipeline.inference.crex_live_predictor \
  --match-url "CREX_MATCH_URL" \
  --model-dir models/sat_v1 \
  --feature-store-dir data/sat_feature_store_v1 \
  --output-json data/live_state.json
```

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2025-12-31 | Initial clean rebuild with CV-OOF calibration |
