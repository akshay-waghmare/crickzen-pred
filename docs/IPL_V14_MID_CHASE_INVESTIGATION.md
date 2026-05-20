# IPL v14 MID Chase Investigation

Date: 2026-05-19

## Trigger

The live CSK vs SRH chase showed v14 underpredicting SRH through the innings-2 middle overs. SRH were set with Ishan Kishan and Heinrich Klaasen, the chase was accelerating, and market odds moved much faster than the model.

The main question was whether the problem came from:

- the base resource probability,
- the post-model calibration/router,
- missing set-batter and partnership features,
- or the MID model itself.

## What We Rejected

### Resource v2 is not promoted

We tested a context-adjusted resource baseline using chase context such as recent rate, wickets in hand, set batter exposure, and partnership solidity.

Finding:

- Standalone resource v2 improved the resource-only baseline.
- But replacing or adding it inside v14 did not cleanly beat current v14.
- MID became worse when the new resource value was used broadly.
- PP-only replacement improved Brier but worsened LogLoss.

Decision:

```text
Do not promote resource v2.
Keep current v14 resource feature in production.
```

## Router Finding

The post-model calibration router had a rule named:

```text
inn2_par_pp_mid
```

This rule is intended to lift compressed innings-2 chaser probabilities in par-target states when the model output is in the 50-80% range.

Initial broad idea:

```text
Allow the rule in PP and all MID par chases.
```

But OOS showed this was too broad.

Positive-par MID chases got worse when lifted broadly:

```text
v14_prod_raw positive-par MID gate:
Brier 0.24569 -> 0.28768
LogLoss 0.68540 -> 0.80304
```

Negative/easier-par MID chases improved:

```text
v14_prod_raw negative-par MID gate:
Brier 0.11256 -> 0.05802
LogLoss 0.39949 -> 0.25396
```

## Final Router Rule

The production router now supports phase-specific target-above-par bounds.

Final rule:

```text
PP:
  -20 <= target_above_par <= +20

MID:
  -20 <= target_above_par <= 0

Death:
  no par correction
```

The artifact now contains:

```python
allowed_phases = ["pp", "mid"]
phase_target_above_par_bounds = {"mid": [-20.0, 0.0]}
```

This intentionally does not apply a generic correction to positive-par MID states.

## SRH Case Implication

SRH target was around:

```text
target_above_par = +7.5
```

That means it is positive-par MID.

The narrowed router will not apply to that SRH-style state. This is intentional because broad OOS says positive-par MID lifts are risky.

To fix SRH-style positive-par MID underprediction, the next experiment should be feature-aware, likely gated by:

- low wickets lost,
- set batter exposure,
- partnership solidity,
- recent acceleration,
- chase completion,
- target still inside par bucket.

It should not be a broad probability-only MID lift.

## Set Batter And Partnership Features

The MID phase model already expects these features:

```text
balls_since_wicket
set_batter_exposure
partnership_solidity
```

So the model architecture was not missing them.

The issue found was in live feature visibility:

- The actual `Inn2PhaseRouter` engineers innings-2 features internally before prediction.
- But some live JSON and match-state logger feature snapshots were exporting the raw mapper row.
- That made `partnership_solidity` appear missing in diagnostics/logs even when the router computed it internally.

Fix:

```text
Apply innings-2 engineering to live feature snapshots and logger exports too.
```

This keeps the visible/debug feature row aligned with the row used by the router.

## Code Changes

Changed files:

- `src/bbl_pipeline/inference/post_model_calibration_router.py`
- `src/bbl_pipeline/inference/crex_live_predictor.py`
- `models/ipl_v14_pitch_features/post_model_calibration_router.pkl`
- `models/ipl_v14_pitch_features/routing_config.json`
- `tests/unit/test_post_model_calibration_router.py`
- `tests/unit/test_crex_live_predictor.py`
- `scripts/audit_ipl_v14_mid_correction.py`
- `docs/IPL_V14_PITCH_FEATURES.md`

Key behavior changes:

- Router supports `phase_target_above_par_bounds`.
- MID par correction is limited to `target_above_par <= 0`.
- Live JSON/logger snapshots now include engineered innings-2 features such as `partnership_solidity`.
- Audit script now prints match counts and flags small match samples.
- Tests guard against accidentally restoring broad positive-par MID correction.

## Verification

Targeted tests passed:

```powershell
python -m pytest tests\unit\test_post_model_calibration_router.py tests\unit\test_crex_live_predictor.py tests\unit\test_realtime_mapper_training_parity.py tests\test_inn2_phase_router.py
```

Result:

```text
26 passed
```

Only warning:

```text
.pytest_cache permission warning
```

## Current Production Recommendation

Use current v14 with the narrowed post-model router.

Do not promote:

- resource v2,
- broad MID par correction,
- positive-par MID probability-only lift.

Next work should focus on a separate SRH-style positive-par MID experiment with explicit feature gates, not a generic router lift.
