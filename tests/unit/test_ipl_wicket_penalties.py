"""Tests for IPL-specific wicket penalty overrides in FormatConfig.ipl().

Validates:
- chase_wicket_penalty_2d structure and values
- first_innings_wicket_penalty_3d structure and values
- FR-002: IPL chase penalties strictly less than T20 base for wickets 4-8
- Monotonic decrease and boundary constraints
"""

import pytest

from bbl_pipeline.features.format_config import FormatConfig

EASE_LEVELS = ["very_easy", "easy", "comfortable", "tough", "desperate"]
PHASES = ["powerplay", "middle", "death", "final"]
EASE_BUCKETS_1ST = ["well_ahead", "ahead", "par", "behind", "well_behind"]

# T20 base chase penalties for FR-002 comparison
T20_BASE_CHASE = {
    "very_easy":   {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00, 5: 0.88, 6: 0.76, 7: 0.56, 8: 0.24, 9: 0.05, 10: 0.00},
    "easy":        {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00, 5: 1.00, 6: 1.00, 7: 1.00, 8: 0.44, 9: 0.22, 10: 0.00},
    "comfortable": {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00, 5: 1.00, 6: 1.00, 7: 1.00, 8: 0.62, 9: 0.74, 10: 0.00},
    "tough":       {0: 1.00, 1: 0.93, 2: 0.90, 3: 0.88, 4: 0.76, 5: 0.79, 6: 0.71, 7: 0.70, 8: 0.34, 9: 0.05, 10: 0.00},
    "desperate":   {0: 1.00, 1: 0.72, 2: 0.46, 3: 0.35, 4: 0.21, 5: 0.21, 6: 0.15, 7: 0.08, 8: 0.05, 9: 0.01, 10: 0.00},
}


@pytest.fixture
def ipl_config():
    return FormatConfig.ipl()


# ── chase_wicket_penalty_2d structure ────────────────────────────────


class TestChaseWicketPenalty2dStructure:
    """Validate chase_wicket_penalty_2d has the correct shape."""

    def test_has_all_ease_levels(self, ipl_config):
        """All 5 ease levels must be present."""
        for ease in EASE_LEVELS:
            assert ease in ipl_config.chase_wicket_penalty_2d, (
                f"Missing ease level: {ease}"
            )

    def test_each_ease_has_wickets_0_to_10(self, ipl_config):
        """Each ease level must map wickets 0-10."""
        for ease in EASE_LEVELS:
            penalties = ipl_config.chase_wicket_penalty_2d[ease]
            for w in range(11):
                assert w in penalties, (
                    f"chase_wicket_penalty_2d[{ease}] missing wicket {w}"
                )


# ── FR-002: IPL < T20 base for wickets 4-8 ──────────────────────────


class TestFR002ChaseStrictlyLess:
    """FR-002: For wickets 4-8, IPL penalties must be STRICTLY LESS than T20 base."""

    @pytest.mark.parametrize("ease", EASE_LEVELS)
    @pytest.mark.parametrize("wicket", [4, 5, 6, 7, 8])
    def test_ipl_less_than_t20_base(self, ipl_config, ease, wicket):
        ipl_val = ipl_config.chase_wicket_penalty_2d[ease][wicket]
        t20_val = T20_BASE_CHASE[ease][wicket]
        assert ipl_val < t20_val, (
            f"FR-002 violated: IPL {ease}[{wicket}]={ipl_val} "
            f"should be < T20 base {t20_val}"
        )


# ── Chase monotonicity and boundaries ───────────────────────────────


class TestChaseMonotonicityAndBoundaries:
    """Penalty must be non-increasing and respect 0/10 boundary values."""

    @pytest.mark.parametrize("ease", EASE_LEVELS)
    def test_boundary_zero_wickets(self, ipl_config, ease):
        assert ipl_config.chase_wicket_penalty_2d[ease][0] == 1.0

    @pytest.mark.parametrize("ease", EASE_LEVELS)
    def test_boundary_ten_wickets(self, ipl_config, ease):
        assert ipl_config.chase_wicket_penalty_2d[ease][10] == 0.0

    @pytest.mark.parametrize("ease", EASE_LEVELS)
    def test_monotonic_decrease(self, ipl_config, ease):
        penalties = ipl_config.chase_wicket_penalty_2d[ease]
        for w in range(1, 11):
            assert penalties[w] <= penalties[w - 1], (
                f"chase[{ease}]: penalty[{w}]={penalties[w]} > "
                f"penalty[{w-1}]={penalties[w-1]}"
            )


# ── first_innings_wicket_penalty_3d structure ────────────────────────


class TestFirstInningsWicketPenalty3dStructure:
    """Validate first_innings_wicket_penalty_3d has 4 phases × 5 ease × 11 wickets."""

    def test_has_all_phases(self, ipl_config):
        for phase in PHASES:
            assert phase in ipl_config.first_innings_wicket_penalty_3d, (
                f"Missing phase: {phase}"
            )

    def test_each_phase_has_all_ease_buckets(self, ipl_config):
        for phase in PHASES:
            for ease in EASE_BUCKETS_1ST:
                assert ease in ipl_config.first_innings_wicket_penalty_3d[phase], (
                    f"first_innings[{phase}] missing ease bucket: {ease}"
                )

    def test_each_bucket_has_wickets_0_to_10(self, ipl_config):
        for phase in PHASES:
            for ease in EASE_BUCKETS_1ST:
                penalties = ipl_config.first_innings_wicket_penalty_3d[phase][ease]
                for w in range(11):
                    assert w in penalties, (
                        f"first_innings[{phase}][{ease}] missing wicket {w}"
                    )


# ── First innings monotonicity and boundaries ────────────────────────


class TestFirstInningsMonotonicityAndBoundaries:
    """Same non-increasing / boundary constraints for first innings."""

    @pytest.mark.parametrize("phase", PHASES)
    @pytest.mark.parametrize("ease", EASE_BUCKETS_1ST)
    def test_boundary_zero_wickets(self, ipl_config, phase, ease):
        assert ipl_config.first_innings_wicket_penalty_3d[phase][ease][0] == 1.0

    @pytest.mark.parametrize("phase", PHASES)
    @pytest.mark.parametrize("ease", EASE_BUCKETS_1ST)
    def test_boundary_ten_wickets(self, ipl_config, phase, ease):
        assert ipl_config.first_innings_wicket_penalty_3d[phase][ease][10] == 0.0

    @pytest.mark.parametrize("phase", PHASES)
    @pytest.mark.parametrize("ease", EASE_BUCKETS_1ST)
    def test_monotonic_decrease(self, ipl_config, phase, ease):
        penalties = ipl_config.first_innings_wicket_penalty_3d[phase][ease]
        for w in range(1, 11):
            assert penalties[w] <= penalties[w - 1], (
                f"first_innings[{phase}][{ease}]: penalty[{w}]={penalties[w]} > "
                f"penalty[{w-1}]={penalties[w-1]}"
            )
