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

| Segment | Feature | Effect | Keep | Sign Stable | LOO Brier Delta |
|---------|---------|--------|------|-------------|-----------------|
| innings_2_death | `dls_pressure_index` | +3.9812 | 0.524 | 1.00 | -0.02227 |

## Top Ranked By Segment

### innings_2_death

| Feature | Effect | Shrunk | Keep | Sign | LOO ΔBrier |
|---------|--------|--------|------|------|------------|
| `dls_pressure_index` | +3.9812 | +2.0865 | 0.524 | 1.00 | -0.02227 |
| `venue_chase_success` | +9.4594 | +3.1637 | 0.334 | 1.00 | -0.04737 |
| `target_above_par` | +9.5621 | +2.8570 | 0.299 | 0.97 | -0.04901 |
| `score_vs_par` | -3.1485 | -0.9214 | 0.293 | 1.00 | +0.02007 |
| `resource_edge` | +5.9499 | +1.6799 | 0.282 | 1.00 | -0.00352 |
| `chase_difficulty` | +1.1555 | +0.3261 | 0.282 | 1.00 | +0.01066 |
| `model_edge_raw` | +3.0569 | +0.6327 | 0.207 | 1.00 | +0.00678 |
| `model_edge_iso` | +5.1085 | +0.7198 | 0.141 | 1.00 | -0.00520 |
| `model_edge_full` | +3.7969 | +0.4633 | 0.122 | 1.00 | +0.00625 |
| `required_run_rate` | +1.4900 | +0.1542 | 0.103 | 1.00 | +0.01729 |

### innings_2_middle

| Feature | Effect | Shrunk | Keep | Sign | LOO ΔBrier |
|---------|--------|--------|------|------|------------|
| `score_vs_par` | -2.6529 | -0.0367 | 0.014 | 0.97 | +0.01301 |
| `inn1_defendability` | +3.5713 | +0.0257 | 0.007 | 0.93 | +0.00586 |
| `venue_chase_success` | +2.4180 | +0.0105 | 0.004 | 0.93 | -0.00621 |
| `resource_edge` | +1.4980 | +0.0060 | 0.004 | 1.00 | +0.01762 |
| `model_edge_iso` | +1.0227 | +0.0034 | 0.003 | 0.97 | +0.01504 |
| `model_edge_full` | +0.9470 | +0.0025 | 0.003 | 0.95 | +0.01895 |
| `model_edge_raw` | +0.9568 | +0.0025 | 0.003 | 0.97 | +0.01379 |
| `dls_pressure_index` | +1.3404 | +0.0031 | 0.002 | 0.95 | +0.00031 |
| `bowling_team_win_rate` | +0.7194 | +0.0014 | 0.002 | 0.72 | +0.05277 |
| `target_above_par` | +1.4662 | +0.0027 | 0.002 | 0.90 | +0.01970 |

### innings_2_overs_4_12

| Feature | Effect | Shrunk | Keep | Sign | LOO ΔBrier |
|---------|--------|--------|------|------|------------|
| `dls_pressure_index` | +2.4745 | +0.0173 | 0.007 | 1.00 | -0.01843 |
| `resource_edge` | +2.1284 | +0.0122 | 0.006 | 0.94 | -0.01000 |
| `venue_chase_success` | +2.6127 | +0.0122 | 0.005 | 0.93 | +0.00150 |
| `inn1_defendability` | +2.7654 | +0.0087 | 0.003 | 0.97 | +0.03922 |
| `model_edge_full` | +1.1940 | +0.0031 | 0.003 | 0.96 | -0.00627 |
| `model_edge_raw` | +1.2412 | +0.0028 | 0.002 | 0.96 | -0.00734 |
| `model_edge_iso` | +1.2638 | +0.0025 | 0.002 | 0.93 | -0.00680 |
| `target_above_par` | +1.7437 | +0.0019 | 0.001 | 0.96 | +0.02069 |
| `wickets_lost` | -0.4897 | -0.0004 | 0.001 | 0.68 | +0.00545 |
| `wickets_remaining` | +0.4897 | +0.0003 | 0.001 | 0.68 | +0.00545 |

### innings_2_powerplay

| Feature | Effect | Shrunk | Keep | Sign | LOO ΔBrier |
|---------|--------|--------|------|------|------------|
| `model_edge_full` | +2.4058 | +0.1541 | 0.064 | 0.97 | -0.03684 |
| `wickets_remaining` | +2.2720 | +0.1323 | 0.058 | 0.93 | -0.01345 |
| `rrr_times_wickets` | -2.0946 | -0.1193 | 0.057 | 0.91 | -0.01136 |
| `wickets_lost` | -2.2720 | -0.1202 | 0.053 | 0.94 | -0.01345 |
| `resource_edge` | +3.4389 | +0.1334 | 0.039 | 0.90 | -0.03659 |
| `required_run_rate` | +2.7756 | +0.0693 | 0.025 | 0.93 | -0.01633 |
| `model_edge_iso` | +1.5814 | +0.0363 | 0.023 | 0.94 | -0.02867 |
| `model_edge_raw` | +1.7139 | +0.0316 | 0.018 | 0.97 | -0.02794 |
| `venue_chase_success` | +2.5712 | +0.0218 | 0.008 | 0.97 | -0.02444 |
| `inn1_defendability` | +2.1547 | +0.0139 | 0.006 | 0.96 | +0.03748 |
