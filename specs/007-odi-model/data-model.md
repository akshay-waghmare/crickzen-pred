# Data Model: ODI Win Probability Model

**Feature**: 007-odi-model  
**Date**: 2026-02-20

## Entities

### FormatConfig (New)

A frozen dataclass representing all format-specific constants for cricket win probability calculation.

| Field | Type | T20 Default | ODI Male (estimated) | ODI Female (estimated) | Description |
|-------|------|-------------|---------------------|----------------------|-------------|
| `format_name` | `str` | `"t20"` | `"odi"` | `"odi"` | Format identifier |
| `gender` | `str` | `"male"` | `"male"` | `"female"` | Gender context |
| `total_overs` | `int` | `20` | `50` | `50` | Overs per innings |
| `total_balls` | `int` | `120` | `300` | `300` | Balls per innings |
| `balls_per_over` | `int` | `6` | `6` | `6` | Balls per over |
| `total_wickets` | `int` | `10` | `10` | `10` | Max wickets |
| `par_score` | `float` | `160.0` | *empirical* | *empirical* | Average 1st innings score |
| `league_avg_score` | `float` | `165.0` | *empirical* | *empirical* | League average for SQI |
| `bat_first_win_rate` | `float` | `0.37` | *empirical* | *empirical* | Historical bat-first win rate |
| `phase_thresholds` | `dict[str, int]` | `{pp:6, mid:14, death:18, final:20}` | `{pp:10, mid:34, setup:40, death:50}` | same | Phase boundary over numbers |
| `phase_names` | `list[str]` | `[pp,mid,death,final]` | `[pp,mid,setup,death]` | same | Phase name labels |
| `expected_run_rates` | `dict[str, float]` | `{pp:7.5, mid:7.8, death:9.5, final:11.0}` | *empirical* | *empirical* | Expected RR per phase |
| `ease_thresholds` | `dict[str, float]` | `{well_ahead:1.15, ahead:1.05, par:0.95, behind:0.85, well_behind:0.0}` | same | same | CRR/ExpectedRR ratio thresholds |
| `dls_resource_table` | `dict[int, dict[int, float]]` | 10×6 grid (20 overs) | 10×11 grid (50 overs) | *empirical* | Wickets → {overs_rem: resource_%} |
| `first_innings_wicket_penalty_3d` | `dict` | 4×5×11 (BBL empirical) | 4×5×11 (ODI empirical) | *empirical* | Phase→ease→wickets→penalty |
| `chase_wicket_penalty_2d` | `dict` | 5×11 (BBL empirical) | 5×11 (ODI empirical) | *empirical* | Chase_ease→wickets→penalty |
| `chase_ease_thresholds` | `dict[str, float]` | `{very_easy:3.0, easy:1.5, comfortable:1.0, tough:0.7, desperate:0.0}` | *empirical* | *empirical* | CRR/RRR ratio thresholds for chase |
| `rrr_midpoint` | `float` | `9.5` | *empirical* (~6.0) | *empirical* | RRR where chase win_prob = 50% |
| `rrr_beta` | `float` | `0.7` | *empirical* | *empirical* | Chase RRR logistic steepness |
| `sqi_beta` | `float` | `0.75` | *empirical* | *empirical* | SQI → win prob sigmoid steepness |
| `sqi_shift` | `float` | `0.35` | *empirical* | *empirical* | SQI center shift for bat-first disadvantage |
| `confidence_full_overs` | `float` | `12.0` | *empirical* (~25) | *empirical* | Overs until full model confidence |
| `score_std_early` | `float` | `15.0` | *empirical* | *empirical* | Projected score std dev (early overs) |
| `score_std_late` | `float` | `26.0` | *empirical* | *empirical* | Projected score std dev (late overs) |
| `score_cap_min` | `float` | `100.0` | `100.0` | `50.0` | Min projected score bound |
| `score_cap_max` | `float` | `280.0` | `500.0` | `350.0` | Max projected score bound |
| `endgame_balls` | `int` | `12` | `30` | `30` | Balls threshold for endgame logic |
| `pressure_rrr_min` | `float` | `7.0` | *empirical* (~4.0) | *empirical* | Min RRR for pressure scale |
| `pressure_rrr_max` | `float` | `15.0` | *empirical* (~10.0) | *empirical* | Max RRR for pressure scale |

*"empirical"* = determined by `scripts/analyze_odi_empirical.py` output.

### Validation Rules
- `total_balls == total_overs * balls_per_over`
- `total_wickets == 10`
- `len(phase_thresholds) == len(phase_names)`
- Last phase threshold == `total_overs`
- `0 < bat_first_win_rate < 1`
- `score_cap_min < par_score < score_cap_max`
- DLS table has entries for all 0..total_wickets keys
- Penalty tables have entries for all phase names

### State Transitions
`FormatConfig` is **immutable** (frozen dataclass). Created once at pipeline start, passed through all stages.

---

### League Config (Extended)

Existing league config dict with new `format_type` field:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `json_dir` | `str` | Yes | Source JSON directory |
| `raw_dir` | `str` | Yes | Ingested parquet directory |
| `features_dir` | `str` | Yes | Processed features directory |
| `feature_store_dir` | `str` | Yes | Feature store artifacts directory |
| `model_prefix` | `str` | Yes | Model directory prefix |
| `format_type` | `str` | Yes (default `'t20'`) | Cricket format: `'t20'` or `'odi'` |

**ODI entry example**:
```python
'odi': {
    'json_dir': 'odis_json',
    'raw_dir': 'data/odi_raw',
    'features_dir': 'data/odi_features',
    'feature_store_dir': 'data/odi_feature_store',
    'model_prefix': 'odi',
    'format_type': 'odi',
}
```

---

### ODI Training Sample (Extended from T20)

Each row in `training.parquet` represents one ball state. ODI-specific additions:

| Column | Type | New? | Description |
|--------|------|------|-------------|
| `gender` | `str` | **NEW** | `"male"` or `"female"` — training feature |
| `is_setup` | `int` | **NEW** | Binary: 1 if overs 35-40 (ODI setup phase) |
| `match_type` | `str` | existing | `"ODI"` (was `"T20"`) |
| All other features | various | existing | Same 25 features used by T20 model |

The `gender` field is encoded as a binary feature (0=male, 1=female) for model training.

---

### Empirical Analysis Output

The analysis script produces `scripts/odi_empirical_constants.json`:

```json
{
  "male": {
    "par_score": 252.3,
    "league_avg_score": 255.0,
    "bat_first_win_rate": 0.48,
    "expected_run_rates": {"powerplay": 5.2, "middle": 4.8, "setup": 6.5, "death": 8.2},
    "dls_resource_table": {"0": {"0": 0.0, "5": 15.2, ...}, ...},
    "first_innings_wicket_penalty_3d": {...},
    "chase_wicket_penalty_2d": {...},
    "rrr_midpoint": 6.1,
    "sample_counts": {"total_matches": 2100, "total_balls": 420000}
  },
  "female": {
    "par_score": 195.0,
    ...
  }
}
```
