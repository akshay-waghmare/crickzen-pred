"""Chronological, prior-only opening-probability baseline.

The live predictor consumes ball-state features and must not be used before a
match begins.  This module establishes a deliberately small alternative: it
builds fixture outcomes from historical raw data, scores each fixture from
*only earlier dates*, and updates team records after every same-day fixture has
been scored.  It is an offline experiment, never a public-serving path.
"""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import date
import math
from pathlib import Path
import re
from typing import Iterable, Mapping, Sequence


REQUIRED_RAW_COLUMNS = {
    "match_id",
    "date",
    "batting_team_id",
    "bowling_team_id",
    "winner",
}

_EVENT_NAME_PATTERN = re.compile(
    r'"event"\s*:\s*\{.{0,12000}?"name"\s*:\s*"([^"]+)"',
    re.DOTALL,
)


@dataclass(frozen=True)
class FixtureOutcome:
    """One resolved historical fixture in a deterministic team perspective."""

    match_id: str
    match_date: date
    team_a: str
    team_b: str
    winner: str
    league: str | None = None
    gender: str | None = None
    venue: str | None = None


@dataclass(frozen=True)
class OpeningPrediction:
    """An offline opening estimate and the only history used to make it."""

    fixture: FixtureOutcome
    team_a_probability: float
    team_a_historical_win_rate: float
    team_a_prior_matches: int
    team_b_prior_matches: int
    coverage_ready: bool

    @property
    def actual_team_a_win(self) -> int:
        return int(self.fixture.winner == self.fixture.team_a)


@dataclass(frozen=True)
class EvaluationMetrics:
    sample_count: int
    brier: float | None
    baseline_brier: float | None
    historical_win_rate_brier: float | None
    log_loss: float | None
    baseline_log_loss: float | None
    historical_win_rate_log_loss: float | None
    ece: float | None


@dataclass(frozen=True)
class ChronologicalPredictionSplit:
    """Date-disjoint calibration and final-holdout prediction partitions."""

    calibration: tuple[OpeningPrediction, ...]
    holdout: tuple[OpeningPrediction, ...]
    holdout_start: date


@dataclass(frozen=True)
class PlattCalibrator:
    """Small, serializable logistic calibrator for a pre-match probability."""

    intercept: float
    slope: float
    training_sample_count: int

    def transform(self, probability: float) -> float:
        probability = min(max(probability, 1e-6), 1.0 - 1e-6)
        score = self.intercept + self.slope * _logit(probability)
        return _sigmoid(score)


@dataclass(frozen=True)
class PromotionGateResult:
    """Deterministic offline gate; it is not a deployment instruction."""

    decision: str
    reasons: tuple[str, ...]


def _clean_team(value: object) -> str:
    return str(value or "").strip()


def _as_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    try:
        converted = value.to_pydatetime()  # pandas Timestamp
        return converted.date()
    except AttributeError:
        pass
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def build_fixture_outcomes(
    raw_frame: object,
    *,
    competition_by_match_id: Mapping[str, str] | None = None,
) -> list[FixtureOutcome]:
    """Collapse ball rows into resolved fixtures without using match-state data.

    ``batting_team_id`` and ``bowling_team_id`` are used solely to discover the
    two competing teams.  Their ordering is discarded because it depends on
    toss.  Fields such as toss, innings, score, over, and ball are intentionally
    neither read nor accepted as model inputs.
    """

    columns = set(getattr(raw_frame, "columns", []))
    missing = REQUIRED_RAW_COLUMNS - columns
    if missing:
        raise ValueError(f"Raw frame is missing required columns: {sorted(missing)}")

    # The ingestion data has one row per legal ball.  Selecting the first row
    # per match is safe for fixture identity because date, teams, winner and
    # metadata are match-level fields; it does not inspect ball-state fields.
    rows = raw_frame.sort_values(["date", "match_id"]).drop_duplicates("match_id", keep="first")
    outcomes: list[FixtureOutcome] = []
    for row in rows.to_dict(orient="records"):
        first_team = _clean_team(row.get("batting_team_id"))
        second_team = _clean_team(row.get("bowling_team_id"))
        winner = _clean_team(row.get("winner"))
        match_date = _as_date(row.get("date"))
        if not first_team or not second_team or first_team == second_team or not winner or match_date is None:
            continue
        if winner not in {first_team, second_team}:
            # Abandoned/no-result fixtures are not binary training outcomes.
            continue
        team_a, team_b = sorted((first_team, second_team), key=str.casefold)
        outcomes.append(
            FixtureOutcome(
                match_id=str(row["match_id"]),
                match_date=match_date,
                team_a=team_a,
                team_b=team_b,
                winner=winner,
                league=(
                    _usable_competition(row.get("league"))
                    or _usable_competition((competition_by_match_id or {}).get(str(row["match_id"])))
                ),
                gender=_optional_text(row.get("gender")),
                venue=_optional_text(row.get("venue_id")),
            )
        )
    return sorted(outcomes, key=lambda item: (item.match_date, item.match_id))


