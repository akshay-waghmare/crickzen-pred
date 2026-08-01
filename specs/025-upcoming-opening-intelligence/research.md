# Research — Spec 025 Phase 0 Data and Leakage Audit

Checked: 2026-08-01

## Usable historical source

`data/t20_all_raw/matches/**/*.parquet` records ball rows with:

`match_id`, `date`, `venue_id`, `batting_team_id`, `bowling_team_id`,
`batting_team`, `winner`, `league`, and `gender`, alongside toss and
ball-by-ball fields. The analogous ODI raw dataset follows the same ingestion
contract.

One T20 sample is `Australia` v `New Zealand` on 2005-02-17 at Eden Park, with
`winner=Australia`. This proves that a match-level outcome table can be built
by collapsing each `match_id` to its first record and treating the two team IDs
as an unordered fixture pair. The public estimator must use a deterministic
team perspective (for example lexicographic source-team order or the upstream
fixture order), not `batting_team`/`bowling_team`, because that assignment is
known only after toss.

## Exclusions

The following raw fields are prohibited in an opening feature table because
they are determined at or after start: `toss_winner`, `toss_decision`,
`innings`, `is_super_over`, `over`, `ball`, all player-on-ball fields, runs,
wicket fields, and `winner` (target only).

`venue_id`, `league`, and `gender` are optional pre-match context. A production
row must be `not_ready` rather than impute a value when its required identity or
coverage is missing.

## Existing rating-store hazard

`data/t20_all_feature_store_v2/team_ratings.parquet` has 109 current aggregate
team rows with `team, win_rate, matches, bat_first_wr, bowl_first_wr,
recent_nrr`; `data/odi_all_feature_store_v2/team_ratings.parquet` has 28 rows
with the same columns. Neither file carries a date/as-of timestamp.

Those files are suitable only as a runtime candidate after a separately proven
as-of rebuild. They must not be used to score chronological historical test
rows, because they aggregate outcomes from the full data set and would leak
future results. The Phase 2 baseline must calculate expanding historical team
features inside each training period instead.

## Immediate implementation implication

The first experiment can be a time-safe team-strength baseline with:

- a deterministic fixture-team order;
- prior-only, expanding team win record and sample count;
- optional known venue/competition/gender context;
- chronological train/calibration/test windows; and
- explicit low-history/non-resolved-team fallback.

It cannot reuse the live state predictor or its terminal feature store directly.

## Initial chronological baseline (2026-08-01)

The first T20 experiment is an expanding, smoothed team-strength baseline. It
forms a deterministic unordered team pair from raw fixture rows, scores every
fixture from only prior dates, and waits until all fixtures on a date have been
scored before recording that date's outcomes. It requires at least five prior
matches for each team.

The final test reserves the newest 20% of whole fixture dates. A Platt
calibrator is fit only on the earlier eligible OOF predictions, then applied
once to the untouched holdout. This is a model-quality experiment, not a
public-model artifact or a claim of production readiness.

| Evaluation | Rows | Brier | Log loss | ECE | Historical-rate Brier | Historical-rate log loss |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Eligible chronological OOF | 4,935 | 0.2327 | 0.6574 | 0.0454 | 0.2433 | 0.6803 |
| Final holdout, raw | 1,491 | 0.2301 | 0.6522 | 0.0588 | 0.2444 | 0.6819 |
| Final holdout, Platt-calibrated | 1,491 | 0.2258 | 0.6430 | 0.0251 | 0.2444 | 0.6819 |

The calibrated final holdout beats the neutral 0.50 baseline (Brier 0.2500,
log loss 0.6931) and the simple historical-rate baseline overall. Its learned
parameters are intercept `0.02996` and slope `1.61391`, fit on 3,444 earlier
eligible rows; its final holdout starts at `2025-01-22`.

### Promotion gate and decision

The current offline gate requires at least 1,000 overall holdout rows, 500 for
each female and male segment, Brier improvement of at least 0.002 against both
baselines, lower log loss against both, ECE at or below 0.050, and a named
competition holdout segment. The calibrated male segment passes its measured
gate (811 rows, Brier 0.2253, ECE 0.0486), but the female segment does not
(680 rows, Brier 0.2265, ECE 0.0705).

