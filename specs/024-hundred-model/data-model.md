# Data Model — The Hundred

## Source entities

### `HundredMatchRaw`

The Cricsheet JSON document from `hnd_json/<match_id>.json`. It is immutable input and
must remain available for traceability.

Required source fields:

- `info.dates`
- `info.gender`
- `info.season`
- `info.teams`
- `info.venue`
- `info.outcome`
- `info.balls_per_over`
- `info.overs`
- `innings[].team`
- `innings[].overs[].deliveries[]`

### `QuarantineRecord`

```text
match_id: string
innings_number: integer
source_path: string
reason_code: enum
observed_value: string
eligible_for_recovery: boolean
created_at: datetime
```

Reason codes:

- `invalid_json`
- `missing_required_metadata`
- `unexpected_balls_per_over`
- `legal_ball_overflow`
- `dls_target_not_supported`
- `no_result`
- `tie_or_super_five`
- `missing_winner`
- `entity_resolution_failure`

## Normalized delivery

Each raw delivery becomes one row. Raw fields remain available for debugging; derived
fields are the model contract.

```text
match_id: string
season: string
date: date
gender: enum[male, female]
gender_female: integer[0,1]
league: string = "hundred"
venue_id: string
batting_team_id: string
bowling_team_id: string
innings: integer[1,2]
is_super_five: boolean
raw_over: integer
raw_delivery_label: string|null
delivery_sequence: integer
is_legal_delivery: boolean
legal_ball_index: integer[1,100]
five_index: integer[1,20]
end_block_index: integer[1,10]
balls_bowled: integer[1,100]
balls_remaining: integer[0,99]
phase: enum[powerplay,middle,death,final]
powerplay_active: boolean
batter_id: string
bowler_id: string
non_striker_id: string
runs_batter: integer
runs_extras: integer
runs_total: integer
extras_json: object
wicket_type: string|null
player_out_id: string|null
winner: string|null
target_score: integer|null
```

`legal_ball_index` increments only when the delivery is not a wide or no-ball. A raw
delivery after legal ball 100 is not accepted into the normal model cohort; it is logged
as `legal_ball_overflow`.

## Match-state contract

```text
format_name: "hundred"
total_balls: 100
balls_per_over: 5
total_legal_balls: 100
scoring_set_size: 5
end_change_interval: 10
powerplay_balls: 25
max_balls_per_bowler: 20
innings: 1|2
score: integer >= 0
wickets_lost: integer 0..10
legal_balls_bowled: integer 0..100
balls_remaining: integer 0..100
target_runs: integer|null
runs_needed: integer|null
current_run_rate: float
required_run_rate: float|null
phase: string
powerplay_active: boolean
ball_within_five: integer[1,5]
anomaly_flags: list[string]
gender_female: integer 0|1
```

All live prediction paths must construct this contract using the same formulas as
historical processing. The unit of `overs_remaining` is five-ball overs only when a
human-readable over value is needed; the primary clock remains legal balls.

## Artifact layout

```text
data/hundred_raw/
data/hundred_normalized_v1/
data/hundred_features_v1/
data/hundred_feature_store_v1/
models/hundred_all_v1/
experiments/hundred_v1/
```

Required model metadata:

```text
format_name: hundred
total_balls: 100
balls_per_over: 5
gender_encoding: gender_female
source_dir: hnd_json
source_file_count: integer
training_match_count: integer
excluded_match_count: integer
feature_columns: ordered list
calibration_method: string
data_fingerprint: string
```
