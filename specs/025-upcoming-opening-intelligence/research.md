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
