# Implementation Plan: Dashboard Metrics Foundation

**Spec**: `specs/017-dashboard-metrics-foundation/spec.md`  
**Branch**: `017-dashboard-metrics-foundation`  
**Date**: 2026-06-07  

---

## Summary

Build the first canonical proof-data layer for the CrickenZen dashboard. This phase does not yet ship the public proof page UI. Instead, it defines and implements the one approved path for dashboard-visible Brier, ECE, and accuracy reporting, produces reusable snapshot artifacts, and exposes stable backend contracts that later proof and `Ask CrickenZen` phases can consume.

The key product shift is:

```text
Ad hoc metric references → Canonical proof snapshots → Proof page and Ask surfaces
```

This plan intentionally focuses on trust infrastructure, not presentation polish.

---

## Technical Context

### Existing Metric Sources

- `src/bbl_pipeline/analysis/state_analyzer.py`
  - Already consolidates `data/match_states/<league>/`
  - Already computes overall and segmented Brier/ECE/log loss
- `src/bbl_pipeline/training/evaluation.py`
  - Already provides expected calibration error and segmented metric helpers
- `src/bbl_pipeline/telegram/signals.py`
  - Already provides `build_accuracy_tracker_row()`
- `src/bbl_pipeline/inference/match_state_logger.py`
  - Already writes the match-state records that probability proof should depend on

### Existing Dashboard Surface

- Public pages: `dashboard/templates/public.html`, `ipl_today.html`, `match_public.html`
- Dashboard API/router stack: `dashboard/app/routers/`
- Existing public insight tests: `dashboard/tests/test_public_insights.py`

### Important Product Constraint

This phase must explicitly separate:

1. **Probability quality**
   - Brier
   - ECE
   - optional supporting log loss

2. **Comparable prediction-call accuracy**
   - hit rate
   - wins/losses
   - confidence band summaries

The proof page can display both later, but this foundation must not blend them into one metric.

---

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Scalability & Reusability | ✅ PASS | Snapshot generation should be league-aware and reusable across dashboard proof surfaces, without hardcoding IPL-specific logic into generic loaders. |
| II. Pipeline-Driven Architecture & Rapid Retraining | ✅ PASS | This is a modular analysis pipeline: load state data → compute canonical metrics → write snapshots → expose dashboard contracts. |
| III. Reproducibility & Versioning | ✅ PASS | Snapshots will be versioned artifacts with manifests, timestamps, windows, and source metadata. |
| IV. Data Integrity & Entity Consistency | ✅ PASS | Canonical proof metrics depend on existing state files and winner metadata, with exclusions counted explicitly. |
| V. Model Calibration & Observability | ✅ PASS | The whole phase strengthens observability by making Brier/ECE/accuracy visible and stable for dashboard use. |

**Verdict**: PASS.

---

## Architecture

### Recommended New Modules

| File | Purpose |
|------|---------|
| `src/bbl_pipeline/analysis/proof_metrics.py` | Canonical snapshot builder for probability metrics, accuracy metrics, segments, metadata, and exclusions |
| `dashboard/app/proof_metrics.py` | Dashboard-side loader/service for reading the latest snapshot artifacts |
| `dashboard/app/routers/proof.py` | Stable backend contract for summary, segments, and ledger payloads |
| `scripts/build_dashboard_metrics_snapshot.py` | Rebuild snapshot artifacts for one or more leagues/windows |
| `dashboard/tests/test_proof_metrics.py` | Contract and loader tests |
| `tests/unit/analysis/test_proof_metrics.py` | Canonical metrics builder tests |

### Optional Reuse Instead of Rebuild

Where practical, reuse existing logic from:

- `StateAnalyzer._compute_metrics()`
- `StateAnalyzer._compute_ece()`
- `build_accuracy_tracker_row()`

If helper reuse creates tight coupling or awkward I/O assumptions, extract shared helpers rather than duplicating metric semantics.

---

## Data Boundary

### Canonical Probability Metric Inputs

Primary source:

- `data/match_states/<league>/all_matches.parquet`
- `data/match_states/<league>/match_metadata.parquet`

Derived fields:

- `actual_win = batting_team == winner`
- probability column:
  - default candidate: `model_prob_final`
  - final chosen field must be documented in the builder

Eligible rows:

- completed matches only
- rows with non-null winner
- rows with valid probability field

### Canonical Accuracy Inputs

Primary source candidates:

- explicit pre-match or tracked public-call records
- existing signal/tracker rows via `build_accuracy_tracker_row()`
- future persisted proof ledger rows

This phase should define one V1-compatible source contract for accuracy rows even if persistence later improves.

### Forbidden Product Mistake

Do not compute:

- Brier from pre-match accuracy rows
- accuracy from every live ball state
- a blended “trust score” that hides metric semantics

---

## Snapshot Semantics

### Probability Metrics

V1 required fields:

- `brier`
- `ece`
- `sample_count`
- `last_updated`
- `evaluation_window`
- `league`
- `status`

Optional supporting fields:

- `log_loss`
- `eligible_matches`
- `excluded_rows`
- `build_version`

### Accuracy Metrics

V1 required fields:

- `accuracy_pct`
- `wins`
- `losses`
- `sample_count`
- `excluded_rows`
- `last_updated`
- `evaluation_window`
- `league`
- `status`

### Segment Metrics

Minimum segment grain:

- by innings
- by phase

Recommended additional grain if data is practical:

- by league
- by month or rolling window
- by broad match context

### Freshness Metadata

Every snapshot should carry:

- build timestamp
- input timestamp range if available
- staleness threshold
- stale/not-stale flag

---

## Artifact Layout

Recommended V1 artifact location:

