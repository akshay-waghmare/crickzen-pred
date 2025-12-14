# BBL Model v3 Documentation

## Overview

BBL Model v3 represents a significant milestone in our predictive modeling capabilities, achieving an exceptionally low Expected Calibration Error (ECE) of **0.0087** while maintaining high accuracy (Brier Score: 0.1514).

## Evolution & Findings

### v1: The Baseline (Ensemble)
- **Architecture:** Ensemble of XGBoost and Logistic Regression.
- **Features:** 51 features (comprehensive set).
- **Performance:**
  - Brier Score: 0.1762
  - ECE: 0.0220
- **Analysis:** Good baseline, but room for improvement in accuracy.

### v2: Hyperparameter Optimization (Uncalibrated)
- **Change:** Applied hyperparameters tuned for the WBBL v3 champion model (which had shown 5% improvement).
- **Performance:**
  - Brier Score: **0.1533** (13% improvement over v1)
  - ECE: 0.0475 (Degraded calibration)
- **Analysis:** The WBBL parameters significantly improved the model's discriminative power (lower Brier/LogLoss), but the raw probabilities became uncalibrated (over/under-confident).

### v3: The Champion (Calibrated)
- **Change:** Applied **Isotonic Calibration** on top of the v2 XGBoost model.
- **Method:** Split training data into Train (60%), Calibration (20%), and Test (20%).
- **Performance:**
  - Brier Score: **0.1514** (Best)
  - ECE: **0.0087** (State-of-the-art calibration)
- **Analysis:** Calibration corrected the probability distribution without sacrificing the accuracy gains from the hyperparameter tuning.

## Key Metrics Breakdown (v3)

| Inning | Phase | ECE | Brier Score | Count | Status |
|--------|-------|-----|-------------|-------|--------|
| **1** | Powerplay | 0.0290 | 0.2038 | 3,624 | Good |
| **1** | Middle | 0.0250 | 0.1808 | 5,412 | Good |
| **1** | Death | 0.0270 | 0.1717 | 3,038 | Good |
| **2** | Powerplay | 0.0315 | 0.1549 | 3,618 | Good |
| **2** | Middle | **0.0128** | 0.1036 | 5,238 | ✅ Excellent |
| **2** | Death | 0.0366 | **0.0537** | 2,264 | Good |

*Note: Inning 2 Middle Overs show exceptional calibration, while Inning 2 Death Overs show the highest predictive accuracy (lowest Brier).*

## Implementation Details

### Hyperparameters (Inherited from WBBL v3)
```python
params = {
    "subsample": 0.8,
    "reg_lambda": 2,
    "reg_alpha": 1,
    "n_estimators": 500,
    "min_child_weight": 5,
    "max_depth": 4,
    "learning_rate": 0.01,
    "colsample_bytree": 0.4,
    "objective": "binary:logistic",
    "eval_metric": "logloss"
}
```

### Calibration Strategy
We used `CalibratedClassifierCV` with `method='isotonic'` and `cv='prefit'`. This requires a dedicated calibration hold-out set to avoid overfitting the calibration map.

```python
# Split: Train (60%), Calibration (20%), Test (20%)
X_train, X_calib, y_train, y_calib = train_test_split(...)

# Train Base
base_model.fit(X_train, y_train)

# Calibrate
calibrated = CalibratedClassifierCV(base_model, method='isotonic', cv='prefit')
calibrated.fit(X_calib, y_calib)
```

## Detailed Performance Analysis

### 1. Probability Zone Calibration
The model shows exceptional calibration across high-density probability zones.

| Range | Count | Mean Pred | Actual Win Rate | Diff (Error) | Brier Score | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **0.0 - 0.1** | 3,406 | 3.20% | 3.20% | **0.00%** | 0.0301 | ✅ Perfect |
| **0.1 - 0.2** | 1,660 | 14.11% | 11.51% | 2.61% | 0.1019 | Slight Overconfidence |
| **0.2 - 0.3** | 3,024 | 25.02% | 25.43% | **0.41%** | 0.1890 | ✅ Excellent |
| **0.3 - 0.4** | 322 | 35.44% | 31.37% | 4.07% | 0.2170 | Overconfidence (Low Sample) |
| **0.4 - 0.5** | 3,194 | 41.88% | 41.70% | **0.17%** | 0.2426 | ✅ Perfect |
| **0.5 - 0.6** | 2,035 | 55.60% | 54.64% | 0.95% | 0.2477 | ✅ Excellent |
| **0.6 - 0.7** | 1,391 | 67.92% | 64.34% | 3.58% | 0.2307 | Slight Overconfidence |
| **0.7 - 0.8** | 4,175 | 74.18% | 75.50% | 1.32% | 0.1835 | ✅ Very Good |
| **0.8 - 0.9** | 36 | 85.97% | 91.67% | 5.69% | 0.0793 | Underconfidence (Very Low Sample) |
| **0.9 - 1.0** | 3,951 | 94.97% | 94.99% | **0.02%** | 0.0459 | ✅ Perfect |

### 2. Over-wise Performance
The model's reliability varies by match stage, with the **2nd Inning Middle Overs** being the most reliable.

#### Inning 1
| Over | ECE | Brier | Notes |
| :--- | :--- | :--- | :--- |
| **2-6 (PP)** | ~0.046 | ~0.205 | High uncertainty, slightly higher calibration error. |
| **7-15** | ~0.040 | ~0.185 | Calibration improves as the inning stabilizes. |
| **16-20** | ~0.032 | ~0.172 | **Best Calibration** for Inning 1. The model reads the death overs well. |

#### Inning 2
| Over | ECE | Brier | Notes |
| :--- | :--- | :--- | :--- |
| **2-6 (PP)** | ~0.042 | ~0.160 | Better accuracy than Inn 1 PP, but similar calibration error. |
| **7-15** | **~0.029** | **~0.109** | **Sweet Spot**. Over 11 has an incredible ECE of **0.0148**. |
| **16-20** | ~0.040 | **~0.059** | **Highest Accuracy**. Brier drops massively as the result becomes clear. |

## Conclusion
The combination of **domain-specific hyperparameter tuning** (transfer learning from WBBL) and **post-hoc isotonic calibration** yields the most robust probability estimates for the Big Bash League.
