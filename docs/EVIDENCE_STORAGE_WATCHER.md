# Evidence storage watcher

The evidence watcher checks the live prediction JSON against the durable
per-ball Parquet record while a match is active. It is an operational guard for
the seven-day market/model review; it does not restart predictors, alter public
probabilities, delete evidence, or promote a model.

The prediction scope is T20 and one-day/ODI only. Test/first-class and unknown
format fixtures are ignored by the watcher because they are not prediction
subjects.

## What it checks

- A fresh dashboard prediction has a separate expected file at
  `data/match_states/<league>/<provider-match-slug>.parquet`.
- Parquet can be opened, has rows, and contains the source URL, ball identity,
  teams, striker/non-striker/bowler figures, feature/inference JSON, model
  probability, and explicit market status fields.
- The file has no duplicate `state_key`, mixed match IDs, mixed source URLs, or
  implicit market availability.
- Persisted evidence is not more than 180 seconds behind the live state and is
  not more than 300 seconds old. The normal logger flushes its buffer every 30
  records, so the 180-second grace window covers an ordinary flush without
  hiding a broken writer.
- Feature completeness is at least 95%; team identity must be complete for all
  stored rows. Missing market data remains valid only when it is recorded as
  `market_status=unavailable` with a reason.

## Run once locally

```bash
python -m bbl_pipeline.ops.evidence_storage_watcher audit --json
```

The report is written atomically to
`data/model_reviews/evidence_watcher.json`. Status transitions are appended to
`data/model_reviews/evidence_watcher_events.jsonl`; unchanged cycles do not
spam the event log.

## Run continuously

```bash
python -m bbl_pipeline.ops.evidence_storage_watcher watch --interval-seconds 60
```

The production compose file runs this as the independent
`crickzen-evidence-watcher` container with `restart: unless-stopped`. A critical
status makes that container unhealthy and leaves a machine-readable report plus
an operator-visible container log. A warning is visible but does not restart
the watcher.

Exit codes for a one-shot audit are `0` healthy, `1` warning, and `2` critical.
The watcher intentionally remains alive in continuous mode so the next cycle
can observe recovery and record the transition.
