# ODI Feature Audit

## Scope

This audit checks the 41 features selected by `models/odi_all_v2` for semantic validity, training/inference alignment, redundancy, and measurable predictive value.

The current champion remains unchanged until a detached retrain passes the chronological promotion gate.

## Current Findings

### Keep and validate in the next retrain

- `resource_win_prob`: strongest live and held-out signal; retain.
- `score_vs_par`: valid resource-adjusted progress signal. It is not a DLS score and can be negative while `expected_final_score` remains above target.
- `expected_final_score`: valid projection signal. Its importance is lower than `score_vs_par`, but permutation testing shows useful signal.
- `dls_pressure_index`, `score_per_wicket`, `inn1_defendability`, and the first-innings carryover features: meaningful independent context, subject to source-quality checks.
- Team/context features: useful as a group on the recent holdout, but must be checked for leakage and future availability.

### Redundant pressure family

These features describe closely related chase pressure:

- `required_run_rate`
- `run_rate_diff`
- `pressure_index`
- `rrr_times_wickets`

Training correlations are very high: `required_run_rate` vs `pressure_index` about `.973`, `pressure_index` vs `rrr_times_wickets` about `.989`, and `run_rate_diff` vs `pressure_index` about `.958`. They should be evaluated as a group in a detached ablation, not interpreted as four independent causes.

### Candidates for removal or replacement

- `set_batter_exposure`: zero XGBoost importance and zero permutation impact in the recent chronological audit slice.
- `wickets_last_6`: zero XGBoost importance and zero permutation impact in the same slice.
- `projected_score`: selected, but deliberately zero during innings 2. It behaves mainly as an innings indicator in the chase and needs a detached comparison before being retained.

## Formula and Source Checks

- Training and realtime inference use the same `score_vs_par` shape: current score minus a resource-adjusted reference based on the first-innings score in a chase.
- `expected_final_minus_target` is a useful derived explanation metric, but it is not currently a selected champion feature. It describes projected finishing margin, whereas `score_vs_par` describes current resource-adjusted pace.
- `pressure_index` is driven by required run rate and wickets lost; `score_vs_par` does not directly feed its formula. The model can use both, but the UI must not describe them as the same calculation.
- Current England/India live state had real first-innings carryover from `crex_over_api` (`234` target, `10` wickets lost, `42` powerplay runs, death rate `4.64`). Older state files still contain defaults and must not be used for verification.

## Held-Out Evidence

Recent chronological seasons (`2025`, `2025/26`, `2026`), 112,203 rows, XGBoost component:

- Baseline Brier: `0.1536`
- Resource group permutation delta: `+0.0277`
- Innings-1 carryover group delta: `+0.0156`
- Context group delta: `+0.0149`
- Projection group delta: `+0.0026`
- Pressure group delta: `+0.0023`
- Momentum group delta: approximately `+0.00004`
- `expected_final_score` individual delta: `+0.0013`
- `score_vs_par` individual delta: `+0.0072`
- `projected_score` individual delta: `+0.00028`
- `required_run_rate` individual delta: `+0.00013`
- `run_rate_diff` individual delta: `+0.00067`
- `pressure_index` individual delta: `+0.00092`
- `rrr_times_wickets` individual delta: `+0.00052`

Permutation results are diagnostic, not a promotion result. They use the saved XGBoost component because the saved sklearn logistic component cannot currently be loaded under the local sklearn version (`SimpleImputer` serialization incompatibility).

## Detached Candidate Comparison

A first detached run trained the same XGB/logistic ensemble family on a capped pre-2025 sample and evaluated on all `2025`, `2025/26`, and `2026` rows. This is directional evidence only; it is not the final promotion gate.

| Candidate | Features | All Brier | Male Brier | Female Brier | Innings-2 Brier | All log loss |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | 41 | 0.17842 | 0.18735 | 0.16912 | 0.13487 | 0.52443 |
| Drop `set_batter_exposure`, `wickets_last_6` | 39 | 0.17846 | 0.18710 | 0.16947 | 0.13482 | 0.52447 |
| Drop `projected_score` | 40 | **0.17815** | **0.18725** | **0.16867** | **0.13447** | **0.52340** |
| Drop two pressure variables | 39 | 0.17879 | 0.18755 | 0.16968 | 0.13573 | 0.52537 |

The evidence supports testing removal of `projected_score` on the full chronological training split. It does not support removing the pressure family. The two zero-impact features remain cleanup candidates, but removing them alone is not an improvement.

The full pre-2025 retrain confirms the candidate clears the measured slice gate:

| Candidate | All Brier | Male Brier | Female Brier | Innings-2 Brier | Late Brier | All log loss |
|---|---:|---:|---:|---:|---:|---:|
| Full baseline | 0.178138 | 0.187249 | 0.168653 | 0.135810 | 0.105109 | 0.525141 |
| Full candidate without `projected_score` | **0.177274** | **0.186654** | **0.167510** | **0.134979** | **0.104123** | **0.522643** |

The candidate artifact is saved at `models/odi_all_v3_feature_pruned_candidate`. It loads through `Predictor.load`, exposes 40 model inputs, and excludes `projected_score`. It is still not routed as production until the remaining smoke tests and deployment decision are complete.

The semantic follow-up tested the complete projected-only family. Although `projected_vs_venue_avg` and `score_vs_venue_over_par` are zero during innings 2, they are nonzero and useful in innings 1. Removing all three fields produced a worse full chronological candidate: overall Brier `0.177679` versus `0.177274`, male `0.187026` versus `0.186654`, female `0.167950` versus `0.167510`, innings-2 `0.135405` versus `0.134979`, and late `0.104618` versus `0.104123`. They remain in the validated candidate; their zero chase values must be described as phase-scoped behavior, not treated as missing data.

### Calibration Gate Result

An initial candidate-specific isotonic experiment was rejected. It fitted curves from in-sample pre-2025 predictions, and therefore was not a valid OOF calibration; it worsened the 2025+ Brier score from `0.177274` raw to `0.178710` overall, with regressions in male, female, innings-2, and late-chase slices. The generated calibration file was removed so it cannot be applied accidentally. Proper out-of-fold calibration is still required before production routing.

A second chronological OOF calibration attempt was also rejected. It used three forward-only folds over pre-2025 data (`111,396` OOF rows), then evaluated on untouched 2025+ data. Overall Brier changed from `0.177274` raw to `0.179175` calibrated, and log loss changed from `0.522643` to `0.546263`. Male Brier changed `0.186654 -> 0.189466`, female `0.167510 -> 0.168464`, and innings-2 `0.134979 -> 0.135617`; only late-chase Brier improved (`0.104123 -> 0.102873`). No calibration artifact was saved.

## Required Next Experiment

Train detached ODI candidates using the same trainer and chronological split (`train before 2025`, test on `2025+`), with all/male/female slices:

1. Baseline 41 features.
2. Remove `set_batter_exposure` and `wickets_last_6`.
3. Remove `projected_score`.
4. Replace the redundant pressure family with a smaller validated subset.
5. Add `expected_final_minus_target` only if it can be reconstructed identically in both training and realtime inference.

The current training parquet does not contain `first_innings_score` or `target_score`; the live mapper gets the target from the scraped match state. `target_above_par` alone cannot reconstruct the target because `venue_avg_score` is not present in the selected training table. Therefore `expected_final_minus_target` remains explanation-only until the historical processor exports the target contract and the feature is added through a new parity-tested dataset build.

Promote only a candidate that improves Brier/log loss overall and does not regress the male, female, innings-2, or late-innings slices. Until then, keep the champion and use `expected_final_minus_target` as an explanatory UI metric only.
