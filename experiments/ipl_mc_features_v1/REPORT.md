# IPL MC Features Experiment — Results Report

**Generated**: 2026-04-27 14:44 UTC  
**Mode**: `pilot`  
**MC settings**: n_sims=100, horizon_balls=6  
**Evaluator**: resource-based (no ML model, apply_temp=False)  

---

## Overall OOF Metrics

| Method | N | Brier | ECE | LogLoss | ΔBrier | ΔECE | ΔLogLoss |
|--------|---|-------|-----|---------|--------|------|----------|
| `baseline_ipl_v6_features` | 2316 | 0.2326 | 0.1277 | 0.6705 | +0.0000 | +0.0000 | +0.0000 |
| `mc_standalone_calibrated` | 2316 | 0.2240 | 0.0594 | 0.6328 | -0.0086 | -0.0684 | -0.0376 |
| `ml_add_mc_win_prob` | 2316 | 0.2264 | 0.1001 | 0.6557 | -0.0061 | -0.0277 | -0.0148 |
| `ml_add_mc_gap_features` | 2316 | 0.2299 | 0.1214 | 0.6646 | -0.0027 | -0.0063 | -0.0059 |
| `ml_replace_resource_with_mc` | 2316 | 0.2282 | 0.1060 | 0.6588 | -0.0044 | -0.0218 | -0.0117 |
| `ml_clean_swap_resource` | 2316 | 0.2293 | 0.1259 | 0.6619 | -0.0033 | -0.0019 | -0.0086 |

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
| `mc_standalone_calibrated` | innings_1 | 0.2574 | 0.1142 | 0.7157 |
| `mc_standalone_calibrated` | innings_1_death | 0.2564 | 0.1749 | 0.7181 |
| `mc_standalone_calibrated` | innings_1_middle | 0.2524 | 0.1227 | 0.7045 |
| `mc_standalone_calibrated` | innings_1_powerplay | 0.2677 | 0.1212 | 0.7344 |
| `mc_standalone_calibrated` | innings_2 | 0.1879 | 0.1645 | 0.5431 |
| `mc_standalone_calibrated` | innings_2_death | 0.1311 | 0.1477 | 0.4084 |
| `mc_standalone_calibrated` | innings_2_middle | 0.1791 | 0.1745 | 0.5152 |
| `mc_standalone_calibrated` | innings_2_powerplay | 0.2465 | 0.2661 | 0.6942 |
| `mc_standalone_calibrated` | overall | 0.2240 | 0.1047 | 0.6328 |
| `ml_add_mc_win_prob` | innings_1 | 0.2666 | 0.1796 | 0.7528 |
| `ml_add_mc_win_prob` | innings_1_death | 0.2602 | 0.2054 | 0.7420 |
| `ml_add_mc_win_prob` | innings_1_middle | 0.2648 | 0.2126 | 0.7453 |
| `ml_add_mc_win_prob` | innings_1_powerplay | 0.2758 | 0.2293 | 0.7760 |
| `ml_add_mc_win_prob` | innings_2 | 0.1830 | 0.1378 | 0.5508 |
| `ml_add_mc_win_prob` | innings_2_death | 0.1480 | 0.1610 | 0.4600 |
| `ml_add_mc_win_prob` | innings_2_middle | 0.1751 | 0.1569 | 0.5278 |
| `ml_add_mc_win_prob` | innings_2_powerplay | 0.2238 | 0.2019 | 0.6605 |
| `ml_add_mc_win_prob` | overall | 0.2264 | 0.1232 | 0.6557 |
| `ml_add_mc_gap_features` | innings_1 | 0.2638 | 0.2067 | 0.7435 |
| `ml_add_mc_gap_features` | innings_1_death | 0.2586 | 0.2412 | 0.7327 |
| `ml_add_mc_gap_features` | innings_1_middle | 0.2620 | 0.2267 | 0.7360 |
| `ml_add_mc_gap_features` | innings_1_powerplay | 0.2722 | 0.2239 | 0.7675 |
| `ml_add_mc_gap_features` | innings_2 | 0.1936 | 0.1528 | 0.5805 |
| `ml_add_mc_gap_features` | innings_2_death | 0.1566 | 0.1675 | 0.4853 |
| `ml_add_mc_gap_features` | innings_2_middle | 0.1859 | 0.1574 | 0.5573 |
| `ml_add_mc_gap_features` | innings_2_powerplay | 0.2356 | 0.2332 | 0.6943 |
| `ml_add_mc_gap_features` | overall | 0.2299 | 0.1443 | 0.6646 |
| `ml_replace_resource_with_mc` | innings_1 | 0.2682 | 0.1836 | 0.7558 |
| `ml_replace_resource_with_mc` | innings_1_death | 0.2613 | 0.2252 | 0.7432 |
| `ml_replace_resource_with_mc` | innings_1_middle | 0.2651 | 0.2158 | 0.7457 |
| `ml_replace_resource_with_mc` | innings_1_powerplay | 0.2803 | 0.2284 | 0.7857 |
| `ml_replace_resource_with_mc` | innings_2 | 0.1850 | 0.1311 | 0.5541 |
| `ml_replace_resource_with_mc` | innings_2_death | 0.1486 | 0.1477 | 0.4600 |
| `ml_replace_resource_with_mc` | innings_2_middle | 0.1779 | 0.1477 | 0.5331 |
| `ml_replace_resource_with_mc` | innings_2_powerplay | 0.2254 | 0.2007 | 0.6629 |
| `ml_replace_resource_with_mc` | overall | 0.2282 | 0.1228 | 0.6588 |
| `ml_clean_swap_resource` | innings_1 | 0.2635 | 0.2067 | 0.7425 |
| `ml_clean_swap_resource` | innings_1_death | 0.2602 | 0.2437 | 0.7358 |
| `ml_clean_swap_resource` | innings_1_middle | 0.2626 | 0.2255 | 0.7376 |
| `ml_clean_swap_resource` | innings_1_powerplay | 0.2683 | 0.2142 | 0.7579 |
| `ml_clean_swap_resource` | innings_2 | 0.1928 | 0.1438 | 0.5759 |
| `ml_clean_swap_resource` | innings_2_death | 0.1571 | 0.1587 | 0.4817 |
| `ml_clean_swap_resource` | innings_2_middle | 0.1859 | 0.1442 | 0.5554 |
| `ml_clean_swap_resource` | innings_2_powerplay | 0.2322 | 0.2028 | 0.6841 |
| `ml_clean_swap_resource` | overall | 0.2293 | 0.1477 | 0.6619 |