Decision: **shadow-only revise**. Do not serialize an opening probability,
enable fixture ingress, or change canonical SSR from this experiment. Next
work must improve/calibrate the female segment on a new untouched temporal
holdout.

### Competition metadata recovery (2026-08-01)

The raw parquet `league` column is still `unknown`, but it is not the final
source of truth for a competition label. Every raw match ID was checked against
the bundled Cricsheet archive, and `info.event.name` is pre-innings fixture
metadata. The new exact-ID loader maps 5,300 of 5,363 raw match IDs (98.8%) to
a non-empty event name; 63 source records have no usable event name. It never
falls back to team-name inference or result data.

The temporal holdout now reports 224 named event segments. They are not large
enough for individual event-specific calibration: its largest segment, `ICC
Men's T20 World Cup`, has 49 rows; other leading segments range from 41 to 20.
They are retained as transparent diagnostic cuts (20-row reporting minimum),
not promoted as independent quality gates. Competition identity is therefore
no longer a blocker to reporting, but a public competition-specific model
would need a separately justified grouping and material holdout size.

The decision remains **shadow-only revise** solely because the female
calibrated holdout ECE is 0.0705 over the 0.050 gate. Next work revises the
calibration method and evaluates it again on an untouched temporal holdout.

### Rejected calibration variants (2026-08-01)

Two gender-specific calibration variants were tested only on the same original
date-disjoint split; neither is promoted into the implementation. A female-only
Platt fit used 1,244 older female rows and scored the 680-row female holdout at
Brier 0.2264, log loss 0.6460, and ECE 0.0675. It improves the global-Platt
female ECE only slightly and still fails the 0.050 gate. Female-only isotonic
calibration scored Brier 0.2279, log loss 0.6926, and ECE 0.0801, so it is
strictly worse for the intended probability-quality contract.

The corresponding male-only versions are also not a replacement: Platt ECE is
0.0584 and isotonic ECE is 0.0606. Keep the global Platt result as the current
reference, and make the next experiment a clearly specified feature/model
revision followed by a new untouched temporal holdout rather than another
calibrator swap.

### Elo feature/model revision (2026-08-01)

The next candidate replaces the expanding win-rate ratio with a prior-only Elo
rating. It starts each team at 1500, scores the deterministic fixture pair from
the rating difference before play, and applies its updates only after all
fixtures on the same date have been scored. It retains the prior win-rate field
solely as the unchanged comparison baseline. There is no toss, score,
ball-by-ball, lineup, result-text, or future-date input.

`K=64` was selected on an inner date-disjoint validation within the pre-holdout
period because it had the lowest overall/female Brier and log loss among the
pre-registered Elo K grid. The outer 1,491-fixture holdout beginning
2025-01-22 was then evaluated once by `scripts/evaluate_opening_baseline.py
--estimator elo --elo-k-factor 64`; its generated JSON remains ignored under
`artifacts/opening-baseline/t20_all_elo64_v1.json`.

| Evaluation | Rows | Brier | Log loss | ECE |
| --- | ---: | ---: | ---: | ---: |
| Final holdout, Elo raw | 1,491 | 0.2062 | 0.6005 | 0.0401 |
| Final holdout, Elo + global Platt | 1,491 | 0.2058 | 0.5988 | 0.0180 |
| Female, Elo + global Platt | 680 | 0.2040 | 0.5949 | 0.0340 |
| Male, Elo + global Platt | 811 | 0.2074 | 0.6020 | 0.0460 |

The calibrated candidate improves both Brier and log loss against neutral and
the fixed prior-win-rate baseline, and clears the 0.050 ECE gate overall and
for both gender slices. Focused leakage/regression tests pass (`13 passed`).
This is an **offline promotion only**: it authorizes Phase 1 fixture ingress
and a separately named opening-row contract, but does not itself publish a
percentage, change the live selector, alter canonical SSR, or claim a live
upcoming cohort. Those operations remain separately gated by exact identity,
12–48-hour TTL, production parity, and current-fixture proof.
