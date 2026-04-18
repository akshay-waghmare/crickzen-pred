"""Tests for IPL first-innings scoring midpoint configuration.

Validates:
- FormatConfig.ipl().first_innings_score_midpoint is IPL-specific (not T20 default)
- Venue-adjusted midpoint formula in ResourceFeatureCalculator
"""

import pytest

from bbl_pipeline.features.format_config import FormatConfig
from bbl_pipeline.features.calculator import ResourceFeatureCalculator


@pytest.fixture
def ipl_config():
    return FormatConfig.ipl()


@pytest.fixture
def ipl_calculator(ipl_config):
    return ResourceFeatureCalculator(config=ipl_config)


# ── FormatConfig midpoint value ─────────────────────────────────────


class TestIPLScoringMidpoint:
    """Verify first_innings_score_midpoint is IPL-tuned."""

    def test_midpoint_in_expected_range(self, ipl_config):
        """Midpoint should be within ±3 of 173.45 (170–176)."""
        assert 170.0 <= ipl_config.first_innings_score_midpoint <= 176.0

    def test_midpoint_not_t20_default(self, ipl_config):
        """Must NOT inherit the generic T20 default of 165.0."""
        assert ipl_config.first_innings_score_midpoint != 165.0

    def test_midpoint_exact_value(self, ipl_config):
        """Current implementation sets midpoint to 173.0."""
        assert ipl_config.first_innings_score_midpoint == 173.0

    def test_beta_value_preserved(self, ipl_config):
        """first_innings_score_beta should remain 0.04."""
        assert ipl_config.first_innings_score_beta == 0.04


# ── Venue-adjusted midpoint helper ──────────────────────────────────


class TestVenueAdjustedMidpoint:
    """Verify _get_venue_adjusted_midpoint() formula."""

    def test_chinnaswamy_high_scoring(self, ipl_calculator):
        """Chinnaswamy (venue_avg=184): midpoint = 173.0 + 0.7*(184-167.28)."""
        result = ipl_calculator._get_venue_adjusted_midpoint(venue_avg_score=184)
        expected = 173.0 + 0.7 * (184 - 167.28)  # 184.704
        assert result == pytest.approx(expected, abs=0.01)

    def test_chepauk_low_scoring(self, ipl_calculator):
        """Chepauk (venue_avg=156): midpoint = 173.0 + 0.7*(156-167.28)."""
        result = ipl_calculator._get_venue_adjusted_midpoint(venue_avg_score=156)
        expected = 173.0 + 0.7 * (156 - 167.28)  # 165.104
        assert result == pytest.approx(expected, abs=0.01)

    def test_unknown_venue_defaults_to_league(self, ipl_calculator):
        """Unknown venue (None) should return the league midpoint unchanged."""
        result = ipl_calculator._get_venue_adjusted_midpoint(venue_avg_score=None)
        assert result == 173.0

    def test_venue_at_league_average(self, ipl_calculator):
        """Venue matching league avg (167.28) should give league midpoint."""
        result = ipl_calculator._get_venue_adjusted_midpoint(venue_avg_score=167.28)
        assert result == pytest.approx(173.0, abs=0.01)
