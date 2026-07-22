# Spec 022 — Generalized Innings/Phase Router Models

## Objective

Extend the combined `t20_all` and `odi_all` models using the validated IPL production architecture: one complete innings-1 model, then phase-specific innings-2 models selected only when out-of-sample evidence supports them.

## IPL architecture being generalized

The current IPL v17 production route is:

1. Innings 1: complete `ipl_v7` model.
2. Innings 2 powerplay: v17 PP model, raw output in production.
3. Innings 2 middle: v14 MID model, because v17 regressed on OOS data there.
4. Innings 2 death: v14 DEATH model, for the same evidence-based reason.
5. PP low-chase conditional fallback: v12 PP raw model when `target_above_par < -20`.
6. Guarded post-model calibration: applied only to validated probability/phase/chase buckets.

The key principle is a champion router, not a single globally promoted experiment.

## Generalized model tracks

### T20

- Innings 1: complete combined T20 model.
- Innings 2 powerplay: candidate phase model, overs 1–6.
- Innings 2 middle: candidate phase model, overs 7–15.
- Innings 2 death: candidate phase model, overs 16–20.

### ODI

- Innings 1: complete combined ODI model.
- Innings 2 powerplay: candidate phase model, overs 1–10.
- Innings 2 middle: candidate phase model, overs 11–34.
- Innings 2 setup: candidate phase model, overs 35–40.
- Innings 2 death: candidate phase model, overs 41–50.

## Promotion rules

For each format and innings-2 phase, compare the candidate against the current champion using chronological/OOS data:

- Brier score
- Log loss
- ECE/calibration
- Gender slices
- Match-level aggregation
- Market comparison where market data exists

Promote a phase candidate only when it wins on a held-out window and does not materially regress the other phase buckets. If not, retain the complete innings model for that phase.

## Required artifacts

Each promoted router must contain:

- `routing_config.json`
- complete innings-1 model reference
- phase model artifacts and feature lists
- phase OOF calibrators
- optional conditional fallback model/rule
- post-model calibration artifact and validation report
- OOS comparison report

## Non-goals

- Do not copy IPL constants directly into global T20/ODI models.
- Do not promote phase models based only on in-sample or overall aggregate gains.
- Do not use market data for fitting; use it for comparison and guarded validation.
