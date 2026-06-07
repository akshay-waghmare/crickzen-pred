# Codex / Opencode Skills

This repository has reusable skills for common workflows.

## start-dashboard

- **Purpose**: Start or restart the dashboard app and verify `http://127.0.0.1:8000/health`
- **Location**: `C:\Users\ADMINS\.codex\skills\start-dashboard`
- **Usage**: invoke via Codex

## ipl-market-model-comparison

- **Purpose**: Inspect latest IPL Cricsheet/betx21 coverage, refresh non-active latest features, and rerun the IPL MC market-improvement workflow.
- **Location**: `C:\Users\ADMINS\.codex\skills\ipl-market-model-comparison`
- **Usage**: invoke via Codex

## add-new-league

- **Purpose**: Add a new T20 league model to the BBL pipeline. Covers CLI registration, retrain pipeline, phase distributions, and phase-split model build.
- **Location**: `.opencode/skills/add-new-league.md`
- **Usage**: Load in opencode when user asks to "add a new league", "create a model for X league", or "train X league model"
- **Full documentation**: `docs/ADD_NEW_LEAGUE.md`
- **Reusable scripts**:
  - `scripts/build_league_phase_features.py` -- parameterized phase-split model builder (`--league X --version v1`)
  - `scripts/extract_league_phase_distributions.py` -- phase distribution extractor for MC engine (`--league X`)
