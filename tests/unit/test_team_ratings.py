"""Tests for IPL team_ratings.parquet data quality and schema (User Story 3)."""

import pandas as pd
import pytest
import yaml
from pathlib import Path


PARQUET_PATH = Path("data/ipl_feature_store_v2/team_ratings.parquet")
REGISTRY_PATH = Path("config/entity_registry.yaml")

EXPECTED_SCHEMA = [
    "team",
    "win_rate",
    "matches",
    "effective_matches",
    "bat_first_wr",
    "bowl_first_wr",
    "half_life_seasons",
    "last_updated",
]

# Old alias names that should NOT appear after deduplication
OLD_ALIASES = [
    "Royal Challengers Bengaluru",
    "Delhi Daredevils",
    "Kings XI Punjab",
    "Rising Pune Supergiant",
]


@pytest.fixture(scope="module")
def team_ratings() -> pd.DataFrame:
    """Load the IPL team_ratings.parquet from the repo root."""
    assert PARQUET_PATH.exists(), f"Parquet file not found: {PARQUET_PATH}"
    return pd.read_parquet(PARQUET_PATH)


@pytest.fixture(scope="module")
def entity_registry() -> dict:
    """Load the entity_registry.yaml config."""
    assert REGISTRY_PATH.exists(), f"Registry not found: {REGISTRY_PATH}"
    with open(REGISTRY_PATH) as f:
        return yaml.safe_load(f)


class TestTeamRatingsSchema:
    """Verify schema of the regenerated team_ratings.parquet."""

    def test_schema_columns(self, team_ratings: pd.DataFrame):
        """All expected columns must be present."""
        assert list(team_ratings.columns) == EXPECTED_SCHEMA

    def test_no_extra_columns(self, team_ratings: pd.DataFrame):
        """No unexpected columns."""
        assert set(team_ratings.columns) == set(EXPECTED_SCHEMA)


class TestTeamRatingsNoDuplicates:
    """Verify no duplicate team names."""

    def test_no_duplicate_teams(self, team_ratings: pd.DataFrame):
        """Each team name must appear exactly once."""
        assert team_ratings["team"].is_unique, (
            f"Duplicate teams found: "
            f"{team_ratings['team'][team_ratings['team'].duplicated()].tolist()}"
        )


class TestCanonicalTeamsPresent:
    """Verify canonical IPL teams from entity_registry.yaml are present."""

    def test_rcb_canonical(self, team_ratings: pd.DataFrame):
        """Royal Challengers Bangalore (canonical for RCB) must be present."""
        assert "Royal Challengers Bangalore" in team_ratings["team"].values

    def test_dc_canonical(self, team_ratings: pd.DataFrame):
        """Delhi Capitals (canonical for DC) must be present."""
        assert "Delhi Capitals" in team_ratings["team"].values

    def test_pbks_canonical(self, team_ratings: pd.DataFrame):
        """Punjab Kings (canonical for PBKS) must be present."""
        assert "Punjab Kings" in team_ratings["team"].values

    def test_rps_canonical(self, team_ratings: pd.DataFrame):
        """Rising Pune Supergiants (canonical for RPS) must be present."""
        assert "Rising Pune Supergiants" in team_ratings["team"].values

    def test_all_registry_canonical_teams(
        self, team_ratings: pd.DataFrame, entity_registry: dict
    ):
        """The first alias (canonical name) for each IPL entry in
        entity_registry.yaml must appear in the parquet."""
        ipl_keys = ["RCB", "DC", "PBKS", "RPS"]
        teams_in_parquet = set(team_ratings["team"].values)

        for key in ipl_keys:
            aliases = entity_registry["teams"][key]
            canonical = aliases[0]  # first entry is canonical
            assert canonical in teams_in_parquet, (
                f"Canonical team '{canonical}' (key={key}) missing from parquet. "
                f"Found: {sorted(teams_in_parquet)}"
            )


class TestNoOldAliases:
    """Verify old alias names have been merged and removed."""

    @pytest.mark.parametrize("alias", OLD_ALIASES)
    def test_old_alias_not_present(self, team_ratings: pd.DataFrame, alias: str):
        """Old alias names must not remain in the parquet."""
        assert alias not in team_ratings["team"].values, (
            f"Old alias '{alias}' should have been merged into canonical name"
        )


class TestWinRateBounds:
    """Verify win_rate values are valid probabilities."""

    def test_win_rate_greater_than_zero(self, team_ratings: pd.DataFrame):
        assert (team_ratings["win_rate"] > 0.0).all(), (
            "All teams must have win_rate > 0.0"
        )

    def test_win_rate_less_than_one(self, team_ratings: pd.DataFrame):
        assert (team_ratings["win_rate"] < 1.0).all(), (
            "All teams must have win_rate < 1.0"
        )


class TestEffectiveMatches:
    """Verify effective_matches is positive for all teams."""

    def test_effective_matches_positive(self, team_ratings: pd.DataFrame):
        assert (team_ratings["effective_matches"] > 0).all(), (
            "All teams must have effective_matches > 0"
        )


class TestMinimumMatches:
    """Verify matches >= 10 for included teams."""

    def test_matches_minimum_threshold(self, team_ratings: pd.DataFrame):
        """All teams should have at least 10 matches.
        Kochi Tuskers Kerala (14 matches) is the lowest — they played only one
        IPL season (2011) before being terminated."""
        below = team_ratings[team_ratings["matches"] < 10]
        assert below.empty, (
            f"Teams with fewer than 10 matches: "
            f"{below[['team', 'matches']].to_dict('records')}"
        )


class TestTeamCount:
    """Verify team count after deduplication."""

    def test_fifteen_teams(self, team_ratings: pd.DataFrame):
        """Should have 15 unique teams after merging 4 duplicates from 19."""
        assert len(team_ratings) == 15, (
            f"Expected 15 teams, got {len(team_ratings)}: "
            f"{sorted(team_ratings['team'].tolist())}"
        )
