from datetime import date, datetime

import pandas as pd
import pytest

from src.bbl_pipeline.prematch.opening_baseline import (
    FixtureOutcome,
    EvaluationMetrics,
    assess_promotion_gate,
    apply_calibration,
    build_elo_runtime_state,
    build_fixture_outcomes,
    evaluate_by_segment,
    evaluate_predictions,
    fit_platt_calibrator,
    generate_elo_opening_predictions,
    generate_opening_predictions,
    load_competition_by_match_id,
    score_elo_opening_fixture,
    split_predictions_chronologically,
)


def fixture(match_id: str, when: date, first: str, second: str, winner: str) -> FixtureOutcome:
    team_a, team_b = sorted((first, second), key=str.casefold)
    return FixtureOutcome(match_id, when, team_a, team_b, winner)


def test_build_fixture_outcomes_uses_pair_not_toss_order_or_ball_state():
    base = {
        "match_id": ["m1", "m1"],
        "date": ["2026-01-01", "2026-01-01"],
        "batting_team_id": ["B", "B"],
        "bowling_team_id": ["A", "A"],
        "winner": ["A", "A"],
        "toss_winner": ["B", "B"],
        "over": [0, 19],
        "runs_total": [0, 200],
    }
    changed = {**base, "toss_winner": ["A", "A"], "over": [5, 20], "runs_total": [9, 210]}

    original = build_fixture_outcomes(pd.DataFrame(base))
    altered = build_fixture_outcomes(pd.DataFrame(changed))

    assert original == altered
    assert original[0].team_a == "A"
    assert original[0].team_b == "B"


def test_fixture_dates_drop_pandas_or_datetime_time_components():
    outcomes = build_fixture_outcomes(pd.DataFrame({
        "match_id": ["m1"],
        "date": [datetime(2026, 1, 1, 23, 30)],
        "batting_team_id": ["A"],
        "bowling_team_id": ["B"],
        "winner": ["A"],
    }))

    assert outcomes[0].match_date == date(2026, 1, 1)


def test_unresolved_winner_is_excluded_from_binary_training_rows():
    frame = pd.DataFrame({
        "match_id": ["draw"], "date": ["2026-01-01"],
        "batting_team_id": ["A"], "bowling_team_id": ["B"], "winner": [""],
    })
    assert build_fixture_outcomes(frame) == []


def test_exact_cricsheet_event_metadata_recovers_unknown_competition(tmp_path):
    (tmp_path / "m1.json").write_text(
        '{"info":{"event":{"name":"Example T20 Cup"},"outcome":{"winner":"A"}},"innings":[]}',
        encoding="utf-8",
    )
    metadata = load_competition_by_match_id(tmp_path, ["m1", "missing"])
    frame = pd.DataFrame({
        "match_id": ["m1"], "date": ["2026-01-01"],
        "batting_team_id": ["A"], "bowling_team_id": ["B"],
        "winner": ["A"], "league": ["unknown"],
    })

    outcomes = build_fixture_outcomes(frame, competition_by_match_id=metadata)

    assert metadata == {"m1": "Example T20 Cup"}
    assert outcomes[0].league == "Example T20 Cup"


def test_future_results_do_not_change_an_earlier_prediction():
    early = fixture("m1", date(2026, 1, 1), "A", "B", "A")
    target = fixture("m2", date(2026, 1, 2), "A", "B", "B")
    future = fixture("m3", date(2026, 1, 3), "A", "C", "C")

    without_future = generate_opening_predictions([early, target], minimum_prior_matches=0)
    with_future = generate_opening_predictions([early, target, future], minimum_prior_matches=0)

    assert with_future[1].team_a_probability == without_future[1].team_a_probability
    assert with_future[1].team_a_prior_matches == 1


def test_same_day_results_are_not_available_to_each_other():
    prior = fixture("m1", date(2026, 1, 1), "A", "B", "A")
    first_same_day = fixture("m2", date(2026, 1, 2), "A", "C", "A")
    second_same_day = fixture("m3", date(2026, 1, 2), "A", "D", "D")

    predictions = generate_opening_predictions([prior, first_same_day, second_same_day], minimum_prior_matches=0)

    assert predictions[1].team_a_prior_matches == predictions[2].team_a_prior_matches == 1
    assert predictions[1].team_a_probability == predictions[2].team_a_probability


def test_elo_candidate_remains_safe_from_future_and_same_day_results():
    prior = fixture("m1", date(2026, 1, 1), "A", "B", "A")
    target = fixture("m2", date(2026, 1, 2), "A", "C", "A")
    same_day = fixture("m3", date(2026, 1, 2), "B", "D", "B")
    future = fixture("m4", date(2026, 1, 3), "A", "D", "D")

    without_future = generate_elo_opening_predictions([prior, target, same_day], minimum_prior_matches=0)
    with_future = generate_elo_opening_predictions([prior, target, same_day, future], minimum_prior_matches=0)

    assert with_future[1].team_a_probability == without_future[1].team_a_probability
    assert with_future[2].team_a_probability == without_future[2].team_a_probability
    assert with_future[1].team_a_probability != 0.5


