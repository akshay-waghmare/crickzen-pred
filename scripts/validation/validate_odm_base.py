from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

KEY_COLUMNS = ['league', 'match_id', 'innings', 'over', 'ball']


def validate_file(path: Path) -> None:
    df = pd.read_parquet(path)
    missing = [column for column in KEY_COLUMNS + ['date', 'season'] if column not in df.columns]
    if missing:
        raise ValueError(f'{path}: missing columns {missing}')
    if df[KEY_COLUMNS].isna().any().any():
        raise ValueError(f'{path}: null key values found')
    if df.duplicated(KEY_COLUMNS).any():
        raise ValueError(f'{path}: duplicate (league, match_id, innings, over, ball) rows found')
    if not df[KEY_COLUMNS].reset_index(drop=True).equals(df.sort_values(KEY_COLUMNS)[KEY_COLUMNS].reset_index(drop=True)):
        raise ValueError(f'{path}: rows are not sorted by {KEY_COLUMNS}')
    if not (df['ball'] >= 1).all():
        raise ValueError(f'{path}: invalid ball numbers detected')
    print(f'PASS {path} rows={len(df):,} matches={df["match_id"].nunique():,}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Validate ODM base parquet files')
    parser.add_argument('paths', nargs='+', help='ODM base parquet files')
    args = parser.parse_args()
    for raw_path in args.paths:
        validate_file(Path(raw_path))


if __name__ == '__main__':
    main()
