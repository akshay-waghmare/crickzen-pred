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
| `post_model_calibration_router.pkl` | Guardrailed post-model probability router for IPL v14 production display/output |
| `post_model_calibration_router_validation.json` | 2025-fit / 2026-holdout audit for the post-model router |

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

## Post-model calibration router

Raw v14 remains the production base. `routing_config.json` still has `apply_calibration=false`, because the broad OOF calibrators were not better than raw v14 for this production path. The new correction is a separate post-model router that only fires in the failure regions found in the OOS bucket analysis.

| Rule | Gate | Intent |
|---|---|---|
| `inn1_low_side` | Innings 1, probability `< 0.50` | Compress the active batting side downward only in the low-side region |
| `inn2_easy_chase` | Innings 2, `target_above_par < -20`, probability `0.50-0.85` | Sharpen chaser probabilities in easy/low-target chases |
| `inn2_par_pp_mid` | Innings 2, probability `0.50-0.80`; powerplay uses `-20 <= target_above_par <= 20`, middle uses `-20 <= target_above_par <= 0` | Sharpen compressed chaser favourites where OOS supports it |

Guardrails intentionally left mostly untouched:

- Inn1 probabilities `>= 0.50`
- Inn2 hard/high chases (`target_above_par > 20`)
- Inn2 90-100% chaser probabilities
- Inn2 death except where the easy-chase rule is already in-range
- Inn2 hard/high middle-over chases, which remain outside the par gate
- Inn2 positive-par middle-over chases, because broad OOS showed over-lifting there

Validation policy: fit the specialist calibrators on 2025 OOS-style predictions and validate on 2026 holdout. Key 2026 production-like holdout checks:

| Segment | n | Base Brier | Post-cal Brier | Change | Base LogLoss | Post-cal LogLoss | Change |
|---|---:|---:|---:|---:|---:|---:|---:|
| Overall all innings | 5,451 | 0.12727 | 0.11653 | -8.44% | 0.40477 | 0.37411 | -7.57% |
| Inn1 overall | 2,844 | 0.17026 | 0.15816 | -7.10% | 0.51699 | 0.48556 | -6.08% |
| Inn1 p<50 | 1,562 | 0.14272 | 0.12070 | -15.43% | 0.45465 | 0.39743 | -12.59% |
| Inn1 p>=50 guardrail | 1,282 | 0.20380 | 0.20380 | 0.00% | 0.59294 | 0.59294 | 0.00% |
| Inn2 overall | 2,607 | 0.08038 | 0.07111 | -11.53% | 0.28234 | 0.25252 | -10.56% |
| Inn2 50-80 | 653 | 0.13735 | 0.10225 | -25.56% | 0.45093 | 0.34021 | -24.55% |
| Inn2 easy | 632 | 0.08229 | 0.05549 | -32.56% | 0.28456 | 0.19176 | -32.61% |
| Inn2 easy 50-85 | 256 | 0.07803 | 0.01188 | -84.77% | 0.31517 | 0.08608 | -72.69% |
| Inn2 par PP 50-80 | 116 | 0.12377 | 0.06142 | -50.38% | 0.42649 | 0.26197 | -38.58% |
| Inn2 par Mid 50-80 guardrail | 101 | 0.16755 | 0.16755 | 0.00% | 0.51364 | 0.51364 | 0.00% |
| Inn2 hard guardrail | 1,323 | 0.06480 | 0.06480 | 0.00% | 0.24269 | 0.24269 | 0.00% |
| Inn2 death guardrail | 482 | 0.03987 | 0.03821 | -4.17% | 0.14863 | 0.14236 | -4.22% |
| Inn2 90-100 guardrail | 512 | 0.00302 | 0.00302 | 0.00% | 0.04960 | 0.04960 | 0.00% |

Phase-wise 2026 production-like holdout:

| Segment | Phase | n | Base Brier | Post-cal Brier | Change | Base LogLoss | Post-cal LogLoss | Change |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Inn1 | Powerplay | 873 | 0.18551 | 0.17848 | -3.79% | 0.55259 | 0.53376 | -3.41% |
| Inn1 | Middle | 1,271 | 0.16889 | 0.15494 | -8.26% | 0.51353 | 0.47723 | -7.07% |
| Inn1 | Death | 700 | 0.15371 | 0.13869 | -9.77% | 0.47888 | 0.44057 | -8.00% |
| Inn2 | Powerplay | 863 | 0.10770 | 0.08986 | -16.57% | 0.36844 | 0.31438 | -14.67% |
| Inn2 | Middle | 1,262 | 0.07717 | 0.07086 | -8.18% | 0.27453 | 0.25229 | -8.10% |
| Inn2 | Death | 482 | 0.03987 | 0.03821 | -4.17% | 0.14863 | 0.14236 | -4.22% |

