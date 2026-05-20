# IPL MC Features Experiment — Results Report

**Generated**: 2026-04-27 14:58 UTC  
**Mode**: `pilot`  
**MC settings**: n_sims=200, horizon_balls=6  
**Evaluator**: resource-based (no ML model, apply_temp=False)  

---

## Overall OOF Metrics

| Method | N | Brier | ECE | LogLoss | ΔBrier | ΔECE | ΔLogLoss |
|--------|---|-------|-----|---------|--------|------|----------|
| `baseline_ipl_v6_features` | 2316 | 0.2326 | 0.1277 | 0.6705 | +0.0000 | +0.0000 | +0.0000 |
| `mc_standalone_calibrated` | 2316 | 0.2241 | 0.0612 | 0.6330 | -0.0084 | -0.0665 | -0.0375 |
| `ml_add_mc_win_prob` | 2316 | 0.2268 | 0.0996 | 0.6569 | -0.0058 | -0.0281 | -0.0135 |
| `ml_add_mc_gap_features` | 2316 | 0.2293 | 0.1183 | 0.6635 | -0.0032 | -0.0095 | -0.0070 |
| `ml_replace_resource_with_mc` | 2316 | 0.2276 | 0.1075 | 0.6571 | -0.0049 | -0.0203 | -0.0133 |
| `ml_clean_swap_resource` | 2316 | 0.2281 | 0.1227 | 0.6591 | -0.0045 | -0.0051 | -0.0114 |

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
| `mc_standalone_calibrated` | innings_1 | 0.2572 | 0.1175 | 0.7152 |
| `mc_standalone_calibrated` | innings_1_death | 0.2566 | 0.1791 | 0.7185 |
| `mc_standalone_calibrated` | innings_1_middle | 0.2518 | 0.1264 | 0.7031 |
| `mc_standalone_calibrated` | innings_1_powerplay | 0.2678 | 0.1330 | 0.7345 |
| `mc_standalone_calibrated` | innings_2 | 0.1884 | 0.1632 | 0.5441 |
| `mc_standalone_calibrated` | innings_2_death | 0.1317 | 0.1464 | 0.4085 |
| `mc_standalone_calibrated` | innings_2_middle | 0.1798 | 0.1772 | 0.5168 |
| `mc_standalone_calibrated` | innings_2_powerplay | 0.2468 | 0.2680 | 0.6948 |
| `mc_standalone_calibrated` | overall | 0.2241 | 0.1110 | 0.6330 |
| `ml_add_mc_win_prob` | innings_1 | 0.2679 | 0.1781 | 0.7563 |
| `ml_add_mc_win_prob` | innings_1_death | 0.2614 | 0.2075 | 0.7454 |
| `ml_add_mc_win_prob` | innings_1_middle | 0.2662 | 0.2006 | 0.7490 |
| `ml_add_mc_win_prob` | innings_1_powerplay | 0.2769 | 0.2166 | 0.7791 |
| `ml_add_mc_win_prob` | innings_2 | 0.1824 | 0.1427 | 0.5498 |
| `ml_add_mc_win_prob` | innings_2_death | 0.1464 | 0.1485 | 0.4573 |
| `ml_add_mc_win_prob` | innings_2_middle | 0.1748 | 0.1646 | 0.5273 |
| `ml_add_mc_win_prob` | innings_2_powerplay | 0.2232 | 0.1961 | 0.6600 |
| `ml_add_mc_win_prob` | overall | 0.2268 | 0.1302 | 0.6569 |
| `ml_add_mc_gap_features` | innings_1 | 0.2634 | 0.2099 | 0.7418 |
| `ml_add_mc_gap_features` | innings_1_death | 0.2599 | 0.2562 | 0.7351 |
| `ml_add_mc_gap_features` | innings_1_middle | 0.2613 | 0.2262 | 0.7338 |
| `ml_add_mc_gap_features` | innings_1_powerplay | 0.2706 | 0.2283 | 0.7631 |
| `ml_add_mc_gap_features` | innings_2 | 0.1930 | 0.1570 | 0.5801 |
| `ml_add_mc_gap_features` | innings_2_death | 0.1557 | 0.1670 | 0.4833 |
| `ml_add_mc_gap_features` | innings_2_middle | 0.1853 | 0.1514 | 0.5569 |
| `ml_add_mc_gap_features` | innings_2_powerplay | 0.2351 | 0.2304 | 0.6949 |
| `ml_add_mc_gap_features` | overall | 0.2293 | 0.1506 | 0.6635 |
| `ml_replace_resource_with_mc` | innings_1 | 0.2683 | 0.1815 | 0.7555 |
| `ml_replace_resource_with_mc` | innings_1_death | 0.2617 | 0.2168 | 0.7442 |
| `ml_replace_resource_with_mc` | innings_1_middle | 0.2649 | 0.2107 | 0.7444 |
| `ml_replace_resource_with_mc` | innings_1_powerplay | 0.2805 | 0.2329 | 0.7860 |
| `ml_replace_resource_with_mc` | innings_2 | 0.1838 | 0.1405 | 0.5511 |
| `ml_replace_resource_with_mc` | innings_2_death | 0.1475 | 0.1391 | 0.4576 |
| `ml_replace_resource_with_mc` | innings_2_middle | 0.1773 | 0.1546 | 0.5314 |
| `ml_replace_resource_with_mc` | innings_2_powerplay | 0.2231 | 0.2112 | 0.6572 |
| `ml_replace_resource_with_mc` | overall | 0.2276 | 0.1293 | 0.6571 |
| `ml_clean_swap_resource` | innings_1 | 0.2618 | 0.2059 | 0.7379 |
| `ml_clean_swap_resource` | innings_1_death | 0.2577 | 0.2346 | 0.7291 |
| `ml_clean_swap_resource` | innings_1_middle | 0.2607 | 0.2243 | 0.7327 |
| `ml_clean_swap_resource` | innings_1_powerplay | 0.2677 | 0.2228 | 0.7560 |
| `ml_clean_swap_resource` | innings_2 | 0.1921 | 0.1465 | 0.5750 |
| `ml_clean_swap_resource` | innings_2_death | 0.1568 | 0.1548 | 0.4811 |
| `ml_clean_swap_resource` | innings_2_middle | 0.1853 | 0.1462 | 0.5548 |
| `ml_clean_swap_resource` | innings_2_powerplay | 0.2314 | 0.2088 | 0.6824 |
| `ml_clean_swap_resource` | overall | 0.2281 | 0.1419 | 0.6591 |

