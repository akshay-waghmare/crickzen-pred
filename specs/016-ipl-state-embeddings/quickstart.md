# Quickstart: IPL Regime-Aware State Embeddings

## Goal

Run an offline IPL-only pilot that:
1. builds a reusable embedding corpus from IPL v6 feature rows,
2. discovers regimes,
3. retrieves historical analogues, and
4. compares regime-aware variants against the current IPL baseline.

## 1. Pilot run on sampled IPL data

```powershell
python scripts/analyze_ipl_state_embeddings_experiment.py `
  --input data/ipl_features_v6/training_sampled.parquet `
  --raw-backfill-dir data/ipl_raw/matches `
  --output-dir experiments/ipl_state_embeddings_v1 `
  --mode pilot `
  --seed 42 `
  --resume
```

Notes:
- `training_sampled.parquet` may not carry match metadata columns in older exports; the script backfills them from sibling `training.parquet` and IPL raw JSON metadata when needed.
- Pilot mode is the recommended first run. It produces the full offline artefact tree and a decision-ready `PILOT_REPORT.md`.

## 2. Full run on the main IPL corpus

```powershell
python scripts/analyze_ipl_state_embeddings_experiment.py `
  --input data/ipl_features_v6/training.parquet `
  --raw-backfill-dir data/ipl_raw/matches `
  --output-dir experiments/ipl_state_embeddings_v1 `
  --mode full `
  --seed 42 `
  --resume
```

Notes:
- Full mode is resumable and can take materially longer during analogue retrieval because it uses exact nearest neighbours over the full IPL corpus.
- Keep V1 offline-only even if a candidate variant passes the report gate.

## 3. Expected outputs

```text
experiments/ipl_state_embeddings_v1/
├── corpus/corpus_manifest.json
├── regimes/regime_summary.csv
├── retrieval/retrieval_summary.json
└── evaluation/
    ├── metrics.csv
    ├── segment_metrics.csv
    └── PILOT_REPORT.md
```

## 4. Success checks

- `corpus_manifest.json` shows >=95% eligible-row coverage or explains exclusions.
- `retrieval_summary.json` shows valid analogue coverage for held-out queries.
- `metrics.csv` includes `baseline_ipl_v6_features` and regime-aware variants with deltas for Brier, log loss, and ECE.
- `PILOT_REPORT.md` ends with explicit `GO` or `NO-GO`.
- `segment_metrics.csv` and `reliability_bins.csv` must be checked before treating any aggregate win as meaningful.

## 5. Recommended development validation

```powershell
pytest tests/unit/analysis/state_embeddings -q
pytest tests/integration/test_ipl_state_embeddings_experiment.py -q
```

## 6. Promotion rule

Do **not** propose production rollout unless at least one regime-aware variant:
- beats the current IPL baseline on **both** Brier and log loss, and
- does not materially worsen ECE or key innings/phase behaviour.
- otherwise the correct outcome is `NO-GO` / no production change.

Use the stricter stress-tested rule for IPL:

1. OOS Brier improves
2. OOS LogLoss improves
3. ECE does not worsen
4. Innings 2 powerplay does not regress
5. No innings/phase segment worsens materially
6. Season-slice validation remains directionally stable across:
   - train `<2024` -> test `2024`
   - train `<2025` -> test `2025`
   - train `<2026` -> test `2026`

Official current conclusion:
- Regime clusters contain real predictive signal, but current regime context is not temporally stable enough for direct promotion.
- The only promotable direction is conservative additive `regime_cluster_features` with strict Inn2 PP guardrails.
- Do **not** promote `regime_hybrid_features`.
- Do **not** promote `guarded_regime_phase_calibration` or broader regime-conditioned calibration.
