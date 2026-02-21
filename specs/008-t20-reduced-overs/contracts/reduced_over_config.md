# Contract: Reduced-Over Configuration

**Feature**: 008-t20-reduced-overs  
**Date**: 2026-02-21

## FormatConfig.t20_reduced() Factory

### Signature

```
FormatConfig.t20_reduced(total_overs: int) → FormatConfig
```

### Preconditions

- `5 <= total_overs <= 20`
- When `total_overs == 20`, returns identical config to `FormatConfig.t20()`

### Postconditions

- `config.total_overs == total_overs`
- `config.total_balls == total_overs * 6`
- `config.par_score` scaled via DLS resource table (non-linear)
- `config.phase_thresholds["final"] == total_overs`
- All phase thresholds are strictly ascending
- Powerplay threshold: `max(2, min(6, round(total_overs * 0.30)))`
- Death starts at: `total_overs - max(2, round(total_overs * 0.25)) + 1`

### Examples

| Input | par_score | Phases (pp/mid/death/final) |
|:-----:|:---------:|:---------------------------:|
| 20 | 160.0 | 6/14/18/20 |
| 15 | ~133 | 5/11/12/15 |
| 10 | ~101 | 3/7/8/10 |
| 5 | ~62 | 2/3/4/5 |

---

## SimulationMatchState (extended)

### New Field

```
total_balls: int = 120
```

### Validation Contract

- `0 <= balls_remaining <= total_balls` (was `<= 120`)
- `30 <= total_balls <= 120` (maps to 5-20 overs)
- `total_balls % 6 == 0`

### Property Contracts

- `overs_completed = (total_balls - balls_remaining) / 6`
- `phase = get_phase(balls_remaining, total_balls)` — not `get_phase(balls_remaining)`
- `copy()` propagates `total_balls`

---

## CLI Arguments

### New Arguments

```
--total-overs    INT   Optional. Total overs per innings (5-20). Default: auto-detect or 20.
--revised-target INT   Optional. DLS revised target for 2nd innings. Default: auto-detect or none.
```

### Priority Order

1. CLI argument (if provided) — highest priority
2. CREX auto-detection (if found on page) — default behavior
3. Standard defaults (20 overs, no revision) — fallback

---

## CREX Auto-Detection

### Detection Patterns

```
Revised target: r'(?:revised\s+)?target\s*[:\-]\s*(\d+)\s*\(?(?:d/?l/?s?|dls)\)?'
Reduced overs:  r'(\d+)\s+ov(?:er)?s?\s+(?:match|per\s+side|a\s+side)'
                or parsed from sV3 API response metadata
```

### Output

```
detected_total_overs: Optional[int]    # None if not detected
detected_revised_target: Optional[int]  # None if not detected
```

### Behavior

- Detection runs on every scrape cycle
- If `total_overs` changes from 20 to <20: log transition, switch to MC-only mode
- If detection fails: use CLI value or default 20

---

## MC Calibration

### Calibrator Interface

```
MCCalibrator.calibrate(raw_mc_prob: float) → float
MCCalibrator.calibrate_batch(raw_mc_probs: np.ndarray) → np.ndarray
MCCalibrator.load(path: str) → MCCalibrator
MCCalibrator.save(path: str) → None
```

### Training Contract

- Input: 141K+ `(mc_raw_prob, actual_outcome)` pairs from 20-over matches
- Method: Platt scaling (logistic regression on logit of mc_pred)
- Output: `mc_calibrator.pkl`
- Quality gate: log loss ≤ 0.55 on held-out validation set

### Prediction Mode Contract

| Condition | Prediction Engine | Calibration |
|-----------|-------------------|-------------|
| `total_overs == 20` | XGBLogRegEnsemble + per-over calibration chain | Standard (existing) |
| `total_overs < 20` | Monte Carlo only | Platt MC calibrator |
| Mode switch mid-match | Immediate; log transition | Switch calibration method |
