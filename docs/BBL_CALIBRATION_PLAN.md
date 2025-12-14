# BBL Model Calibration Improvement Plan

## Objective
Reduce the Expected Calibration Error (ECE) of the BBL model from **0.0220** to **< 0.0016**.
This target exceeds the constitutional requirement of < 0.0021, aiming for betting-grade reliability.

## Current Baseline (BBL v2)
*   **Model**: XGBLogRegEnsemble (50% XGBoost, 50% Logistic Regression)
*   **Brier Score**: 0.1664
*   **ECE**: 0.0220
*   **Innings 1 ECE**: 0.0185
*   **Innings 2 ECE**: 0.0289
*   **Observation**: The model is currently uncalibrated (likely overconfident). A 10x reduction in ECE is required.

## Strategy 1: Post-Hoc Calibration (High Impact)
The current pipeline trains the ensemble but does not apply a dedicated calibration layer on the final output.
*   **Action**: Implement `CalibratedClassifierCV` (scikit-learn) on top of the final ensemble.
*   **Methods to Try**:
    *   **Isotonic Regression**: Non-parametric, good for correcting bias if we have enough data (we have ~23k samples, which is sufficient).
    *   **Platt Scaling (Sigmoid)**: Parametric, better if the distortion is S-shaped.
*   **Implementation**:
    *   Split training data: Train on 80%, Calibrate on 20% (must be time-ordered).
    *   Or use Cross-Validation calibration.

## Strategy 2: Direct ECE Optimization (Medium Impact)
Currently, the ensemble weights (XGB vs LogReg) are fixed at 0.5/0.5 or optimized for Brier Score.
*   **Action**: Optimize the ensemble weights specifically to minimize ECE on a validation set.
*   **Hypothesis**: Logistic Regression is generally better calibrated than XGBoost. Increasing the LogReg weight might improve calibration naturally, even if Brier score degrades slightly.

## Strategy 3: Regularization & Hyperparameters (Medium Impact)
Overconfidence (high ECE) often stems from overfitting.
*   **Action**: Tune XGBoost parameters to be more conservative.
    *   Increase `min_child_weight`.
    *   Increase `gamma` (min split loss).
    *   Decrease `max_depth`.
    *   Increase `reg_lambda` (L2 regularization).

## Strategy 4: Feature Engineering for Uncertainty (Low Impact)
The model might be overconfident because it lacks "context of uncertainty".
*   **Action**: Add features representing variance/volatility.
    *   `std_dev` of rolling run rates.
    *   `match_volatility_index` (fluctuation in win probability over the last 2 overs).

## Execution Plan
1.  **Baseline Analysis**: Confirm current calibration curve shape (S-shaped vs. J-shaped) to choose between Isotonic/Sigmoid.
2.  **Experiment A (Post-Hoc)**: Apply Isotonic Regression to the existing BBL v2 model output. Measure ECE.
3.  **Experiment B (Regularization)**: Retrain XGBoost with stricter regularization.
4.  **Experiment C (Ensemble Weights)**: Grid search ensemble weights (0.1 to 0.9) against ECE.

## Success Criteria
*   **Primary**: ECE < 0.0016 on the hold-out test set.
*   **Secondary**: Brier Score does not increase by more than 5% (must stay < 0.175).
