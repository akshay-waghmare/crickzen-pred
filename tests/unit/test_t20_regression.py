"""T20 regression tests — verify calculator output is identical after refactoring.

These tests load pre-computed snapshots (``test_t20_regression_snapshots.json``)
that capture the output of :class:`ResourceFeatureCalculator` for 10 diverse
match states.  After any refactoring (e.g. parameterising constants via
:class:`FormatConfig`), **every feature value must be identical** to the
snapshot baseline.

Run with::

    pytest tests/unit/test_t20_regression.py -v
"""

import json
import math
from pathlib import Path

import pytest

from bbl_pipeline.features.calculator import ResourceFeatureCalculator


SNAPSHOT_PATH = Path(__file__).parent / "test_t20_regression_snapshots.json"

# Tolerance for floating-point comparison (should essentially be zero)
RTOL = 1e-9
ATOL = 1e-12


@pytest.fixture(scope="module")
def snapshots():
    with open(SNAPSHOT_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def calculator():
    return ResourceFeatureCalculator()


def _close(a, b):
    """Check two values are nearly identical."""
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if math.isnan(a) and math.isnan(b):
            return True
        return math.isclose(a, b, rel_tol=RTOL, abs_tol=ATOL)
    return a == b


@pytest.mark.parametrize(
    "state_label",
    [
        "inn1_early_pp_0w",
        "inn1_mid_pp_1w",
        "inn1_mid_overs_2w",
        "inn1_mid_struggling_5w",
        "inn1_death_3w",
        "inn1_final_4w",
        "inn2_early_chase_0w",
        "inn2_mid_chase_3w",
        "inn2_comfortable_2w",
        "inn2_endgame_6w",
    ],
)
def test_t20_regression(state_label: str, snapshots, calculator):
    """Each snapshot match state must reproduce the exact same features."""
    snap = snapshots[state_label]
    inp = snap["input"]

    actual = calculator.calculate_all_features(
        innings=inp["innings"],
        over=inp["over"],
        ball=inp["ball"],
        current_score=inp["current_score"],
        wickets_lost=inp["wickets_lost"],
        target_runs=inp.get("target_runs"),
    )

    expected = snap["expected_output"]
    for key, expected_val in expected.items():
        actual_val = actual.get(key)
        assert actual_val is not None, (
            f"[{state_label}] Missing feature '{key}' in calculator output"
        )
        assert _close(actual_val, expected_val), (
            f"[{state_label}] Feature '{key}' changed: "
            f"expected {expected_val}, got {actual_val}"
        )


def test_snapshot_file_exists():
    """Ensure the snapshot file is present before running regression tests."""
    assert SNAPSHOT_PATH.exists(), (
        f"Snapshot file not found at {SNAPSHOT_PATH}. "
        "Regenerate with T003 task script."
    )
