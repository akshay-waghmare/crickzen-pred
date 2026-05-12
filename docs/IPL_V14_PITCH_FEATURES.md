# IPL v14 Pitch Features

IPL production now uses `models/ipl_v14_pitch_features` as the active innings-2 phase router. Innings 1 remains the existing `models/ipl_v7` base model via `routing_config.json`; innings 2 routes to v14 PP/MID/DEATH phase models.

This model does not replace or rewrite the resource calculator. The resource calculator still produces stable base columns such as `resource_win_prob`, `score_vs_par`, `dls_pressure_index`, `resources_remaining`, and `chase_difficulty`. v14 retrains the innings-2 ML phase models so they can learn how to adjust those resource/scoreboard signals using first-innings pitch context.

## Active production model

| Surface | Active value |
|---|---|
| Registry key | `active_models.IPL` and lowercase `active_models.ipl` |
| Router directory | `models/ipl_v14_pitch_features` |
| Innings 1 model | `models/ipl_v7` |
| Innings 2 router | `models/ipl_v14_pitch_features` |
| Feature store | `data/ipl_feature_store_v9` |
| Build script | `scripts/build_ipl_v14_pitch_features.py` |
| Main docs | `docs/IPL_V14_PITCH_FEATURES.md` |

The router artifacts are:

| Artifact | Purpose |
|---|---|
| `routing_config.json` | Declares v7 for innings 1 and v14 phase routing for innings 2 |
| `champion_model_pp.joblib` | Innings-2 powerplay model |
| `champion_model_mid.joblib` | Innings-2 middle-overs model |
| `champion_model_death.joblib` | Innings-2 death-overs model |
| `phase_features.json` | Exact feature list per phase |
| `phase_oof_calibrators.pkl` | Phase/per-over OOF calibration bundles |
| `venue_pitch_baselines.json` | Venue baselines used live to create relative first-innings pitch features |
| `oos_comparison.csv` | v12 vs v14 OOS comparison |
| `oof_results.csv` | v14 OOF phase metrics |
| `pitch_partnership_eda_correlations.csv` | EDA correlations for extra pitch/partnership candidates |
| `pitch_partnership_eda_groups.csv` | EDA group summary used to choose the selective death features |

## Feature changes vs v12

| Phase | Added features | Purpose |
|---|---|---|
| PP | `pp_score_vs_venue`, `pp_wkts_vs_venue`, `death_rr_vs_venue`, `death_wkts_vs_venue` | First-innings pitch read versus venue baseline |
| MID | `pp_wkts_vs_venue` | Venue-normalized PP damage signal |
| DEATH | `inn1_pp_wickets`, `mid_avg_boundary18_vs_venue`, `avg_boundary18_vs_venue` | PP wicket damage plus boundary-freedom pitch read |

`avg_boundary18_vs_venue` and `mid_avg_boundary18_vs_venue` measure how boundary-friendly the first innings was compared with normal conditions at the same venue. Positive values mean boundaries were easier than venue average; negative values mean the pitch/conditions suppressed boundaries.

These features are ML inputs, not resource-calculator inputs:

1. `crex_live_predictor` computes first-innings carryover and venue-relative pitch fields.
2. `realtime_mapper` forwards those fields into the live feature dataframe.
3. `Inn2PhaseRouter` selects the PP/MID/DEATH model and fills its phase-specific feature list.
4. The phase model combines resource features plus v14 pitch features to produce the innings-2 probability.

This separation is intentional. The resource model remains stable and interpretable; the retrained ML router learns when to move above or below the resource baseline based on pitch/venue evidence from the first innings.

## OOS comparison

Standard split: train seasons `<2025`, test seasons `2025` and `2026`.

| Phase | v12 calibrated Brier | v14 calibrated Brier | Change |
|---|---:|---:|---:|
| PP | 0.14589 | 0.14382 | -1.42% |
| MID | 0.10412 | 0.10370 | -0.41% |
| DEATH | 0.06809 | 0.06493 | -4.63% |
| Overall | 0.11316 | 0.11175 | -1.24% |

Raw Brier also improved overall: `0.11188 -> 0.10988`.

## What changed in this stage

This stage promoted the selective v15 death improvement into v14 and kept only v14 as the production model.

| Area | Change |
|---|---|
| Model artifacts | Rebuilt `models/ipl_v14_pitch_features` with PP/MID v14 pitch features plus the selective death boundary features from v15 |
| v15 cleanup | Removed separate v15 candidate artifacts/scripts after merging useful death features into v14 |
| Registry | Updated `models/model_registry.json` so IPL active model paths point to `models/ipl_v14_pitch_features` |
| Desktop launcher | Updated IPL `model_dir` and `inn2_model_dir` to `models/ipl_v14_pitch_features` |
| Dashboard config | Updated IPL `model_dir` to `models/ipl_v14_pitch_features` |
| Streamlit app | Updated IPL prediction configs and user-facing router note to v14 |
| Live predictor | Added live calculation of PP/death venue-relative features and boundary-freedom features from first-innings ball history |
| betx21 fallback | Added PP/death wicket extraction so mid-chase starts can still populate v14 carryover fields when score snapshots are available |
| Realtime mapper | Added v14 carryover columns to the live feature dictionary |
| Router docs | Updated `Inn2PhaseRouter` docstring/example to reference v14 |
| Tests | Updated realtime mapper parity test for the training boundary-rate definition |

## Production wiring

- Desktop launcher IPL config points `model_dir` to `models/ipl_v14_pitch_features`.
- Dashboard IPL config points `model_dir` to `models/ipl_v14_pitch_features`.
- Streamlit IPL configs point `model_dir` to `models/ipl_v14_pitch_features`.
- `model_registry.json` marks `IPL` and lowercase `ipl` as `v14_pitch_features`.
- `crex_live_predictor` loads `venue_pitch_baselines.json` from the active router directory and computes the live venue-relative carryover features from first-innings ball history.
- `realtime_mapper` forwards the v14 feature fields into the router feature dictionary.
- If ball history is unavailable after starting mid-chase, `fetch_betx21_inn1_stats.py` can recover first-innings PP/death score and wicket fields from betx21 score progression where available.

## Rebuild command

```bash
python scripts/build_ipl_v14_pitch_features.py
```

The build writes:

- `champion_model_pp.joblib`
- `champion_model_mid.joblib`
- `champion_model_death.joblib`
- `phase_features.json`
- `phase_oof_calibrators.pkl`
- `venue_pitch_baselines.json`
- `oos_comparison.csv`
- `oof_results.csv`