---

## Feature Importance (MC Features)

| Variant | Feature | Mean Importance |
|---------|---------|-----------------|
| `ml_add_mc_gap_features` | `mc_win_prob` | 0.1124 |
| `ml_add_mc_gap_features` | `mc_simulation_std` | 0.0245 |
| `ml_add_mc_gap_features` | `mc_resource_gap` | 0.0117 |
| `ml_add_mc_gap_features` | `mc_resource_abs_gap` | 0.0112 |
| `ml_add_mc_win_prob` | `mc_win_prob` | 0.1170 |
| `ml_replace_resource_with_mc` | `mc_win_prob` | 0.0991 |
| `ml_replace_resource_with_mc` | `mc_simulation_std` | 0.0223 |
| `ml_replace_resource_with_mc` | `mc_resource_gap` | 0.0117 |
| `ml_replace_resource_with_mc` | `mc_resource_abs_gap` | 0.0096 |

---

## Promotion Gate Results

- **ml_add_mc_win_prob**: ❌ FAIL
- **ml_add_mc_gap_features**: ✅ PASS
- **ml_replace_resource_with_mc**: ❌ FAIL
- **ml_clean_swap_resource**: ✅ PASS

**Failure reasons:**
- [ml_add_mc_win_prob] Segment innings_1_powerplay Brier worsened by +0.0080
- [ml_replace_resource_with_mc] Segment innings_1_powerplay Brier worsened by +0.0117

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
| MC simulation (200 sims, 6 balls) | ~200–600 ms | per ball state |
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