```text
data/dashboard_metrics/
├── latest/
│   ├── ipl_summary.json
│   ├── ipl_segments.json
│   ├── ipl_ledger.json
│   └── ipl_manifest.json
├── windows/
│   ├── ipl_last_7_days_summary.json
│   ├── ipl_last_30_days_summary.json
│   ├── ipl_all_available_summary.json
│   └── ...
└── reports/
    └── ipl_metrics_report.md
```

This keeps the dashboard loader simple while preserving room for versioned history.

---

## Proof Contract Shape

### Summary Contract

Recommended top-level shape:

```json
{
  "league": "IPL",
  "window": "last_30_days",
  "status": "ready",
  "probability_metrics": {
    "brier": 0.1831,
    "ece": 0.0124,
    "sample_count": 18240
  },
  "accuracy_metrics": {
    "accuracy_pct": 61.5,
    "wins": 24,
    "losses": 15,
    "sample_count": 39
  },
  "freshness": {
    "built_at": "2026-06-07T14:10:00+00:00",
    "stale": false
  },
  "definitions": {
    "brier": "Lower is better. Measures probability error.",
    "ece": "Lower is better. Measures calibration gap.",
    "accuracy": "Higher is better. Measures discrete call hit rate."
  }
}
```

### Segment Contract

Return flat rows with explicit type fields, for example:

- `segment_type = innings`
- `segment_type = phase`
- `segment_key = innings_1`
- `segment_key = phase_death`

### Ledger Contract

Each row should support later proof-page rendering:

- match label
- league
- timestamp
- predicted side
- predicted probability or confidence band
- final winner
- result status
- what changed
- source link if available

---

## Implementation Sequence

### Step 1 - Lock the Canonical Metric Semantics

Decide and document:

1. the canonical probability field
2. the canonical ECE implementation
3. the initial evaluation windows
4. the V1 definition of accuracy

Recommended decision:

- Use the same ECE method as `StateAnalyzer` for dashboard proof V1
- Keep Brier/ECE on completed match-state rows
- Keep accuracy on explicit comparable call rows only

This is the highest-risk design decision because later UI trust depends on it.

### Step 2 - Build Probability Snapshot Generation

Implement a reusable builder that:

1. loads completed state files for a league
2. joins winner metadata
3. filters eligible rows
4. computes overall metrics
5. computes segment metrics by innings and phase
6. counts exclusions
7. writes summary, segments, and manifest artifacts

Prefer reusing `StateAnalyzer` computation logic or extracting its core helpers.

### Step 3 - Build Accuracy Ledger and Summary

Implement a small proof-ledger pipeline that:

1. reads comparable call rows from the chosen source
2. validates required fields
3. dedupes comparable rows
4. computes wins/losses/accuracy
5. records exclusion reasons
6. writes ledger and accuracy summary artifacts

Keep the first version honest even if the ledger volume is still small.

### Step 4 - Add Dashboard Loader Layer

Create a dashboard-side service that:

1. reads the latest snapshot artifacts
2. returns typed summary/segment/ledger payloads
3. marks missing artifacts as `not_ready`
4. marks old artifacts as `stale`

This keeps the future proof page thin and predictable.

### Step 5 - Expose Stable Backend Contracts

Add proof-focused routes or loaders, for example:

- `/api/proof/summary`
- `/api/proof/segments`
- `/api/proof/ledger`

Whether these are public or authenticated can be decided in the next proof-page phase, but the contract should exist now.

### Step 6 - Add Validation and Documentation

Validation must prove:

1. Brier/ECE values reproduce from canonical inputs
2. not-ready cases do not emit fake values
3. ledger accuracy excludes invalid rows cleanly
4. snapshot freshness metadata behaves correctly

Also add an operator-facing note that explains:

- what gets rebuilt
- what data it depends on
- how to refresh it before proof-page release

---

## Testing Strategy

### Unit Tests

Add tests for:

- ECE/Brier snapshot computation
- innings and phase segmentation
- no-completed-data behavior
- exclusion counting
- accuracy summary computation
- stale snapshot detection

### Integration Tests

Add tests that:

- generate a sample league snapshot end to end
- load dashboard summary and segments from artifacts
- return `not_ready` when artifacts are absent
- validate ledger row ordering and readiness metadata

### Suggested Validation Commands

```bash
pytest tests/unit/analysis/test_proof_metrics.py -v
pytest dashboard/tests/test_proof_metrics.py -v
python scripts/build_dashboard_metrics_snapshot.py --league ipl --window all_available
```

If the implementation reuses `StateAnalyzer`, also validate against:

```bash
python -m bbl_pipeline.cli analyze-states --league ipl --calibration-report
```

---

## Risks and Mitigations

### Risk 1 - Accuracy Means Different Things to Different People

Mitigation:

- define accuracy explicitly as comparable call accuracy
- never let it replace Brier/ECE in proof summaries

### Risk 2 - Metric Drift Across Modules

Mitigation:

- pick one canonical path now
- add tests that compare snapshot outputs against the canonical calculation

### Risk 3 - Weak Accuracy Sample Size at First

Mitigation:

- return ready probability metrics even if accuracy is `not_ready`
- surface sample counts and exclusions clearly

### Risk 4 - Future Proof Page Reimplements Logic

Mitigation:

- keep proof-page phase dependent on these artifacts and routes
- document the contract in the spec and loader code

---

## Out of Scope for This Phase

- proof-page template or UI layout
- final public marketing copy
- `Ask CrickenZen` interface
- pre-match match brief UI
- ranked recommendations

---

## Handoff to Next Phase

When this phase is complete, the next proof-page spec should be able to assume:

- stable proof summary data exists
- stable segment data exists
- stable ledger data exists
- freshness and readiness states are explicit
- Brier, ECE, and accuracy semantics are fixed

That will let the proof-page phase focus on product presentation instead of backend uncertainty.