Production integration:

- `crex_live_predictor` loads `post_model_calibration_router.pkl` only when the active router config enables it.
- The live JSON includes `post_model_calibration_rule`, `post_model_calibration_input_prob`, and `post_model_calibration_prob`.
- Streamlit shows a separate `Post-Cal` card only when a gate changes the probability, similar to the separate Shadow T card.
- Match-state logging records `model_post_calibrated` and `model_post_calibration_rule` for later audit.

## Failed post-v14 experiments

v14 remains the IPL champion. Two follow-up context-resource experiments were run to address the favourite/underdog compression problem:

- true 85-88% favourites were often shown around 70-75%
- true 12-15% underdogs were often shown around 25-30%

Both experiments were intentionally reversible and did not change production wiring.

### v15 context resource

Artifact directory: `models/ipl_v15_context_resource`

Formula tested:

```text
logit(resource_context_win_prob)
  = logit(resource_win_prob) + contextual_adjustment
```

Context features were deliberately limited to:

- `venue_chase_success`
- `team_strength_diff`
- `target_above_venue_par`
- `pp_score_vs_venue`
- `death_rr_vs_venue`
- `toss_batting_or_chasing_context`

Candidates tested:

| Candidate | OOS Brier | Brier delta vs v14 | OOS LogLoss | LogLoss delta vs v14 | 70-80 bucket | Guardrails | Verdict |
|---|---:|---:|---:|---:|---|---|---|
| v14 original | 0.11175 | 0.00% | 0.37431 | 0.00% | Baseline | Pass | Champion |
| v15 add context resource | 0.11190 | +0.13% | 0.37622 | +0.51% | Improved | Fail | Reject |
| v15 replace resource | 0.11257 | +0.74% | 0.37793 | +0.97% | Improved | Fail | Reject |

Finding: the context-resource feature improved the exact 70-80 favourite compression bucket, but worsened overall OOS Brier/LogLoss and damaged the 50-60 / 80%+ guardrails. Do not promote.

### v16 context resource interactions

Artifact directory: `models/ipl_v16_context_interactions`

Formula tested:

```text
logit(resource_context_interaction_prob)
  = logit(resource_win_prob)
  + phase_adjustment
  + venue_regime_adjustment
  + phase x venue_regime
  + target_bucket x venue_regime
```

The interaction set was intentionally narrow:

- phase: PP / MID / DEATH
- venue regime: low / neutral / high chase
- target bucket: low / par / high
- `venue_regime x phase`
- `venue_regime x target_bucket`
- `boundary_signal x DEATH`
- `pp_score_vs_venue x PP`

Candidates tested:

| Candidate | OOS Brier | Brier delta vs v14 | OOS LogLoss | LogLoss delta vs v14 | 70-80 bucket | PP ECE | Guardrails | Verdict |
|---|---:|---:|---:|---:|---|---:|---|---|
| v14 original | 0.11175 | 0.00% | 0.37431 | 0.00% | Baseline | 0.13332 | Pass | Champion |
| v16 A add interaction prob | 0.11353 | +1.60% | 0.37985 | +1.48% | Improved | 0.12350 | Fail | Reject |
| v16 B replace resource | 0.11248 | +0.65% | 0.38171 | +1.98% | Improved | 0.12644 | Fail | Reject |
| v16 C both plus regimes | 0.11308 | +1.19% | 0.37691 | +0.69% | Best improvement | 0.11831 | Fail | Reject |

Finding: v16 improved the 70-80 favourite bucket more than v15, and PP ECE improved, but the overall OOS probability quality worsened. This confirms that better global or broad interaction context-resource adjustments are not the right production path.

### Conclusion for future work

Keep `models/ipl_v14_pitch_features` as champion. Archive v15/v16 as useful failed experiments. The bounded specialist correction path is now implemented as the post-model calibration router above, rather than another global resource-context prior.

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
| Post-model router | Added guarded Inn1 low-side, Inn2 easy-chase, and Inn2 par-powerplay probability correction without enabling global calibration |
| Live display | Added separate Streamlit `Post-Cal` card and live JSON fields, while keeping Shadow T separate |
| State logging | Added post-calibrated probability and rule fields to match-state Parquet schema |

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
