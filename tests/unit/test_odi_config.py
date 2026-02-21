"""Tests for ODI FormatConfig and Calculator integration.

Validates:
  - FormatConfig.odi() instantiates for both genders
  - All fields are populated with empirical constants
  - Calculator produces reasonable ODI win probabilities
  - Phase mapping is correct for 50-over format
  - from_league() resolves ODI leagues correctly
"""

import pytest
from bbl_pipeline.features.format_config import FormatConfig
from bbl_pipeline.features.calculator import ResourceFeatureCalculator


# ═══════════════════════════════════════════════════════════════════════════
# FormatConfig.odi() tests
# ═══════════════════════════════════════════════════════════════════════════


class TestODIFormatConfig:
    """Test ODI format configuration constants."""

    def test_odi_male_instantiates(self):
        config = FormatConfig.odi("male")
        assert config.format_name == "odi"
        assert config.gender == "male"

    def test_odi_female_instantiates(self):
        config = FormatConfig.odi("female")
        assert config.format_name == "odi"
        assert config.gender == "female"

    def test_odi_default_is_male(self):
        config = FormatConfig.odi()
        assert config.gender == "male"

    def test_match_structure(self):
        config = FormatConfig.odi()
        assert config.total_overs == 50
        assert config.total_balls == 300
        assert config.balls_per_over == 6
        assert config.total_wickets == 10

    def test_male_scoring_benchmarks(self):
        config = FormatConfig.odi("male")
        assert 240 < config.par_score < 280  # ~257.7
        assert 0.45 < config.bat_first_win_rate < 0.55  # ~0.490

    def test_female_scoring_benchmarks(self):
        config = FormatConfig.odi("female")
        assert 210 < config.par_score < 250  # ~227.8
        assert 0.45 < config.bat_first_win_rate < 0.55  # ~0.508

    def test_male_par_higher_than_female(self):
        male = FormatConfig.odi("male")
        female = FormatConfig.odi("female")
        assert male.par_score > female.par_score

    def test_phase_structure(self):
        config = FormatConfig.odi()
        assert config.phase_names == ["powerplay", "middle", "setup", "death"]
        assert config.phase_thresholds == {
            "powerplay": 10,
            "middle": 34,
            "setup": 40,
            "death": 50,
        }

    def test_expected_run_rates_ordered(self):
        """Death overs should have highest RR, powerplay lowest."""
        config = FormatConfig.odi()
        rr = config.expected_run_rates
        assert rr["death"] > rr["setup"] > rr["middle"]
        assert rr["powerplay"] < rr["death"]

    def test_dls_table_completeness(self):
        config = FormatConfig.odi()
        assert len(config.dls_resource_table) == 10  # wickets 0-9
        for wickets in range(10):
            assert wickets in config.dls_resource_table
            row = config.dls_resource_table[wickets]
            assert 0 in row  # 0 overs remaining = 0%
            assert 50 in row  # 50 overs remaining

    def test_dls_table_monotonic(self):
        """More overs remaining should mean more resources (for 0 wickets)."""
        config = FormatConfig.odi()
        row0 = config.dls_resource_table[0]
        assert row0[0] == 0.0
        assert row0[50] == 100.0
        assert row0[25] > row0[10]

    def test_penalty_3d_phases(self):
        config = FormatConfig.odi()
        p3d = config.first_innings_wicket_penalty_3d
        assert set(p3d.keys()) == {"powerplay", "middle", "setup", "death"}
        for phase in p3d:
            assert "par" in p3d[phase]
            assert p3d[phase]["par"][0] == 1.0
            assert p3d[phase]["par"][10] == 0.01

    def test_chase_penalty_ease_levels(self):
        config = FormatConfig.odi()
        c2d = config.chase_wicket_penalty_2d
        expected = {"very_easy", "easy", "comfortable", "tough", "desperate"}
        assert set(c2d.keys()) == expected
        for ease in c2d:
            assert c2d[ease][0] == 1.0
            assert c2d[ease][10] == 0.0

    def test_chase_params_reasonable(self):
        """ODI RRR midpoint should be lower than T20 (~9.5)."""
        odi = FormatConfig.odi()
        t20 = FormatConfig.t20()
        assert odi.rrr_midpoint < t20.rrr_midpoint

    def test_score_caps(self):
        config = FormatConfig.odi()
        assert config.score_cap_min < config.par_score < config.score_cap_max

    def test_frozen(self):
        config = FormatConfig.odi()
        with pytest.raises(AttributeError):
            config.par_score = 999.0


# ═══════════════════════════════════════════════════════════════════════════
# from_league() tests
# ═══════════════════════════════════════════════════════════════════════════


