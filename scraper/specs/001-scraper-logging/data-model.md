# Data Model: Scraper Logging Recovery

## Overview

The feature introduces structured observability entities to capture scraper run diagnostics, correlate log events, and surface recurring failure patterns without altering existing match/statistic schemas.

## Entities

### ScrapeRun
- **Purpose**: Represents a single scraper execution cycle.
- **Fields**:
  - `correlation_id` (UUID, primary) – shared key for logs, diagnostics, and health metrics.
  - `job_name` (string) – identifier for background job or manual invocation.
  - `start_ts` / `end_ts` (datetime) – window for the run (nullable end_ts while in-flight).
  - `stage_durations` (JSON object) – keyed by stage (`navigation`, `dom_eval`, `extraction`, `validation`, `persistence`).
  - `status` (enum: `success`, `degraded`, `failed`, `aborted`) – aligns with success criteria.
  - `urls_processed` (integer) – count of URLs validated during the run.
  - `artifact_paths` (array<string>) – relative paths to captured diagnostics.
  - `notes` (string, optional) – free-form annotations for operators.
- **Relationships**:
  - 1:* with `LogEvent` via `correlation_id`.
  - 1:* with `FailureSignature` references produced during the run.
- **Constraints**:
  - Enforce unique `correlation_id`.
  - Require `status` to transition `in_progress → {success|degraded|failed|aborted}` only once per run.
  - Ensure `stage_durations` keys cover all mandatory stages per FR-001.

### LogEvent
- **Purpose**: Canonical structured log record for scraper operations.
- **Fields**:
  - `timestamp` (datetime) – ISO8601 with milliseconds.
  - `level` (enum: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).
  - `component` (enum: `navigation`, `dom`, `extraction`, `validation`, `persistence`, `job_control`, `network`).
  - `event` (string) – concise event name (e.g., `dom.selector.missing`).
  - `metadata` (JSON object) – redacted payload storing contextual fields.
  - `correlation_id` (UUID, foreign key → `ScrapeRun`).
  - `sequence` (integer) – monotonically increasing per run for ordering.
- **Constraints**:
  - Composite unique `correlation_id + sequence`.
  - Enforce JSON schema for metadata keys required by FR-001.
  - Apply redaction filter before persistence to prevent sensitive data leakage.

### ScraperHealthSnapshot
- **Purpose**: Aggregated view of job lifecycle for monitoring endpoints.
- **Fields**:
  - `job_name` (string, primary).
  - `state` (enum: `starting`, `running`, `retrying`, `stopped`, `failed`).
  - `last_success_ts` (datetime) – last run completing with `success`.
  - `active_correlation_id` (UUID, nullable) – current run or `null` if idle.
  - `retry_count` (integer) – consecutive retries since last success.
  - `alerts` (array<string>) – outstanding warnings (e.g., `dom_drift`, `retry_exhausted`).
- **Constraints**:
  - Update atomically when state transitions occur to avoid race conditions.
  - Ensure `retry_count` resets to 0 on `success`.

### FailureSignature
- **Purpose**: Captures repeated failure patterns to accelerate root cause analysis.
- **Fields**:
  - `signature_id` (UUID, primary).
  - `type` (enum: `selector_missing`, `timeout`, `validation_error`, `anti_bot`, `resource_exhaustion`).
  - `fingerprint` (string hash) – deterministic key derived from failing selector/URL/error message.
  - `first_seen_ts` / `last_seen_ts` (datetime).
  - `occurrence_count` (integer).
  - `sample_correlation_id` (UUID) – reference to representative run.
  - `advice` (string, optional) – remediation hint captured during resolution.
- **Constraints**:
  - Unique constraint on `type + fingerprint`.
  - Automatically increment `occurrence_count` when same signature detected.

## Derived Views

- **RunMetricsView**: Aggregates `ScrapeRun` records to compute p95 cycle durations and success/failure ratios for success criteria SC-002/SC-004.
- **FailureTrendView**: Joins `FailureSignature` with recent `LogEvent`s matching the fingerprint to support proactive alerts.

## State Transitions

```
ScrapeRun.status:
  in_progress → success     (normal completion)
  in_progress → degraded    (completed with warnings)
  in_progress → failed      (unrecoverable error; artifacts captured)
  in_progress → aborted     (manual stop or shutdown)

ScraperHealthSnapshot.state:
  starting → running → retrying (on failure) → running (on recovery) → stopped/failed (terminal)
```

## Validation Rules

- `ScrapeRun.stage_durations` must include the same keys for every run; missing stages trigger warning logs per User Story 1.
- `LogEvent.metadata` must include URL validation outcomes when `component=validation` to support FR-006.
- Diagnostic artifacts referenced in `artifact_paths` must exist within retention window; nightly housekeeping prunes expired directories and emits warning if deletion fails.

## Open Questions

_None._ Research phase resolved prior ambiguities regarding storage, retention, and formatter choices.