def test_elo_runtime_state_scores_future_fixture_without_mutating_or_using_future_results():
    fixtures = [
        fixture("m1", date(2026, 1, 1), "A", "B", "A"),
        fixture("m2", date(2026, 1, 2), "A", "C", "A"),
        fixture("m3", date(2026, 1, 3), "B", "C", "C"),
    ]
    state = build_elo_runtime_state(fixtures, as_of_date=date(2026, 1, 2))
    before = dict(state.ratings)

    scored = score_elo_opening_fixture(
        state,
        first_team="A",
        second_team="C",
        minimum_prior_matches=2,
    )

    assert scored.first_team_probability > 0.5
    assert scored.coverage_ready is False
    assert state.ratings == before
    assert "C" in state.ratings


def test_low_history_rows_are_not_coverage_ready():
    prediction = generate_opening_predictions(
        [fixture("m1", date(2026, 1, 1), "A", "B", "A")],
        minimum_prior_matches=1,
    )[0]
    assert prediction.coverage_ready is False
    assert evaluate_predictions([prediction]).sample_count == 0


def test_evaluation_reports_candidate_and_neutral_baseline_metrics():
    fixtures = [
        fixture("m1", date(2026, 1, 1), "A", "B", "A"),
        fixture("m2", date(2026, 1, 2), "A", "B", "A"),
        fixture("m3", date(2026, 1, 3), "A", "B", "A"),
    ]
    predictions = generate_opening_predictions(fixtures, minimum_prior_matches=0)
    metrics = evaluate_predictions(predictions)

    assert metrics.sample_count == 3
    assert metrics.brier is not None
    assert metrics.baseline_brier == pytest.approx(0.25)
    assert metrics.historical_win_rate_brier is not None
    assert metrics.log_loss is not None
    assert metrics.baseline_log_loss == pytest.approx(0.6931471805599453)
    assert metrics.historical_win_rate_log_loss is not None
    assert metrics.ece is not None


def test_segment_evaluation_keeps_metadata_out_of_scoring_path():
    fixtures = [
        FixtureOutcome("m1", date(2026, 1, 1), "A", "B", "A", gender="female"),
        FixtureOutcome("m2", date(2026, 1, 2), "A", "B", "B", gender="female"),
    ]
    predictions = generate_opening_predictions(fixtures, minimum_prior_matches=0)
    segments = evaluate_by_segment(predictions, attribute="gender", minimum_samples=1)

    assert set(segments) == {"female"}
    assert segments["female"].sample_count == 2


def test_chronological_holdout_never_splits_a_fixture_date():
    fixtures = [
        fixture("m1", date(2026, 1, 1), "A", "B", "A"),
        fixture("m2", date(2026, 1, 2), "A", "B", "B"),
        fixture("m3", date(2026, 1, 3), "A", "B", "A"),
        fixture("m4", date(2026, 1, 3), "A", "C", "A"),
        fixture("m5", date(2026, 1, 4), "A", "B", "B"),
    ]
    predictions = generate_opening_predictions(fixtures, minimum_prior_matches=0)
    split = split_predictions_chronologically(predictions, holdout_fraction=0.4)

    assert split.holdout_start == date(2026, 1, 3)
    assert {row.fixture.match_date for row in split.calibration} == {date(2026, 1, 1), date(2026, 1, 2)}
    assert {row.fixture.match_date for row in split.holdout} == {date(2026, 1, 3), date(2026, 1, 4)}


def test_calibrator_only_uses_pre_holdout_rows_and_returns_probabilities():
    fixtures = [
        fixture("m1", date(2026, 1, 1), "A", "B", "A"),
        fixture("m2", date(2026, 1, 2), "A", "B", "B"),
        fixture("m3", date(2026, 1, 3), "A", "B", "A"),
        fixture("m4", date(2026, 1, 4), "A", "B", "A"),
        fixture("m5", date(2026, 1, 5), "A", "B", "B"),
    ]
    predictions = generate_opening_predictions(fixtures, minimum_prior_matches=0)
    split = split_predictions_chronologically(predictions, holdout_fraction=0.4)
    calibrator = fit_platt_calibrator(split.calibration)
    transformed = apply_calibration(split.holdout, calibrator)

    assert calibrator.training_sample_count == len(split.calibration)
    assert all(0.0 < row.team_a_probability < 1.0 for row in transformed)
    assert [row.fixture.match_id for row in transformed] == [row.fixture.match_id for row in split.holdout]


def test_calibrator_rejects_single_class_training_data():
    fixtures = [
        fixture("m1", date(2026, 1, 1), "A", "B", "A"),
        fixture("m2", date(2026, 1, 2), "A", "B", "A"),
    ]
    predictions = generate_opening_predictions(fixtures, minimum_prior_matches=0)

    with pytest.raises(ValueError, match="both team-A outcomes"):
        fit_platt_calibrator(predictions)


def test_promotion_gate_requires_calibrated_gender_and_competition_evidence():
    passing = EvaluationMetrics(1_500, 0.22, 0.25, 0.23, 0.62, 0.69, 0.65, 0.03)
    result = assess_promotion_gate(
        passing,
        {"female": EvaluationMetrics(600, 0.22, 0.25, 0.23, 0.62, 0.69, 0.65, 0.06), "male": passing},
        {"unknown": passing},
    )

    assert result.decision == "shadow_only_revise"
    assert any("gender:female: ECE" in reason for reason in result.reasons)
    assert any("competition:" in reason for reason in result.reasons)