def _optional_text(value: object) -> str | None:
    text = _clean_team(value)
    return text or None


def _usable_competition(value: object) -> str | None:
    text = _optional_text(value)
    return text if text and text.casefold() not in {"unknown", "none", "nan"} else None


def load_competition_by_match_id(
    json_dir: Path,
    match_ids: Iterable[str],
) -> dict[str, str]:
    """Read exact Cricsheet ``info.event.name`` metadata for known matches.

    ``event.name`` is in the top-level pre-innings `info` object, so it is
    legitimate fixture metadata.  The source is joined only by exact match ID;
    neither team labels nor results are used as a fallback.  A bounded header
    read avoids parsing every ball from the archive during offline reporting.
    """

    requested_ids = sorted({str(match_id) for match_id in match_ids if str(match_id)})

    def read_event_name(match_id: str) -> tuple[str, str | None]:
        path = json_dir / f"{match_id}.json"
        try:
            with path.open("r", encoding="utf-8") as handle:
                header = handle.read(64 * 1024)
        except OSError:
            return match_id, None
        match = _EVENT_NAME_PATTERN.search(header)
        return match_id, _usable_competition(match.group(1) if match else None)

    with ThreadPoolExecutor(max_workers=16) as executor:
        pairs = list(executor.map(read_event_name, requested_ids))
    return {match_id: name for match_id, name in pairs if name}


def generate_opening_predictions(
    fixtures: Iterable[FixtureOutcome],
    *,
    alpha: float = 2.0,
    beta: float = 2.0,
    minimum_prior_matches: int = 5,
) -> list[OpeningPrediction]:
    """Score sorted fixtures from prior-only smoothed team records.

    Fixtures sharing the same date are all scored before any result from that
    date updates a team record.  This prevents same-day result leakage.
    """

    if alpha <= 0 or beta <= 0:
        raise ValueError("alpha and beta must be positive")
    if minimum_prior_matches < 0:
        raise ValueError("minimum_prior_matches must be non-negative")

    ordered = sorted(fixtures, key=lambda item: (item.match_date, item.match_id))
    wins: dict[str, int] = defaultdict(int)
    matches: dict[str, int] = defaultdict(int)
    predictions: list[OpeningPrediction] = []
    position = 0

    while position < len(ordered):
        fixture_date = ordered[position].match_date
        end = position
        while end < len(ordered) and ordered[end].match_date == fixture_date:
            end += 1
        same_day = ordered[position:end]

        for fixture in same_day:
            team_a_games = matches[fixture.team_a]
            team_b_games = matches[fixture.team_b]
            team_a_strength = (wins[fixture.team_a] + alpha) / (team_a_games + alpha + beta)
            team_b_strength = (wins[fixture.team_b] + alpha) / (team_b_games + alpha + beta)
            probability = team_a_strength / (team_a_strength + team_b_strength)
            predictions.append(
                OpeningPrediction(
                    fixture=fixture,
                    team_a_probability=probability,
                    team_a_historical_win_rate=team_a_strength,
                    team_a_prior_matches=team_a_games,
                    team_b_prior_matches=team_b_games,
                    coverage_ready=(
                        team_a_games >= minimum_prior_matches
                        and team_b_games >= minimum_prior_matches
                    ),
                )
            )

        for fixture in same_day:
            matches[fixture.team_a] += 1
            matches[fixture.team_b] += 1
            wins[fixture.winner] += 1
        position = end

    return predictions


