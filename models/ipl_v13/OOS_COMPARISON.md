# IPL v13 — OOS Comparison Report

**Train seasons:** ['2007/08', '2009', '2009/10', '2011', '2012', '2013', '2014', '2015', '2016', '2017', '2018', '2019', '2020/21', '2021', '2022', '2023', '2024']
**Test seasons:** ['2025', '2026']

## v13 feature updates
- **EDA early removal candidates (14):** rescue_needed_flag, critical_wicket_zone, dls_pressure_index, wickets_remaining, run_rate_diff, resource_pct, wicket_pressure, rrr_times_wickets, wicket_adj_momentum, momentum_vs_rrr, score_per_wicket, momentum_x_wickets, batting_pair_momentum, runs_last_12
- **EDA late removal candidates (3):** pressure_momentum_gap, chase_category, target_above_par
- **Final Early-MID removals (0):** None (OOS screening kept the baseline MID core)
- **Early-MID additions (3):** target_clarity_index, early_settle_flag, chase_on_track_score
- **Final Late-MID removals (0):** None (OOS screening kept the baseline MID core)
- **Late-MID additions (3):** late_mid_urgency, late_mid_run_gap, late_wkt_collapse_risk

## OOS segment comparison

| Segment | v12 baseline | v13 split | Delta | v12 raw | v13 raw | n |
|---------|-------------:|----------:|------:|--------:|--------:|--:|
| PP | 0.14589 | 0.14589 | +0.00% | 0.14423 | 0.14423 | 3,481 |
| Early-MID | 0.12136 | 0.12195 | +0.49% | 0.12039 | 0.12125 | 2,856 |
| Late-MID | 0.08168 | 0.08929 | +9.32% | 0.08103 | 0.08803 | 2,194 |
| Combined MID | 0.10412 | 0.10776 | +3.50% | 0.10329 | 0.10682 | 5,050 |
| Death | 0.06809 | 0.06809 | +0.00% | 0.06624 | 0.06624 | 1,516 |
| Overall | 0.11316 | 0.11499 | +1.62% | 0.11188 | 0.11366 | 0 |

**Combined MID verdict:** Regressed (+3.50%)
