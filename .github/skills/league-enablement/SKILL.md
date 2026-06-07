---
name: league-enablement
description: Use this when auditing, enabling, wiring, or validating a cricket league model for launcher, live prediction, and Streamlit dashboard use.
---

Use this skill when the task is about onboarding or validating a league such as NTB, BBL, IPL, PSL, SA20, ILT20, WPL, SSM, BPL, or a new T20/ODI league.

This repository already provides extension tools for this workflow:

- `audit_league_model`
- `wire_league_live`

Follow this process.

## 1. Identify league inputs

Collect or infer:

- league key for UI/config surfaces, for example `NTB`
- league code for predictor/runtime usage, for example `ntb`
- model directory, for example `models/ntb_v1_phase`
- feature store directory, for example `data/ntb_feature_store_v1`
- live output JSON stem, for example `data/ntb_live_ml.json`
- CREX URL patterns used for league auto-detection

If the user did not supply all of these, inspect the repository and model registry before changing anything.

## 2. Audit before wiring

Always run `audit_league_model` first.

Audit goals:

- verify model artifacts exist
- verify feature store exists
- detect whether the model is a single model or an innings-2 phase router
- collect OOF and OOS metrics when available
- inspect calibration structure and artifact completeness
- identify warnings before any launcher/dashboard wiring

If the audit reports missing artifacts, missing feature store files, or broken router structure, stop and report that before editing application surfaces.

## 3. Interpret the model architecture

Check whether the model is:

1. a standard single-model setup, or
2. an innings-2 routed architecture with `routing_config.json`

For routed models, confirm:

- `inn1_model_dir` exists
- `inn2_phase_model_dir` exists
- phase model artifacts exist for `pp`, `mid`, and `death`
- phase calibrator artifacts exist if the router expects them

When describing the model, be explicit about whether it follows the IPL-style pattern of:

- innings 1 using a base model
- innings 2 using phase-specific routing

## 4. Wire live surfaces only after audit passes

When the audit is acceptable, run `wire_league_live` with the resolved league inputs.

The expected wiring targets are:

- `scripts/launcher.py`
- `dashboard/app/config.py`
- `src/bbl_pipeline/app/live_streamlit_app.py`

The intent is to make the league usable from:

- launcher league selection
- launcher URL auto-detection
- live Streamlit managed predictor controls
- Streamlit JSON source selection
- shared dashboard league configuration

## 5. Verify runtime behavior

After wiring, verify the league can actually be used.

Minimum checks:

1. the configured model path is loadable for the real runtime path
2. if it is a router model, confirm the runtime loads the innings-1 base model and then attaches the innings-2 router
3. launcher output JSON naming is consistent for normal and MC-only runs
4. Streamlit can select the league output JSON path
5. dashboard/shared config contains the same league mapping

Do not assume `Predictor.load(model_dir)` alone is the right validation for router models. If the router is loaded via `crex_live_predictor`, validate the actual routing load path.

## 6. Report the outcome clearly

Summarize:

- what was audited
- the important OOF and OOS metrics found
- whether the model is single-model or routed
- what files were wired
- whether the league is ready for launcher plus Streamlit use
- any remaining warnings or follow-up work

## Example usage

Use this skill for prompts like:

- "enable NTB live in launcher and Streamlit"
- "audit the new Blast model and wire it"
- "check if this league follows IPL v17 architecture"
- "make the new league launchable from scripts/launcher.py"

## Important behavior

- Prefer the extension tools over redoing the same audit logic manually.
- Audit first, wire second.
- If metrics or artifacts look suspicious, say so plainly instead of presenting the league as production-ready.