def generate_elo_opening_predictions(
    fixtures: Iterable[FixtureOutcome],
    *,
    k_factor: float = 64.0,
    rating_scale: float = 400.0,
    initial_rating: float = 1500.0,
    alpha: float = 2.0,
    beta: float = 2.0,
    minimum_prior_matches: int = 5,
) -> list[OpeningPrediction]:
    """Score fixtures with date-safe Elo strength and prior-only coverage.

    Elo is deliberately a separate candidate from the smoothed win-rate
    baseline. Ratings and win counts are updated only after every fixture on a
    given date has been scored, so neither same-day nor future results can
    affect an opening estimate. The historical win-rate field is retained only
    for the fixed comparison baseline in :func:`evaluate_predictions`.
    """

    if k_factor <= 0 or rating_scale <= 0:
        raise ValueError("k_factor and rating_scale must be positive")
    if alpha <= 0 or beta <= 0:
        raise ValueError("alpha and beta must be positive")
    if minimum_prior_matches < 0:
        raise ValueError("minimum_prior_matches must be non-negative")

    ordered = sorted(fixtures, key=lambda item: (item.match_date, item.match_id))
    ratings: dict[str, float] = defaultdict(lambda: initial_rating)
    wins: dict[str, int] = defaultdict(int)
    matches: dict[str, int] = defaultdict(int)
    predictions: list[OpeningPrediction] = []
    position = 0

    while position < len(ordered):
        fixture_date = ordered[position].match_date
        end = position
        while end < len(ordered) and ordered[end].match_date == fixture_date:
            end += 1
        same_day = ordered[position:end]

        for fixture in same_day:
            team_a_games = matches[fixture.team_a]
            team_b_games = matches[fixture.team_b]
            rating_difference = ratings[fixture.team_b] - ratings[fixture.team_a]
            probability = 1.0 / (1.0 + 10.0 ** (rating_difference / rating_scale))
            historical_win_rate = (wins[fixture.team_a] + alpha) / (team_a_games + alpha + beta)
            predictions.append(
                OpeningPrediction(
                    fixture=fixture,
                    team_a_probability=probability,
                    team_a_historical_win_rate=historical_win_rate,
                    team_a_prior_matches=team_a_games,
                    team_b_prior_matches=team_b_games,
                    coverage_ready=(
                        team_a_games >= minimum_prior_matches
                        and team_b_games >= minimum_prior_matches
                    ),
                )
            )

        for fixture in same_day:
            rating_difference = ratings[fixture.team_b] - ratings[fixture.team_a]
            expected_team_a_win = 1.0 / (1.0 + 10.0 ** (rating_difference / rating_scale))
            actual_team_a_win = int(fixture.winner == fixture.team_a)
            adjustment = k_factor * (actual_team_a_win - expected_team_a_win)
            ratings[fixture.team_a] += adjustment
            ratings[fixture.team_b] -= adjustment
            matches[fixture.team_a] += 1
            matches[fixture.team_b] += 1
            wins[fixture.winner] += 1
        position = end

    return predictions


def evaluate_predictions(
    predictions: Sequence[OpeningPrediction],
    *,
    require_coverage_ready: bool = True,
    ece_bins: int = 10,
) -> EvaluationMetrics:
    """Compare a candidate with a neutral 0.50 baseline using offline rows."""

    if ece_bins < 2:
        raise ValueError("ece_bins must be at least 2")
    rows = [row for row in predictions if row.coverage_ready or not require_coverage_ready]
    if not rows:
        return EvaluationMetrics(0, None, None, None, None, None, None, None)

    values = [min(max(row.team_a_probability, 1e-6), 1.0 - 1e-6) for row in rows]
    actuals = [row.actual_team_a_win for row in rows]
    brier = sum((probability - actual) ** 2 for probability, actual in zip(values, actuals)) / len(rows)
    baseline_brier = sum((0.5 - actual) ** 2 for actual in actuals) / len(rows)
    historical_values = [min(max(row.team_a_historical_win_rate, 1e-6), 1.0 - 1e-6) for row in rows]
    historical_win_rate_brier = sum(
        (probability - actual) ** 2 for probability, actual in zip(historical_values, actuals)
    ) / len(rows)
    log_loss = -sum(
        actual * math.log(probability) + (1 - actual) * math.log(1 - probability)
        for probability, actual in zip(values, actuals)
    ) / len(rows)
    baseline_log_loss = math.log(2.0)
    historical_win_rate_log_loss = -sum(
        actual * math.log(probability) + (1 - actual) * math.log(1 - probability)
        for probability, actual in zip(historical_values, actuals)
    ) / len(rows)
    ece = _expected_calibration_error(actuals, values, ece_bins)
    return EvaluationMetrics(
        len(rows),
        brier,
        baseline_brier,
        historical_win_rate_brier,
        log_loss,
        baseline_log_loss,
        historical_win_rate_log_loss,
        ece,
    )