class TestFromLeague:
    """Test league resolution to FormatConfig."""

    def test_odi_league(self):
        config = FormatConfig.from_league("odi")
        assert config.format_name == "odi"
        assert config.total_overs == 50

    def test_odi_female_league(self):
        config = FormatConfig.from_league("odi_female")
        assert config.gender == "female"

    def test_t20_leagues_unchanged(self):
        for league in ["bbl", "sa20", "ilt20", "wpl", "ssm"]:
            config = FormatConfig.from_league(league)
            assert config.format_name == "t20"
            assert config.total_overs == 20


# ═══════════════════════════════════════════════════════════════════════════
# Calculator integration tests
# ═══════════════════════════════════════════════════════════════════════════


class TestODICalculator:
    """Test ResourceFeatureCalculator with ODI config."""

    @pytest.fixture
    def calc(self):
        return ResourceFeatureCalculator(config=FormatConfig.odi("male"))

    def test_instantiation(self, calc):
        assert calc.TOTAL_OVERS == 50
        assert calc.TOTAL_BALLS == 300

    def test_phase_mapping_powerplay(self, calc):
        assert calc.get_first_innings_phase(1) == "powerplay"
        assert calc.get_first_innings_phase(5) == "powerplay"
        assert calc.get_first_innings_phase(9) == "powerplay"

    def test_phase_mapping_middle(self, calc):
        assert calc.get_first_innings_phase(10) == "middle"
        assert calc.get_first_innings_phase(20) == "middle"
        assert calc.get_first_innings_phase(33) == "middle"

    def test_phase_mapping_setup(self, calc):
        assert calc.get_first_innings_phase(34) == "setup"
        assert calc.get_first_innings_phase(38) == "setup"
        assert calc.get_first_innings_phase(39) == "setup"

    def test_phase_mapping_death(self, calc):
        assert calc.get_first_innings_phase(40) == "death"
        assert calc.get_first_innings_phase(45) == "death"
        assert calc.get_first_innings_phase(50) == "death"

    def test_first_innings_wp_range(self, calc):
        """First innings WP should be in [0.001, 0.999]."""
        wp = calc.calculate_resource_win_probability(
            innings=1,
            expected_final_score=250.0,
            target_runs=0,
            resource_pct=60.0,
            current_run_rate=5.0,
            required_run_rate=0,
            current_score=100,
            balls_remaining=180,
            wickets_lost=2,
        )
        assert 0.001 <= wp <= 0.999

    def test_second_innings_easy_chase(self, calc):
        """Chasing well within reach should give high WP."""
        wp = calc.calculate_resource_win_probability(
            innings=2,
            expected_final_score=200.0,
            target_runs=200,
            resource_pct=60.0,
            current_run_rate=5.0,
            required_run_rate=3.0,
            current_score=140,
            balls_remaining=120,
            wickets_lost=1,
        )
        assert wp > 0.5

    def test_second_innings_desperate_chase(self, calc):
        """Chasing a very high RRR should give low WP."""
        wp = calc.calculate_resource_win_probability(
            innings=2,
            expected_final_score=350.0,
            target_runs=350,
            resource_pct=20.0,
            current_run_rate=4.0,
            required_run_rate=12.0,
            current_score=200,
            balls_remaining=60,
            wickets_lost=5,
        )
        assert wp < 0.3

    def test_higher_wickets_lower_wp(self, calc):
        """More wickets fallen should reduce win probability."""
        wp_2w = calc.calculate_resource_win_probability(
            innings=2,
            expected_final_score=260.0,
            target_runs=260,
            resource_pct=40.0,
            current_run_rate=5.0,
            required_run_rate=5.5,
            current_score=150,
            balls_remaining=120,
            wickets_lost=2,
        )
        wp_7w = calc.calculate_resource_win_probability(
            innings=2,
            expected_final_score=260.0,
            target_runs=260,
            resource_pct=40.0,
            current_run_rate=5.0,
            required_run_rate=5.5,
            current_score=150,
            balls_remaining=120,
            wickets_lost=7,
        )
        assert wp_2w > wp_7w

    def test_t20_regression_still_passes(self):
        """Ensure T20 calculator is unaffected by ODI additions."""
        calc = ResourceFeatureCalculator(config=FormatConfig.t20())
        assert calc.TOTAL_OVERS == 20
        wp = calc.calculate_resource_win_probability(
            innings=1,
            expected_final_score=160.0,
            target_runs=0,
            resource_pct=50.0,
            current_run_rate=8.0,
            required_run_rate=0,
            current_score=80,
            balls_remaining=60,
            wickets_lost=2,
        )
        assert 0.001 <= wp <= 0.999
