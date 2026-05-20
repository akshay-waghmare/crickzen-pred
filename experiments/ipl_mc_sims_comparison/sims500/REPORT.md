# IPL MC Features Experiment — Results Report

**Generated**: 2026-04-27 15:00 UTC  
**Mode**: `pilot`  
**MC settings**: n_sims=500, horizon_balls=6  
**Evaluator**: resource-based (no ML model, apply_temp=False)  

---

## Overall OOF Metrics

| Method | N | Brier | ECE | LogLoss | ΔBrier | ΔECE | ΔLogLoss |
|--------|---|-------|-----|---------|--------|------|----------|
| `baseline_ipl_v6_features` | 2316 | 0.2326 | 0.1277 | 0.6705 | +0.0000 | +0.0000 | +0.0000 |
| `mc_standalone_calibrated` | 2316 | 0.2240 | 0.0622 | 0.6330 | -0.0085 | -0.0656 | -0.0375 |
| `ml_add_mc_win_prob` | 2316 | 0.2269 | 0.1002 | 0.6566 | -0.0057 | -0.0276 | -0.0139 |
| `ml_add_mc_gap_features` | 2316 | 0.2288 | 0.1194 | 0.6620 | -0.0037 | -0.0083 | -0.0085 |
| `ml_replace_resource_with_mc` | 2316 | 0.2282 | 0.1063 | 0.6585 | -0.0044 | -0.0214 | -0.0120 |
| `ml_clean_swap_resource` | 2316 | 0.2289 | 0.1282 | 0.6608 | -0.0037 | +0.0005 | -0.0097 |

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
| `mc_standalone_calibrated` | innings_1 | 0.2572 | 0.1165 | 0.7152 |
| `mc_standalone_calibrated` | innings_1_death | 0.2564 | 0.1712 | 0.7179 |
| `mc_standalone_calibrated` | innings_1_middle | 0.2520 | 0.1263 | 0.7037 |
| `mc_standalone_calibrated` | innings_1_powerplay | 0.2677 | 0.1273 | 0.7343 |
| `mc_standalone_calibrated` | innings_2 | 0.1882 | 0.1675 | 0.5440 |
| `mc_standalone_calibrated` | innings_2_death | 0.1311 | 0.1513 | 0.4092 |
| `mc_standalone_calibrated` | innings_2_middle | 0.1795 | 0.1732 | 0.5161 |
| `mc_standalone_calibrated` | innings_2_powerplay | 0.2469 | 0.2744 | 0.6953 |
| `mc_standalone_calibrated` | overall | 0.2240 | 0.1096 | 0.6330 |
| `ml_add_mc_win_prob` | innings_1 | 0.2669 | 0.1780 | 0.7532 |
| `ml_add_mc_win_prob` | innings_1_death | 0.2609 | 0.2050 | 0.7427 |
| `ml_add_mc_win_prob` | innings_1_middle | 0.2650 | 0.2041 | 0.7454 |
| `ml_add_mc_win_prob` | innings_1_powerplay | 0.2760 | 0.2177 | 0.7768 |
| `ml_add_mc_win_prob` | innings_2 | 0.1837 | 0.1385 | 0.5524 |
| `ml_add_mc_win_prob` | innings_2_death | 0.1479 | 0.1635 | 0.4605 |
| `ml_add_mc_win_prob` | innings_2_middle | 0.1762 | 0.1714 | 0.5302 |
| `ml_add_mc_win_prob` | innings_2_powerplay | 0.2243 | 0.1921 | 0.6615 |
| `ml_add_mc_win_prob` | overall | 0.2269 | 0.1225 | 0.6566 |
| `ml_add_mc_gap_features` | innings_1 | 0.2632 | 0.2113 | 0.7420 |
| `ml_add_mc_gap_features` | innings_1_death | 0.2591 | 0.2486 | 0.7343 |
| `ml_add_mc_gap_features` | innings_1_middle | 0.2609 | 0.2240 | 0.7335 |
| `ml_add_mc_gap_features` | innings_1_powerplay | 0.2714 | 0.2329 | 0.7649 |
| `ml_add_mc_gap_features` | innings_2 | 0.1922 | 0.1569 | 0.5767 |
| `ml_add_mc_gap_features` | innings_2_death | 0.1545 | 0.1637 | 0.4798 |
| `ml_add_mc_gap_features` | innings_2_middle | 0.1849 | 0.1532 | 0.5547 |
| `ml_add_mc_gap_features` | innings_2_powerplay | 0.2339 | 0.2289 | 0.6897 |
| `ml_add_mc_gap_features` | overall | 0.2288 | 0.1492 | 0.6620 |
| `ml_replace_resource_with_mc` | innings_1 | 0.2684 | 0.1837 | 0.7562 |
| `ml_replace_resource_with_mc` | innings_1_death | 0.2622 | 0.2191 | 0.7451 |
| `ml_replace_resource_with_mc` | innings_1_middle | 0.2649 | 0.2219 | 0.7449 |
| `ml_replace_resource_with_mc` | innings_1_powerplay | 0.2806 | 0.2278 | 0.7867 |
| `ml_replace_resource_with_mc` | innings_2 | 0.1848 | 0.1375 | 0.5531 |
| `ml_replace_resource_with_mc` | innings_2_death | 0.1474 | 0.1542 | 0.4578 |
| `ml_replace_resource_with_mc` | innings_2_middle | 0.1787 | 0.1476 | 0.5343 |
| `ml_replace_resource_with_mc` | innings_2_powerplay | 0.2241 | 0.2170 | 0.6591 |
| `ml_replace_resource_with_mc` | overall | 0.2282 | 0.1259 | 0.6585 |
| `ml_clean_swap_resource` | innings_1 | 0.2629 | 0.2056 | 0.7404 |
| `ml_clean_swap_resource` | innings_1_death | 0.2596 | 0.2449 | 0.7331 |
| `ml_clean_swap_resource` | innings_1_middle | 0.2618 | 0.2259 | 0.7352 |
| `ml_clean_swap_resource` | innings_1_powerplay | 0.2682 | 0.2150 | 0.7568 |
| `ml_clean_swap_resource` | innings_2 | 0.1926 | 0.1477 | 0.5760 |
| `ml_clean_swap_resource` | innings_2_death | 0.1566 | 0.1533 | 0.4809 |
| `ml_clean_swap_resource` | innings_2_middle | 0.1860 | 0.1559 | 0.5563 |
| `ml_clean_swap_resource` | innings_2_powerplay | 0.2319 | 0.2120 | 0.6834 |
| `ml_clean_swap_resource` | overall | 0.2289 | 0.1465 | 0.6608 |

