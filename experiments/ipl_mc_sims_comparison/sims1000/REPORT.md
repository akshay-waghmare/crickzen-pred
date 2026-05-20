# IPL MC Features Experiment — Results Report

**Generated**: 2026-04-27 15:06 UTC  
**Mode**: `pilot`  
**MC settings**: n_sims=1000, horizon_balls=6  
**Evaluator**: resource-based (no ML model, apply_temp=False)  

---

## Overall OOF Metrics

| Method | N | Brier | ECE | LogLoss | ΔBrier | ΔECE | ΔLogLoss |
|--------|---|-------|-----|---------|--------|------|----------|
| `baseline_ipl_v6_features` | 2316 | 0.2326 | 0.1277 | 0.6705 | +0.0000 | +0.0000 | +0.0000 |
| `mc_standalone_calibrated` | 2316 | 0.2240 | 0.0614 | 0.6327 | -0.0085 | -0.0664 | -0.0378 |
| `ml_add_mc_win_prob` | 2316 | 0.2268 | 0.0989 | 0.6568 | -0.0057 | -0.0289 | -0.0136 |
| `ml_add_mc_gap_features` | 2316 | 0.2294 | 0.1204 | 0.6635 | -0.0032 | -0.0074 | -0.0069 |
| `ml_replace_resource_with_mc` | 2316 | 0.2285 | 0.1105 | 0.6592 | -0.0041 | -0.0173 | -0.0113 |
| `ml_clean_swap_resource` | 2316 | 0.2289 | 0.1262 | 0.6611 | -0.0036 | -0.0015 | -0.0093 |

---

## Segment Metrics (Innings × Phase)

| Method | Segment | Brier | ECE | LogLoss |
|--------|---------|-------|-----|---------|
| `baseline_ipl_v6_features` | innings_1 | 0.2658 | 0.2139 | 0.7478 |
| `baseline_ipl_v6_features` | innings_1_death | 0.2649 | 0.2499 | 0.7469 |
| `baseline_ipl_v6_features` | innings_1_middle | 0.2647 | 0.2179 | 0.7427 |
| `baseline_ipl_v6_features` | innings_1_powerplay | 0.2688 | 0.2172 | 0.7577 |
| `baseline_ipl_v6_features` | innings_2 | 0.1971 | 0.1517 | 0.5882 |
| `baseline_ipl_v6_features` | innings_2_death | 0.1611 | 0.1775 | 0.4930 |
| `baseline_ipl_v6_features` | innings_2_middle | 0.1877 | 0.1592 | 0.5614 |
| `baseline_ipl_v6_features` | innings_2_powerplay | 0.2412 | 0.2217 | 0.7078 |
| `baseline_ipl_v6_features` | overall | 0.2326 | 0.1580 | 0.6705 |
| `mc_standalone_calibrated` | innings_1 | 0.2572 | 0.1183 | 0.7152 |
| `mc_standalone_calibrated` | innings_1_death | 0.2565 | 0.1768 | 0.7182 |
| `mc_standalone_calibrated` | innings_1_middle | 0.2520 | 0.1261 | 0.7036 |
| `mc_standalone_calibrated` | innings_1_powerplay | 0.2675 | 0.1328 | 0.7339 |
| `mc_standalone_calibrated` | innings_2 | 0.1882 | 0.1642 | 0.5435 |
| `mc_standalone_calibrated` | innings_2_death | 0.1308 | 0.1573 | 0.4049 |
| `mc_standalone_calibrated` | innings_2_middle | 0.1796 | 0.1743 | 0.5165 |
| `mc_standalone_calibrated` | innings_2_powerplay | 0.2471 | 0.2714 | 0.6960 |
| `mc_standalone_calibrated` | overall | 0.2240 | 0.1096 | 0.6327 |
| `ml_add_mc_win_prob` | innings_1 | 0.2663 | 0.1810 | 0.7522 |
| `ml_add_mc_win_prob` | innings_1_death | 0.2592 | 0.2132 | 0.7394 |
| `ml_add_mc_win_prob` | innings_1_middle | 0.2647 | 0.2067 | 0.7450 |
| `ml_add_mc_win_prob` | innings_1_powerplay | 0.2758 | 0.2206 | 0.7766 |
| `ml_add_mc_win_prob` | innings_2 | 0.1842 | 0.1411 | 0.5540 |
| `ml_add_mc_win_prob` | innings_2_death | 0.1488 | 0.1648 | 0.4621 |
| `ml_add_mc_win_prob` | innings_2_middle | 0.1767 | 0.1643 | 0.5322 |
| `ml_add_mc_win_prob` | innings_2_powerplay | 0.2244 | 0.2043 | 0.6624 |
| `ml_add_mc_win_prob` | overall | 0.2268 | 0.1264 | 0.6568 |
| `ml_add_mc_gap_features` | innings_1 | 0.2625 | 0.2067 | 0.7397 |
| `ml_add_mc_gap_features` | innings_1_death | 0.2584 | 0.2439 | 0.7323 |
| `ml_add_mc_gap_features` | innings_1_middle | 0.2604 | 0.2273 | 0.7314 |
| `ml_add_mc_gap_features` | innings_1_powerplay | 0.2702 | 0.2141 | 0.7619 |
| `ml_add_mc_gap_features` | innings_2 | 0.1941 | 0.1531 | 0.5824 |
| `ml_add_mc_gap_features` | innings_2_death | 0.1561 | 0.1662 | 0.4831 |
| `ml_add_mc_gap_features` | innings_2_middle | 0.1864 | 0.1562 | 0.5593 |
| `ml_add_mc_gap_features` | innings_2_powerplay | 0.2368 | 0.2193 | 0.6991 |
| `ml_add_mc_gap_features` | overall | 0.2294 | 0.1432 | 0.6635 |
| `ml_replace_resource_with_mc` | innings_1 | 0.2682 | 0.1750 | 0.7557 |
| `ml_replace_resource_with_mc` | innings_1_death | 0.2612 | 0.2186 | 0.7436 |
| `ml_replace_resource_with_mc` | innings_1_middle | 0.2646 | 0.2128 | 0.7443 |
| `ml_replace_resource_with_mc` | innings_1_powerplay | 0.2811 | 0.2222 | 0.7876 |
| `ml_replace_resource_with_mc` | innings_2 | 0.1857 | 0.1406 | 0.5551 |
| `ml_replace_resource_with_mc` | innings_2_death | 0.1488 | 0.1419 | 0.4599 |
| `ml_replace_resource_with_mc` | innings_2_middle | 0.1792 | 0.1543 | 0.5356 |
| `ml_replace_resource_with_mc` | innings_2_powerplay | 0.2255 | 0.2206 | 0.6622 |
| `ml_replace_resource_with_mc` | overall | 0.2285 | 0.1304 | 0.6592 |
| `ml_clean_swap_resource` | innings_1 | 0.2630 | 0.2058 | 0.7411 |
| `ml_clean_swap_resource` | innings_1_death | 0.2596 | 0.2536 | 0.7337 |
| `ml_clean_swap_resource` | innings_1_middle | 0.2622 | 0.2295 | 0.7364 |
| `ml_clean_swap_resource` | innings_1_powerplay | 0.2679 | 0.2176 | 0.7567 |
| `ml_clean_swap_resource` | innings_2 | 0.1926 | 0.1538 | 0.5759 |
| `ml_clean_swap_resource` | innings_2_death | 0.1568 | 0.1552 | 0.4808 |
| `ml_clean_swap_resource` | innings_2_middle | 0.1856 | 0.1519 | 0.5554 |
| `ml_clean_swap_resource` | innings_2_powerplay | 0.2323 | 0.2269 | 0.6847 |
| `ml_clean_swap_resource` | overall | 0.2289 | 0.1472 | 0.6611 |