def evaluate_by_segment(
    predictions: Sequence[OpeningPrediction],
    *,
    attribute: str,
    minimum_samples: int = 50,
    require_coverage_ready: bool = True,
) -> dict[str, EvaluationMetrics]:
    """Evaluate only material fixture metadata segments, without re-scoring.

    Segment metadata is attached to the fixture at ingestion time.  It changes
    reporting only; no segment value is retroactively used as a model feature.
    """

    if attribute not in {"gender", "league"}:
        raise ValueError("attribute must be 'gender' or 'league'")
    if minimum_samples < 1:
        raise ValueError("minimum_samples must be positive")
    groups: dict[str, list[OpeningPrediction]] = defaultdict(list)
    for prediction in predictions:
        value = getattr(prediction.fixture, attribute) or "unknown"
        groups[str(value)].append(prediction)
    return {
        key: evaluate_predictions(rows, require_coverage_ready=require_coverage_ready)
        for key, rows in sorted(groups.items())
        if len(rows) >= minimum_samples
    }


def split_predictions_chronologically(
    predictions: Sequence[OpeningPrediction],
    *,
    holdout_fraction: float = 0.2,
    require_coverage_ready: bool = True,
) -> ChronologicalPredictionSplit:
    """Reserve the newest whole fixture dates for a final unseen evaluation.

    Earlier rows may train a calibrator, but no match on a holdout date can
    enter that calibration set.  The underlying predictions are already
    prior-only; the date split protects the second-stage calibrator too.
    """

    if not 0.0 < holdout_fraction < 1.0:
        raise ValueError("holdout_fraction must be between zero and one")
    rows = [row for row in predictions if row.coverage_ready or not require_coverage_ready]
    dates = sorted({row.fixture.match_date for row in rows})
    if len(dates) < 2:
        raise ValueError("At least two distinct prediction dates are required for a holdout")
    holdout_dates = max(1, math.ceil(len(dates) * holdout_fraction))
    if holdout_dates >= len(dates):
        raise ValueError("Holdout leaves no calibration dates")
    holdout_start = dates[-holdout_dates]
    calibration = tuple(row for row in rows if row.fixture.match_date < holdout_start)
    holdout = tuple(row for row in rows if row.fixture.match_date >= holdout_start)
    if not calibration or not holdout:
        raise ValueError("Chronological split produced an empty partition")
    return ChronologicalPredictionSplit(calibration, holdout, holdout_start)


def fit_platt_calibrator(
    predictions: Sequence[OpeningPrediction],
    *,
    require_coverage_ready: bool = True,
    l2_penalty: float = 1e-3,
    max_iterations: int = 100,
) -> PlattCalibrator:
    """Fit logistic calibration only from historical prediction outcomes.

    The implementation deliberately has no ML-library dependency so the
    eventual serving artifact contains only two numeric parameters.  It uses
    a lightly regularized Newton update over logit(candidate_probability).
    """

    if l2_penalty < 0:
        raise ValueError("l2_penalty must be non-negative")
    rows = [row for row in predictions if row.coverage_ready or not require_coverage_ready]
    if len(rows) < 2:
        raise ValueError("At least two calibration rows are required")
    targets = [row.actual_team_a_win for row in rows]
    if len(set(targets)) != 2:
        raise ValueError("Calibration requires both team-A outcomes")
    features = [_logit(row.team_a_probability) for row in rows]
    prevalence = min(max(sum(targets) / len(targets), 1e-6), 1.0 - 1e-6)
    intercept = _logit(prevalence)
    slope = 1.0

    for _ in range(max_iterations):
        fitted = [_sigmoid(intercept + slope * feature) for feature in features]
        residuals = [probability - target for probability, target in zip(fitted, targets)]
        weights = [probability * (1.0 - probability) for probability in fitted]
        gradient_intercept = sum(residuals)
        gradient_slope = sum(residual * feature for residual, feature in zip(residuals, features)) + l2_penalty * slope
        hessian_ii = sum(weights) + l2_penalty
        hessian_is = sum(weight * feature for weight, feature in zip(weights, features))
        hessian_ss = sum(weight * feature * feature for weight, feature in zip(weights, features)) + l2_penalty
        determinant = hessian_ii * hessian_ss - hessian_is * hessian_is
        if determinant <= 1e-12:
            break
        delta_intercept = (hessian_ss * gradient_intercept - hessian_is * gradient_slope) / determinant
        delta_slope = (-hessian_is * gradient_intercept + hessian_ii * gradient_slope) / determinant
        intercept -= delta_intercept
        slope -= delta_slope
        if max(abs(delta_intercept), abs(delta_slope)) < 1e-8:
            break

    return PlattCalibrator(intercept, slope, len(rows))


