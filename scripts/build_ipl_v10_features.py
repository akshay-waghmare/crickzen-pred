"""
Build ipl_features_v10: v9 features + inn2 momentum engineering.

Inn2 rows receive the full set of engineered momentum features.
Inn1 rows receive zero-valued placeholders — XGBoost learns the inn1/inn2
boundary automatically via the innings / phase flags already in TOP_FEATURES.

New features added (ordered by XGB gain observed in phase-model research):
  momentum_under_pressure   — crr/dls_pressure: scoring despite pressure (best death feature)
  net_momentum              — scoring_rate_gap × wicket_cost (high inn2 correlation 0.47)
  batting_pair_momentum     — batting_pair_strength × crr_vs_rrr (consistent all phases)
  wicket_adj_momentum       — momentum_vs_rrr × wicket_cost (death phase signal)
  recovery_momentum         — partnership length × excess scoring rate
  recent_surge_flag         — 1 if last-2-over pace ≥ required rate
  momentum_acceleration     — (r12×1.5 − r18): is last over better than previous?
  chase_category            — ordinal −1/0/+1 for low/par/high chase
  inn1_quality_index        — composite inn1 performance index

Usage:
  python scripts/build_ipl_v10_features.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np

from scripts.inn2_feature_engineering import engineer_inn2_features

# Features to carry from inn2 engineering into the v10 dataset
V10_NEW_FEATURES = [
    "momentum_under_pressure",
    "net_momentum",
    "batting_pair_momentum",
    "wicket_adj_momentum",
    "recovery_momentum",
    "recent_surge_flag",
    "momentum_acceleration",
    "chase_category",
    "inn1_quality_index",
]

INPUT_PATH  = "data/ipl_features_v9/training.parquet"
OUTPUT_DIR  = "data/ipl_features_v10"
OUTPUT_PATH = f"{OUTPUT_DIR}/training.parquet"


def build_v10(input_path: str = INPUT_PATH, output_path: str = OUTPUT_PATH) -> pd.DataFrame:
    print(f"Loading {input_path} ...")
    df = pd.read_parquet(input_path)
    print(f"  {len(df):,} rows  ×  {len(df.columns)} cols")

    inn1 = df[df.innings == 1].copy()
    inn2 = df[df.innings == 2].copy()
    print(f"  Inn1: {len(inn1):,}  Inn2: {len(inn2):,}")

    # ── Engineer inn2 features ────────────────────────────────────────────────
    print("Engineering inn2 momentum features ...")
    inn2_eng = engineer_inn2_features(inn2)

    # ── Zero-fill for inn1 (trees learn the boundary via innings/phase flags) ─
    for feat in V10_NEW_FEATURES:
        if feat not in inn1.columns:
            inn1[feat] = 0.0
        if feat in inn2_eng.columns:
            inn2[feat] = inn2_eng[feat].values
        else:
            inn2[feat] = 0.0

    # ── Recombine and sort ────────────────────────────────────────────────────
    combined = pd.concat([inn1, inn2], ignore_index=True)
    combined = combined.sort_values(["match_id", "innings", "over", "ball"]).reset_index(drop=True)

    # Quick sanity check
    print("\nNew feature stats (inn2 rows):")
    for feat in V10_NEW_FEATURES:
        s = combined.loc[combined.innings == 2, feat]
        print(f"  {feat:35s}: mean={s.mean():.3f}  std={s.std():.3f}  nulls={s.isnull().sum()}")

    # ── Save ──────────────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    combined.to_parquet(output_path, index=False)
    print(f"\nSaved → {output_path}")
    print(f"  {len(combined):,} rows  ×  {len(combined.columns)} cols")
    return combined


if __name__ == "__main__":
    build_v10()
