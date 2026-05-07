# IPL v12 — OOS Comparison Report
**Train seasons:** ['2007/08', '2009', '2009/10', '2011', '2012', '2013', '2014', '2015', '2016', '2017', '2018', '2019', '2020/21', '2021', '2022', '2023', '2024']
**Test seasons:** ['2025', '2026']

## Changes vs v11
- **PP model**: +5 easy-chase features (`pp_ease_score`, `pp_rrr_ease`, `chase_ease_x_venue`, `low_target_strong_venue`, `pp_resources_adj_ease`)
- **MID calibration**: Platt scaling (log-loss optimal) instead of per-over isotonic (which degenerates on small val sets)
- **Death**: unchanged

## Results

| Phase | v11 cal | v12 cal | Change |
|-------|---------|---------|--------|
| **Overall** | 0.11313 | 0.11325 | **+0.1%** |
| PP | 0.14602 | 0.14637 | +0.2% |
| MID | 0.10415 | 0.10415 | +0.0% |
| DEATH | 0.06752 | 0.06752 | +0.0% |

**Verdict: KEEP v11 as champion**
