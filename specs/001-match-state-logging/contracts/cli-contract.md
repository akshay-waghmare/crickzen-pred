# CLI Contract: Match State Recording

## crex_live_predictor (modified — argparse)

### New Arguments

| Argument | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `--record-states` | flag | No | `False` | Enable match state recording to Parquet |
| `--states-dir` | `str` | No | `data/match_states/<league>/` | Directory for recorded state files |

### Behavior When `--record-states` Is Set

1. Creates `MatchStateLogger` instance on startup
2. After each `_write_json_state()` call, passes full state data to logger
3. Logger buffers records in memory (list of dicts)
4. Logger flushes to disk:
   - At innings break (innings number changes)
   - At match completion (final state detected)
   - Every 30 records (safety flush)
5. On match end or SIGINT, writes `match_metadata.parquet` with what's known
6. All logger errors are caught and logged, never interrupting predictions

### Output Files Created

```
<states-dir>/
├── <match_id>.parquet           # Ball-level state records
└── match_metadata.parquet       # Match metadata (appended)
```

---

## bbl-pipeline analyze-states (new Click command)

### Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `--match-file` | `Path` | No* | Path to specific match Parquet file |
| `--league` | `str` | No* | League code (bbl, sa20, etc.) |
| `--outcome` | `str` | No | Match winner team name (for single match) |
| `--consolidate` | flag | No | Consolidate all per-match files into all_matches.parquet |
| `--calibration-report` | flag | No | Generate calibration metrics report |
| `--deviation-threshold` | `float` | No | Min deviation for signal events (default: 0.10) |
| `--states-dir` | `Path` | No | Override default states directory |

*One of `--match-file` or `--league` is required.

### Operations

| Mode | Trigger | Output |
|------|---------|--------|
| **Single match analysis** | `--match-file` + `--outcome` | Updates match_metadata, computes volatility + signals |
| **Consolidate** | `--league` + `--consolidate` | Creates `all_matches.parquet` from all per-match files |
| **Calibration report** | `--league` + `--calibration-report` | Prints Brier, ECE, log-loss + generates markdown report |
| **Full analysis** | `--league` (no flags) | Consolidate + volatility + signals + report |

### Output Files

```
data/match_states/<league>/
├── all_matches.parquet            # Consolidated ball states
├── volatility_profiles.parquet    # Per-match volatility
├── signal_events.parquet          # Deviation events with reversion labels
└── CALIBRATION_REPORT.md          # Calibration analysis report
```
