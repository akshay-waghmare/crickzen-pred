# IPL Horseshoe-Style Edge Analysis

Empirical shrinkage test after controlling for market probability.

Interpretation:
- `effect` is the standardized logistic coefficient after `logit(market_p_inn1)` is included.
- `keep_weight` is the horseshoe-style survival weight; near zero means noisy/shrunk.
- Negative `loo_brier_delta` means the signal improved leave-one-match-out Brier vs market-only.

## Segment Summary

| Segment | Rows | Matches | Actual | Market Mean | Market Brier | Market LogLoss |
|---------|------|---------|--------|-------------|--------------|----------------|
| innings_2_powerplay | 72 | 12 | 0.500 | 0.558 | 0.1195 | 0.3800 |
| innings_2_middle | 104 | 12 | 0.481 | 0.550 | 0.0794 | 0.2865 |
| innings_2_death | 42 | 11 | 0.548 | 0.586 | 0.1154 | 0.4007 |
| innings_2_overs_4_12 | 107 | 12 | 0.495 | 0.556 | 0.0832 | 0.2927 |

## Signals That Survive Shrinkage

_No signal passed the shrinkage survival gate._

## Top Ranked By Segment

### innings_2_death

| Feature | Effect | Shrunk | Keep | Sign | LOO ΔBrier |
|---------|--------|--------|------|------|------------|
| `model_edge_raw` | +3.0569 | +0.8595 | 0.281 | 1.00 | +0.00678 |
| `venue_chase_success` | +9.4594 | +2.5817 | 0.273 | 0.99 | -0.04737 |
| `target_above_par` | +9.5621 | +2.5364 | 0.265 | 0.98 | -0.04901 |
| `dls_pressure_index` | +3.9812 | +0.9584 | 0.241 | 1.00 | -0.02227 |
| `resource_edge` | +5.9499 | +1.3677 | 0.230 | 1.00 | -0.00352 |
| `chase_difficulty` | +1.1555 | +0.2520 | 0.218 | 1.00 | +0.01066 |
| `score_vs_par` | -3.1485 | -0.6663 | 0.212 | 1.00 | +0.02007 |
| `model_edge_iso` | +5.1085 | +0.4860 | 0.095 | 1.00 | -0.00520 |
| `model_edge_full` | +3.7969 | +0.2674 | 0.070 | 1.00 | +0.00625 |
| `inn1_defendability` | +3.9779 | +0.2078 | 0.052 | 0.98 | +0.11129 |

### innings_2_middle

| Feature | Effect | Shrunk | Keep | Sign | LOO ΔBrier |
|---------|--------|--------|------|------|------------|
| `score_vs_par` | -2.6529 | -0.0156 | 0.006 | 0.98 | +0.01301 |
| `inn1_defendability` | +3.5713 | +0.0139 | 0.004 | 0.89 | +0.00586 |
| `resource_edge` | +1.4980 | +0.0045 | 0.003 | 0.99 | +0.01762 |
| `model_edge_iso` | +1.0227 | +0.0022 | 0.002 | 0.98 | +0.01504 |
| `model_edge_full` | +0.9470 | +0.0019 | 0.002 | 0.97 | +0.01895 |
| `venue_chase_success` | +2.4180 | +0.0045 | 0.002 | 0.92 | -0.00621 |
| `dls_pressure_index` | +1.3404 | +0.0020 | 0.001 | 0.96 | +0.00031 |
| `model_edge_raw` | +0.9568 | +0.0013 | 0.001 | 0.96 | +0.01379 |
| `target_above_par` | +1.4662 | +0.0016 | 0.001 | 0.92 | +0.01970 |
| `team_strength_diff` | -0.5661 | -0.0002 | 0.000 | 0.68 | +0.04471 |

### innings_2_overs_4_12

| Feature | Effect | Shrunk | Keep | Sign | LOO ΔBrier |
|---------|--------|--------|------|------|------------|
| `dls_pressure_index` | +2.4745 | +0.0167 | 0.007 | 1.00 | -0.01843 |
| `resource_edge` | +2.1284 | +0.0137 | 0.006 | 0.96 | -0.01000 |
| `venue_chase_success` | +2.6127 | +0.0086 | 0.003 | 0.95 | +0.00150 |
| `model_edge_iso` | +1.2638 | +0.0035 | 0.003 | 0.95 | -0.00680 |
| `model_edge_raw` | +1.2412 | +0.0032 | 0.003 | 0.94 | -0.00734 |
| `inn1_defendability` | +2.7654 | +0.0064 | 0.002 | 0.94 | +0.03922 |
| `target_above_par` | +1.7437 | +0.0034 | 0.002 | 0.95 | +0.02069 |
| `model_edge_full` | +1.1940 | +0.0020 | 0.002 | 0.98 | -0.00627 |
| `wickets_remaining` | +0.4897 | +0.0004 | 0.001 | 0.77 | +0.00545 |
| `wickets_lost` | -0.4897 | -0.0003 | 0.001 | 0.74 | +0.00545 |

### innings_2_powerplay

| Feature | Effect | Shrunk | Keep | Sign | LOO ΔBrier |
|---------|--------|--------|------|------|------------|
| `wickets_lost` | -2.2720 | -0.1369 | 0.060 | 0.94 | -0.01345 |
| `wickets_remaining` | +2.2720 | +0.1283 | 0.056 | 0.93 | -0.01345 |
| `rrr_times_wickets` | -2.0946 | -0.1152 | 0.055 | 0.92 | -0.01136 |
| `model_edge_full` | +2.4058 | +0.1158 | 0.048 | 0.97 | -0.03684 |
| `resource_edge` | +3.4389 | +0.1016 | 0.030 | 0.87 | -0.03659 |
| `model_edge_iso` | +1.5814 | +0.0356 | 0.023 | 0.95 | -0.02867 |
| `required_run_rate` | +2.7756 | +0.0479 | 0.017 | 0.89 | -0.01633 |
| `model_edge_raw` | +1.7139 | +0.0240 | 0.014 | 0.97 | -0.02794 |
| `venue_chase_success` | +2.5712 | +0.0222 | 0.009 | 0.98 | -0.02444 |
| `target_above_par` | +2.2978 | +0.0142 | 0.006 | 0.92 | -0.00117 |
