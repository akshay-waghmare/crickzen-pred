# IPL Innings-2 Gap EDA

**Generated**: 2026-05-01 13:45 UTC

## Current innings-2 accuracy

| Probability | N | Brier | LogLoss | Mean Prob | Actual |
|-------------|---|-------|---------|-----------|--------|
| `market_p_inn1` | 595 | 0.1576 | 0.4624 | 0.4919 | 0.4403 |
| `raw_p_inn1` | 595 | 0.0965 | 0.3194 | 0.4782 | 0.4403 |
| `iso_p_inn1` | 595 | 0.0967 | 0.3145 | 0.4797 | 0.4403 |

## Top feature correlations

Positive `corr_model_brier_advantage` means the model beats market more as the feature increases.

| Feature | Corr Gap | Corr Abs Gap | Corr Model Advantage |
|---------|----------|--------------|----------------------|
| `bowler_venue_sr` | -0.060 | +0.200 | +0.251 |
| `expected_final_score` | -0.299 | -0.104 | -0.182 |
| `score_adjusted_by_team` | -0.414 | -0.208 | -0.163 |
| `current_run_rate` | -0.262 | -0.043 | -0.160 |
| `target_above_par` | +0.175 | +0.006 | -0.151 |
| `bowler_venue_econ` | +0.111 | -0.087 | -0.147 |
| `inn1_defendability` | +0.104 | +0.025 | -0.147 |
| `batsman_venue_sr` | -0.034 | +0.102 | +0.145 |
| `score_vs_par` | -0.415 | -0.137 | -0.144 |
| `wickets_times_balls` | +0.147 | +0.190 | +0.131 |
| `batsman_venue_avg` | -0.072 | -0.223 | -0.131 |
| `inn1_wickets_lost` | -0.064 | -0.084 | +0.119 |
| `bowler_rolling_sr` | -0.033 | -0.014 | -0.110 |
| `runs_last_18` | -0.253 | -0.046 | -0.102 |
| `score_per_wicket` | -0.200 | -0.076 | -0.096 |

## Candidate chronological split means

| Method | Splits | Brier | LogLoss | ΔBrier vs iso | ΔLogLoss vs iso | ΔBrier vs market | ΔLogLoss vs market |
|--------|--------|-------|---------|----------------|-----------------|------------------|-------------------|
| `stack_iso_market` | 3 | 0.1130 | 0.3408 | -0.0030 | -0.0163 | -0.0611 | -0.1555 |
| `iso_90_market_10` | 3 | 0.1152 | 0.3610 | -0.0008 | +0.0039 | -0.0588 | -0.1353 |
| `iso_95_market_05` | 3 | 0.1154 | 0.3588 | -0.0006 | +0.0017 | -0.0586 | -0.1375 |
| `iso_80_market_20` | 3 | 0.1159 | 0.3670 | -0.0001 | +0.0098 | -0.0581 | -0.1293 |
| `train_opt_iso_market_blend` | 3 | 0.1160 | 0.3571 | +0.0000 | +0.0000 | -0.0580 | -0.1391 |
| `iso_v6` | 3 | 0.1160 | 0.3571 | +0.0000 | +0.0000 | -0.0580 | -0.1391 |
| `raw_v6` | 3 | 0.1179 | 0.3678 | +0.0019 | +0.0107 | -0.0561 | -0.1285 |
| `platt_iso_only` | 3 | 0.1354 | 0.4619 | +0.0194 | +0.1048 | -0.0387 | -0.0344 |
| `platt_raw_iso` | 3 | 0.1389 | 0.4900 | +0.0229 | +0.1329 | -0.0352 | -0.0062 |
| `stack_market_features` | 3 | 0.1558 | 0.4554 | +0.0398 | +0.0983 | -0.0182 | -0.0408 |
| `market` | 3 | 0.1740 | 0.4963 | +0.0580 | +0.1391 | +0.0000 | +0.0000 |

## Recommendation

Candidate `stack_iso_market` improves v6 iso on average and still beats market. Treat it as candidate-only until a larger holdout confirms the gain.

## Blend settings

```json
{
  "split_0.33_best_model_blend_weight": 1.0,
  "split_0.50_best_model_blend_weight": 1.0,
  "split_0.67_best_model_blend_weight": 1.0
}
```