---

## Feature Importance (MC Features)

| Variant | Feature | Mean Importance |
|---------|---------|-----------------|
| `ml_add_mc_gap_features` | `mc_win_prob` | 0.1105 |
| `ml_add_mc_gap_features` | `mc_simulation_std` | 0.0252 |
| `ml_add_mc_gap_features` | `mc_resource_gap` | 0.0151 |
| `ml_add_mc_gap_features` | `mc_resource_abs_gap` | 0.0094 |
| `ml_add_mc_win_prob` | `mc_win_prob` | 0.1228 |
| `ml_replace_resource_with_mc` | `mc_win_prob` | 0.0930 |
| `ml_replace_resource_with_mc` | `mc_simulation_std` | 0.0245 |
| `ml_replace_resource_with_mc` | `mc_resource_gap` | 0.0105 |
| `ml_replace_resource_with_mc` | `mc_resource_abs_gap` | 0.0097 |

---

## Promotion Gate Results

- **ml_add_mc_win_prob**: ❌ FAIL
- **ml_add_mc_gap_features**: ❌ FAIL
- **ml_replace_resource_with_mc**: ❌ FAIL
- **ml_clean_swap_resource**: ✅ PASS

**Failure reasons:**
- [ml_add_mc_win_prob] Segment innings_1_powerplay Brier worsened by +0.0070
- [ml_add_mc_gap_features] Segment innings_1_powerplay Brier worsened by +0.0034
- [ml_replace_resource_with_mc] Segment innings_1_powerplay Brier worsened by +0.0114

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
| MC simulation (100 sims, 6 balls) | ~200–600 ms | per ball state |
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

- Source rows: ?
- Simulated successfully: ?
- Skipped: ?
- Evaluator: ?
