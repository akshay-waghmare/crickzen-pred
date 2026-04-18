"""Regenerate IPL team_ratings.parquet with recency weighting and deduplication.

Reads the existing team_ratings, merges duplicate franchise names using
config/entity_registry.yaml, and applies exponential decay so recent
seasons count more than distant ones.
"""

import math
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = PROJECT_ROOT / "data" / "ipl_feature_store_v2" / "team_ratings.parquet"
REGISTRY_PATH = PROJECT_ROOT / "config" / "entity_registry.yaml"
OUTPUT_PATH = INPUT_PATH  # overwrite in place

HALF_LIFE_SEASONS = 2.5
LAMBDA = math.log(2) / HALF_LIFE_SEASONS  # ≈ 0.277
MATCHES_PER_SEASON = 14  # typical IPL matches per team per season

# Newer alias is listed second in each pair; older alias is listed first.
# The "newer" alias represents the current branding.
NEWER_ALIASES: set[str] = {
    "Royal Challengers Bengaluru",
    "Delhi Capitals",
    "Punjab Kings",
    "Rising Pune Supergiants",
}


def load_registry(path: Path) -> dict[str, str]:
    """Build alias → canonical name mapping from entity_registry.yaml.

    Canonical name = first full-name alias (length > 4 to skip abbreviations).
    """
    with open(path, encoding="utf-8") as f:
        registry = yaml.safe_load(f)

    alias_to_canonical: dict[str, str] = {}
    for _code, aliases in registry.get("teams", {}).items():
        # First full-name alias is canonical
        canonical = next((a for a in aliases if len(a) > 4), aliases[0])
        for alias in aliases:
            alias_to_canonical[alias] = canonical
    return alias_to_canonical


def estimate_age(row_team: str, group_df: pd.DataFrame) -> float:
    """Estimate how many seasons ago this entry's matches were played.

    Newer aliases → age 0.  Older aliases → age ≈ (newer_matches / 14),
    representing the seasons that have passed since the rename.
    """
    if len(group_df) == 1:
        return 0.0

    newer_rows = group_df[group_df["_original_team"].isin(NEWER_ALIASES)]
    if newer_rows.empty:
        return 0.0

    if row_team in NEWER_ALIASES:
        return 0.0

    # Older alias: age = number of seasons the newer name has existed
    newer_matches = newer_rows["matches"].sum()
    return max(newer_matches / MATCHES_PER_SEASON, 1.0)


def merge_group(canonical: str, group: pd.DataFrame) -> dict:
    """Merge rows that share a canonical name, applying recency weights."""
    if len(group) == 1:
        row = group.iloc[0]
        return {
            "team": canonical,
            "win_rate": row["win_rate"],
            "matches": int(row["matches"]),
            "effective_matches": float(row["matches"]),
            "bat_first_wr": row["bat_first_wr"],
            "bowl_first_wr": row["bowl_first_wr"],
            "half_life_seasons": HALF_LIFE_SEASONS,
            "last_updated": date.today().isoformat(),
        }

    weights = []
    for _, row in group.iterrows():
        age = estimate_age(row["_original_team"], group)
        w = math.exp(-LAMBDA * age)
        weights.append(w)

    group = group.copy()
    group["_weight"] = weights

    # Weighted merge: win_rate = Σ(wins_i * w_i) / Σ(matches_i * w_i)
    total_weighted_matches = (group["matches"] * group["_weight"]).sum()
    weighted_wr = (
        (group["win_rate"] * group["matches"] * group["_weight"]).sum()
        / total_weighted_matches
    )
    weighted_bat = (
        (group["bat_first_wr"] * group["matches"] * group["_weight"]).sum()
        / total_weighted_matches
    )
    weighted_bowl = (
        (group["bowl_first_wr"] * group["matches"] * group["_weight"]).sum()
        / total_weighted_matches
    )

    return {
        "team": canonical,
        "win_rate": weighted_wr,
        "matches": int(group["matches"].sum()),
        "effective_matches": total_weighted_matches,
        "bat_first_wr": weighted_bat,
        "bowl_first_wr": weighted_bowl,
        "half_life_seasons": HALF_LIFE_SEASONS,
        "last_updated": date.today().isoformat(),
    }


def main() -> None:
    if not INPUT_PATH.exists():
        print(f"ERROR: {INPUT_PATH} not found", file=sys.stderr)
        sys.exit(1)
    if not REGISTRY_PATH.exists():
        print(f"ERROR: {REGISTRY_PATH} not found", file=sys.stderr)
        sys.exit(1)

    df = pd.read_parquet(INPUT_PATH)
    print(f"Loaded {len(df)} rows from {INPUT_PATH}")

    alias_map = load_registry(REGISTRY_PATH)
    print(f"Registry: {len(alias_map)} aliases loaded")

    # Keep original name for age estimation, then map to canonical
    df["_original_team"] = df["team"]
    df["team"] = df["team"].map(lambda t: alias_map.get(t, t))

    duplicates = df.groupby("team").filter(lambda g: len(g) > 1)["team"].unique()
    print(f"Duplicate franchises to merge: {list(duplicates)}")

    merged_rows = []
    for canonical, group in df.groupby("team"):
        merged_rows.append(merge_group(canonical, group))

    result = pd.DataFrame(merged_rows)

    # Enforce types
    result["matches"] = result["matches"].astype(int)
    result["effective_matches"] = result["effective_matches"].astype(float)
    result["half_life_seasons"] = result["half_life_seasons"].astype(float)

    result = result.sort_values("win_rate", ascending=False).reset_index(drop=True)
    result.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nWrote {len(result)} teams to {OUTPUT_PATH}\n")

    # Validation
    assert result["team"].nunique() == len(result), "Duplicate team names found!"
    assert (result["win_rate"] > 0).all() and (result["win_rate"] < 1).all(), (
        "win_rate out of range"
    )
    assert (result["effective_matches"] > 0).all(), "effective_matches <= 0"

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 160)
    pd.set_option("display.float_format", "{:.4f}".format)
    print(result.to_string(index=False))
    print(f"\n✓ {len(result)} unique teams, all validations passed")


if __name__ == "__main__":
    main()
