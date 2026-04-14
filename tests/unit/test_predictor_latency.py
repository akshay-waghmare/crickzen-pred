"""
T021: Inference latency test for Predictor.

Asserts:
  - p50 latency < 50ms  (target)
  - p99 latency < 100ms (hard ceiling)

Requires a trained model in the directory pointed to by the environment
variable LATENCY_TEST_MODEL_DIR, OR falls back to models/bbl_v12.
If neither exists the test is skipped automatically (no CI failure).
"""
import os
import time
import statistics
from pathlib import Path

import pytest

from bbl_pipeline.inference.schema import MatchState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FALLBACK_MODEL_DIRS = [
    "models/bbl_v12",
    "models/t20_male_v2",
    "models/ilt20_v5",
]
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _find_model_dir():
    env_dir = os.environ.get("LATENCY_TEST_MODEL_DIR")
    if env_dir and Path(env_dir).exists():
        return Path(env_dir)
    for rel in _FALLBACK_MODEL_DIRS:
        candidate = _PROJECT_ROOT / rel
        if (candidate / "champion_model.joblib").exists():
            return candidate
    return None


def _make_state(idx: int = 0) -> MatchState:
    """Return a realistic second-innings MatchState."""
    return MatchState(
        match_id=f"latency_test_{idx}",
        venue="Melbourne Cricket Ground",
        batting_team="Melbourne Stars",
        bowling_team="Sydney Sixers",
        innings=2,
        over=12,
        ball=3,
        current_score=98,
        wickets_lost=3,
        batsman_1="David Warner",
        batsman_2="Steve Smith",
        bowler="Josh Hazlewood",
        target_runs=168,
        total_overs=20,
    )


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def loaded_predictor():
    model_dir = _find_model_dir()
    if model_dir is None:
        pytest.skip("No trained model found for latency test (set LATENCY_TEST_MODEL_DIR)")
    from bbl_pipeline.inference.predictor import Predictor
    return Predictor.load(str(model_dir))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

N_CALLS = 100


def test_predict_latency_p50_under_50ms(loaded_predictor):
    """p50 latency must be < 50ms (127 budget for TimesFM/MC overlay layers)."""
    latencies = []
    for i in range(N_CALLS):
        state = _make_state(i)
        t0 = time.perf_counter()
        loaded_predictor.predict(state)
        latencies.append((time.perf_counter() - t0) * 1000)  # ms

    p50 = statistics.median(latencies)
    assert p50 < 50, (
        f"p50 latency {p50:.1f}ms exceeds 50ms target. "
        f"min={min(latencies):.1f}ms max={max(latencies):.1f}ms"
    )


def test_predict_latency_p99_under_100ms(loaded_predictor):
    """p99 latency must be < 100ms (hard ceiling)."""
    latencies = []
    for i in range(N_CALLS):
        state = _make_state(i)
        t0 = time.perf_counter()
        loaded_predictor.predict(state)
        latencies.append((time.perf_counter() - t0) * 1000)  # ms

    latencies_sorted = sorted(latencies)
    p99_idx = int(0.99 * len(latencies_sorted))
    p99 = latencies_sorted[p99_idx]
    assert p99 < 100, (
        f"p99 latency {p99:.1f}ms exceeds 100ms hard ceiling. "
        f"p50={statistics.median(latencies):.1f}ms max={max(latencies):.1f}ms"
    )


def test_explain_returns_expected_keys(loaded_predictor):
    """explain() must return win_probability, features, contributions."""
    state = _make_state()
    result = loaded_predictor.explain(state)
    assert "win_probability" in result
    assert "features" in result
    assert "contributions" in result
    assert 0.0 <= result["win_probability"] <= 1.0
    assert len(result["features"]) > 0