def apply_calibration(
    predictions: Sequence[OpeningPrediction],
    calibrator: PlattCalibrator,
) -> list[OpeningPrediction]:
    """Return copies of predictions with only the candidate probability mapped."""

    return [
        replace(row, team_a_probability=calibrator.transform(row.team_a_probability))
        for row in predictions
    ]


def assess_promotion_gate(
    overall: EvaluationMetrics,
    gender_segments: dict[str, EvaluationMetrics],
    league_segments: dict[str, EvaluationMetrics],
    *,
    minimum_overall_samples: int = 1_000,
    minimum_segment_samples: int = 500,
    minimum_brier_improvement: float = 0.002,
    maximum_ece: float = 0.05,
) -> PromotionGateResult:
    """Apply the written opening-model promotion thresholds consistently.

    A production release needs more gates (identity, ingress, TTL, SSR and
    live proof).  This function only decides whether the offline estimator can
    advance beyond shadow evaluation.
    """

    reasons: list[str] = []

    def assess_metrics(label: str, metrics: EvaluationMetrics) -> None:
        if metrics.sample_count < (minimum_overall_samples if label == "overall" else minimum_segment_samples):
            reasons.append(f"{label}: insufficient sample count ({metrics.sample_count})")
            return
        values = (
            metrics.brier,
            metrics.baseline_brier,
            metrics.historical_win_rate_brier,
            metrics.log_loss,
            metrics.baseline_log_loss,
            metrics.historical_win_rate_log_loss,
            metrics.ece,
        )
        if any(value is None for value in values):
            reasons.append(f"{label}: metric is unavailable")
            return
        assert metrics.brier is not None and metrics.baseline_brier is not None
        assert metrics.historical_win_rate_brier is not None
        assert metrics.log_loss is not None and metrics.baseline_log_loss is not None
        assert metrics.historical_win_rate_log_loss is not None and metrics.ece is not None
        if metrics.brier > metrics.baseline_brier - minimum_brier_improvement:
            reasons.append(f"{label}: Brier does not beat neutral by {minimum_brier_improvement:.3f}")
        if metrics.brier > metrics.historical_win_rate_brier - minimum_brier_improvement:
            reasons.append(f"{label}: Brier does not beat historical rate by {minimum_brier_improvement:.3f}")
        if metrics.log_loss >= metrics.baseline_log_loss:
            reasons.append(f"{label}: log loss does not beat neutral")
        if metrics.log_loss >= metrics.historical_win_rate_log_loss:
            reasons.append(f"{label}: log loss does not beat historical rate")
        if metrics.ece > maximum_ece:
            reasons.append(f"{label}: ECE {metrics.ece:.3f} exceeds {maximum_ece:.3f}")

    assess_metrics("overall", overall)
    for gender in ("female", "male"):
        if gender not in gender_segments:
            reasons.append(f"gender:{gender}: required segment is unavailable")
        else:
            assess_metrics(f"gender:{gender}", gender_segments[gender])
    named_leagues = {name: metrics for name, metrics in league_segments.items() if name != "unknown"}
    if not named_leagues:
        reasons.append("competition: no named-league holdout segment is available")
    else:
        for league, metrics in named_leagues.items():
            if metrics.sample_count >= minimum_segment_samples:
                assess_metrics(f"league:{league}", metrics)

    return PromotionGateResult(
        "promote_candidate" if not reasons else "shadow_only_revise",
        tuple(reasons),
    )


def _expected_calibration_error(actuals: Sequence[int], values: Sequence[float], bins: int) -> float:
    total = len(values)
    error = 0.0
    for bucket in range(bins):
        low = bucket / bins
        high = (bucket + 1) / bins
        indices = [
            index
            for index, probability in enumerate(values)
            if low <= probability < high or (bucket == bins - 1 and probability == 1.0)
        ]
        if not indices:
            continue
        confidence = sum(values[index] for index in indices) / len(indices)
        accuracy = sum(actuals[index] for index in indices) / len(indices)
        error += len(indices) / total * abs(confidence - accuracy)
    return error


def _logit(probability: float) -> float:
    probability = min(max(probability, 1e-6), 1.0 - 1e-6)
    return math.log(probability / (1.0 - probability))


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)