---

## Feature Importance (MC Features)

| Variant | Feature | Mean Importance |
|---------|---------|-----------------|
| `ml_add_mc_gap_features` | `mc_win_prob` | 0.1064 |
| `ml_add_mc_gap_features` | `mc_simulation_std` | 0.0264 |
| `ml_add_mc_gap_features` | `mc_resource_gap` | 0.0116 |
| `ml_add_mc_gap_features` | `mc_resource_abs_gap` | 0.0109 |
| `ml_add_mc_win_prob` | `mc_win_prob` | 0.1169 |
| `ml_replace_resource_with_mc` | `mc_win_prob` | 0.0975 |
| `ml_replace_resource_with_mc` | `mc_simulation_std` | 0.0236 |
| `ml_replace_resource_with_mc` | `mc_resource_gap` | 0.0120 |
| `ml_replace_resource_with_mc` | `mc_resource_abs_gap` | 0.0088 |

---

## Promotion Gate Results

- **ml_add_mc_win_prob**: ❌ FAIL
- **ml_add_mc_gap_features**: ✅ PASS
- **ml_replace_resource_with_mc**: ❌ FAIL
- **ml_clean_swap_resource**: ❌ FAIL

**Failure reasons:**
- [ml_add_mc_win_prob] Segment innings_1_powerplay Brier worsened by +0.0071
- [ml_replace_resource_with_mc] Segment innings_1_powerplay Brier worsened by +0.0118
- [ml_clean_swap_resource] ECE worsened (delta=+0.0005)

---

## Recommendation

✅ **Candidate variant**: `ml_add_mc_gap_features` passed all promotion gates.
Consider creating `models/ipl_v7_mc_features_candidate/` and running a live dry run.

---

## Inference Latency Risk

Adding MC feature generation before ML prediction introduces latency.

| Component | Estimated Latency | Notes |
|-----------|-------------------|-------|
| Baseline IPL v6 ML prediction | ~5–15 ms | feature store + model |
| MC simulation (500 sims, 6 balls) | ~200–600 ms | per ball state |
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