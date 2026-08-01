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
(680 rows, Brier 0.2265, ECE 0.0705). The raw T20 source also reports every
league as `unknown`, so there is no competition-level evidence.

Decision: **shadow-only revise**. Do not serialize an opening probability,
enable fixture ingress, or change canonical SSR from this experiment. Next
work must restore reliable competition identity and improve/calibrate the
female segment on a new untouched temporal holdout.
