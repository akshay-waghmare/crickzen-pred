from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = [
    'league', 'match_id', 'innings', 'over', 'ball', 'phase',
    'ml_prob', 'resource_win_prob',
    'ml_delta_12', 'momentum_baseline_12', 'residual_delta_12',
    'ml_prob_delta_6', 'ml_prob_delta_12', 'ml_rwp_gap', 'ml_rwp_gap_delta_6',
    'direction', 'momentum_direction', 'residual_direction',
]


def validate_dataset(path: Path) -> None:
    df = pd.read_parquet(path)
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f'{path}: missing required columns {missing}')
    if df[REQUIRED_COLUMNS].isna().any().any():
        null_counts = df[REQUIRED_COLUMNS].isna().sum()
        null_counts = null_counts[null_counts > 0].to_dict()
        raise ValueError(f'{path}: unexpected nulls in ODM dataset {null_counts}')
    if df.duplicated(['league', 'match_id', 'innings', 'over', 'ball']).any():
        raise ValueError(f'{path}: duplicate key rows found')
    if not set(df['phase'].unique()).issubset({'powerplay', 'middle', 'death'}):
        raise ValueError(f'{path}: unexpected phase labels {sorted(df["phase"].dropna().unique())}')

    print(f'PASS {path}')
    print(f'  rows={len(df):,} matches={df["match_id"].nunique():,}')
    print(f'  momentum_dir_acc={(df["direction"] == df["momentum_direction"]).mean():.4f}')
    print(f'  zero_delta_mae={df["ml_delta_12"].abs().mean():.4f}')
    print(f'  momentum_mae={(df["ml_delta_12"] - df["momentum_baseline_12"]).abs().mean():.4f}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Validate ODM training dataset parquet')
    parser.add_argument('path', help='ODM training dataset parquet')
    args = parser.parse_args()
    validate_dataset(Path(args.path))


if __name__ == '__main__':
    main()
