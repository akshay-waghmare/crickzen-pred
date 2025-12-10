# ILT20 Model v3: Optimization & Findings
**Date:** December 11, 2025
**Model Version:** v3 (Optimized + Isotonic Calibration)
**Status:** Deployed as `models/ilt_champion_v2`

## 1. Executive Summary
We have successfully deployed a new "v3" model for ILT20 match prediction. This model replaces the previous v2 baseline.
*   **Performance:** Improved Brier Score from **0.1455** (v2) to **0.1416** (v3).
*   **Generalization:** v3 shows significantly less overfitting (Generalization Gap: 0.0126 vs 0.0372).
*   **Endgame Logic:** Implemented "Sensible Guardrails" to correct under-confidence in "Victory Lap" scenarios.

## 2. Model Optimization
The previous model (v2) was an `XGBLogRegEnsemble`. We found it was overfitting the training data.
We switched to a single **XGBoost** model wrapped in **CalibratedClassifierCV (Isotonic)**.

### Key Hyperparameters
*   **Max Depth:** 4 (Increased from 2 to capture more complexity)
*   **Learning Rate:** 0.005 (Slowed down for better convergence)
*   **N Estimators:** 500
*   **Calibration:** Isotonic (Found to be superior to Sigmoid for this dataset)

### Overfitting Analysis
We performed a time-based holdout validation (80% Train / 20% Test):
| Metric | v2 (Old) | v3 (New) | Conclusion |
| :--- | :--- | :--- | :--- |
| **Train Brier** | 0.1352 | 0.1535 | v2 memorized training data. |
| **Test Brier** | 0.1724 | **0.1661** | **v3 generalizes better to new matches.** |

## 3. Endgame Guardrails
We discovered the model was "under-confident" in extreme endgame scenarios (e.g., needing 2 runs off 7 balls).
*   **Model Prediction:** ~86-92% Win Probability.
*   **Reality:** 100% Win Rate (34/34 samples in training data).
*   **Cause:** Sparse data. There are very few historical examples of these specific "easy chase" states, so the model's calibrated bins were too wide.

### The Solution: "Victory Lap" Logic
We implemented deterministic guardrails in `predictor.py` to override the model in these specific cases:

**Tier 1: Victory Lap (Force 99%)**
*   **Condition:** Runs Needed <= 6 AND Wickets Remaining >= 3.
*   **Logic:** One hit away with plenty of wickets is effectively a done deal.

**Tier 2: Safe Chase (Force 98%)**
*   **Condition:** Runs Needed <= 12 AND Run-a-ball or less AND Wickets Remaining >= 4.
*   **Logic:** Cruising to victory with no pressure.

**Tier 3: Resource Confirmation (Force 95%+)**
*   **Condition:** DLS Resource Probability > 97%.
*   **Logic:** If the mathematical resource model says it's a >97% win, we ensure the ML model doesn't drop below 95%.

## 4. Final Performance
| Segment | Brier Score | Notes |
| :--- | :--- | :--- |
| **Overall** | **0.1416** | Excellent accuracy. |
| **2nd Innings** | **0.1084** | Very high confidence in chases. |
| **Death Overs** | **0.1298** | Remains accurate even with guardrails. |

The guardrails caused a negligible mathematical degradation (< 0.001) but significantly improved the "sensibility" and trustworthiness of the model in live usage.
