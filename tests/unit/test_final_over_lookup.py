"""Unit tests for the final-over empirical win-probability lookup."""

import pytest
from bbl_pipeline.features.win_prob_lookup_tables import (
    get_final_over_win_prob,
    FINAL_OVER_WIN_PROB,
)


# ── T1: runs_needed <= 0 always returns 1.0 ───────────────────────────
@pytest.mark.parametrize("runs,wickets", [
    (0, 1), (0, 5), (0, 10), (-1, 3), (-5, 1),
])
def test_runs_lte_zero_returns_one(runs, wickets):
    assert get_final_over_win_prob(runs, wickets) == 1.0


# ── T2: wickets_in_hand <= 0 always returns 0.0 ───────────────────────
@pytest.mark.parametrize("runs,wickets", [
    (1, 0), (10, 0), (25, -1),
])
def test_wickets_lte_zero_returns_zero(runs, wickets):
    assert get_final_over_win_prob(runs, wickets) == 0.0


# ── T3: runs_needed > 25 returns 0.01 ─────────────────────────────────
@pytest.mark.parametrize("runs", [26, 30, 50, 100])
def test_runs_beyond_table_returns_near_zero(runs):
    assert get_final_over_win_prob(runs, 5) == 0.01


# ── T4: High runs + low wickets → near-zero ───────────────────────────
@pytest.mark.parametrize("runs,wickets", [
    (20, 1), (20, 2), (22, 1), (25, 2),
])
def test_high_runs_low_wickets_near_zero(runs, wickets):
    prob = get_final_over_win_prob(runs, wickets)
    assert prob < 0.01, f"Expected near-zero, got {prob}"


# ── T5: Monotonic decrease on runs axis (fixed wickets) ───────────────
@pytest.mark.parametrize("wickets", [1, 3, 5, 8, 10])
def test_monotonic_decrease_on_runs(wickets):
    probs = [get_final_over_win_prob(r, wickets) for r in range(1, 26)]
    for i in range(len(probs) - 1):
        assert probs[i] >= probs[i + 1], (
            f"Non-monotonic at runs={i+1}->{i+2}, wickets={wickets}: "
            f"{probs[i]} < {probs[i+1]}"
        )


# ── T6: Monotonic increase on wickets axis (fixed runs) ──────────────
@pytest.mark.parametrize("runs", [1, 5, 10, 15, 20])
def test_monotonic_increase_on_wickets(runs):
    probs = [get_final_over_win_prob(runs, w) for w in range(1, 11)]
    for i in range(len(probs) - 1):
        assert probs[i] <= probs[i + 1], (
            f"Non-monotonic at wickets={i+1}->{i+2}, runs={runs}: "
            f"{probs[i]} > {probs[i+1]}"
        )


# ── T7: All table entries in [0.0, 1.0] ──────────────────────────────
def test_all_values_in_valid_range():
    for runs_needed, wkt_dict in FINAL_OVER_WIN_PROB.items():
        for wkts, prob in wkt_dict.items():
            assert 0.0 <= prob <= 1.0, (
                f"Out of range at runs={runs_needed}, wickets={wkts}: {prob}"
            )


# ── T8: Interpolation for sparse / missing cells ─────────────────────
def test_interpolation_with_custom_sparse_table():
    """A hand-crafted sparse table to verify interpolation fills in gaps."""
    sparse = {
        0: {0: 1.0, 5: 1.0, 10: 1.0},
        10: {0: 0.0, 5: 0.5, 10: 0.8},
        20: {0: 0.0, 5: 0.1, 10: 0.3},
    }
    # Exact hits
    assert get_final_over_win_prob(0, 5, lookup_table=sparse) == 1.0
    assert get_final_over_win_prob(10, 5, lookup_table=sparse) == 0.5

    # Interpolated along runs axis (wickets=5 exists, runs=5 missing)
    interp = get_final_over_win_prob(5, 5, lookup_table=sparse)
    assert 0.5 < interp < 1.0, f"Expected between 0.5 and 1.0, got {interp}"

    # Interpolated along wickets axis (runs=10 exists, wickets=3 missing)
    interp_w = get_final_over_win_prob(10, 3, lookup_table=sparse)
    assert 0.0 < interp_w < 0.5, f"Expected between 0.0 and 0.5, got {interp_w}"

    # All interpolated values must stay in [0, 1]
    for r in range(0, 21):
        for w in range(0, 11):
            p = get_final_over_win_prob(r, w, lookup_table=sparse)
            assert 0.0 <= p <= 1.0, f"Out of range at r={r}, w={w}: {p}"


def test_direct_table_hits_match_constant():
    """Spot-check a few known values from the constant table."""
    assert get_final_over_win_prob(1, 1) == pytest.approx(0.2935)
    assert get_final_over_win_prob(10, 10) == pytest.approx(0.5)
    assert get_final_over_win_prob(25, 10) == pytest.approx(0.0006)