---

## Feature Importance (MC Features)

| Variant | Feature | Mean Importance |
|---------|---------|-----------------|
| `ml_add_mc_gap_features` | `mc_win_prob` | 0.1172 |
| `ml_add_mc_gap_features` | `mc_simulation_std` | 0.0247 |
| `ml_add_mc_gap_features` | `mc_resource_gap` | 0.0127 |
| `ml_add_mc_gap_features` | `mc_resource_abs_gap` | 0.0096 |
| `ml_add_mc_win_prob` | `mc_win_prob` | 0.1232 |
| `ml_replace_resource_with_mc` | `mc_win_prob` | 0.1009 |
| `ml_replace_resource_with_mc` | `mc_simulation_std` | 0.0227 |
| `ml_replace_resource_with_mc` | `mc_resource_gap` | 0.0107 |
| `ml_replace_resource_with_mc` | `mc_resource_abs_gap` | 0.0107 |

---

## Promotion Gate Results

- **ml_add_mc_win_prob**: ❌ FAIL
- **ml_add_mc_gap_features**: ✅ PASS
- **ml_replace_resource_with_mc**: ❌ FAIL
- **ml_clean_swap_resource**: ✅ PASS

**Failure reasons:**
- [ml_add_mc_win_prob] Segment innings_1_powerplay Brier worsened by +0.0070
- [ml_replace_resource_with_mc] Segment innings_1_powerplay Brier worsened by +0.0123

---

## Recommendation

✅ **Candidate variant**: `ml_clean_swap_resource` passed all promotion gates.
Consider creating `models/ipl_v7_mc_features_candidate/` and running a live dry run.

---

## Inference Latency Risk

Adding MC feature generation before ML prediction introduces latency.

| Component | Estimated Latency | Notes |
|-----------|-------------------|-------|
| Baseline IPL v6 ML prediction | ~5–15 ms | feature store + model |
| MC simulation (1000 sims, 6 balls) | ~200–600 ms | per ball state |
| Candidate ML prediction | ~5–15 ms | includes MC features |
| **Total** | **~210–630 ms** | **vs. dashboard poll interval** |

**Mitigation options** (if latency is too high):
- Reduce n-sims to 200–300
- Cache MC by (innings, over, score, wickets) state key
- Run MC asynchronously, fall back to baseline ML while pending
- Keep MC features out of production ML; use as dashboard diagnostic only

**Decision**: Candidate only (offline-only) until latency verified.

---

## Cache Quality

- Source rows: 3000
- Simulated successfully: 2895
- Skipped: 105
- Evaluator: resource_based (no ML model, apply_temp=False)

**Skip reasons:**
- `terminal_no_balls_remaining`: 104
- `terminal_all_out`: 1