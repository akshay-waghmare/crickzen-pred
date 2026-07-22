# Spec 021 — Unified Men/Women T20 and ODI Models

## Goal

Train production-ready combined-gender win-probability models from `t20s_json/` and `odis_json/`, using the existing IPL pipeline contract.

## Scope

- `t20_all`: all T20 matches in `t20s_json/`, 20-over format.
- `odi_all`: all ODI matches in `odis_json/`, 50-over format.
- Reuse ingestion, feature processing, XGBLogRegEnsemble training, OOF calibration, model registry, and live inference.
- Preserve match gender as an explicit `gender_female` feature and validate that both genders are represented before training.

## Acceptance criteria

1. `bbl-pipeline retrain --league t20_all --version v1` and the ODI equivalent resolve the supplied folders without code edits.
2. Both pipelines produce training parquet, feature-store artifacts, champion model, calibrators, OOF metrics, and registry entries.
3. Evaluation reports overall and gender-segmented Brier, log loss, ECE, and sample/match counts.
4. No IPL-specific constants or calibrators are silently reused for the global datasets.
5. Live predictor can select `t20_all` or `odi_all` through the existing league/config path.
6. CrickZen resolves league-specific models first, then format-matched combined gender-aware models, never a men's-only fallback for women's matches.

## Phases

- Phase A: dataset audit and pipeline wiring.
- Phase B: full ingestion and feature generation.
- Phase C: model training and OOF calibration.
- Phase D: gender/format evaluation, inference smoke tests, and dashboard registration.
