"""
Train IPL Logit-Bias League Calibrator from Market Data

Computes logit-space bias correction per phase×innings segment using
recorded market odds vs PRODUCTION model predictions on IPL 2026 matches.

IMPORTANT: Uses the actual production model (t20_male_v2) with its full
calibration chain (per-over isotonic) to ensure biases match what the
predictor outputs before league calibration.

Usage:
    python scripts/train_ipl_logit_bias.py
    python scripts/train_ipl_logit_bias.py --model-dir models/t20_male_v2
"""
import sys, warnings, argparse
warnings.filterwarnings('ignore')
sys.path.insert(0, 'src')

import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from datetime import datetime
from scipy.special import logit, expit

from bbl_pipeline.training.league_calibrator import LogitBiasScaler


TEAM_ALIASES = {
    'Royal Challengers Bangalore': 'Royal Challengers Bengaluru',
    'Delhi Daredevils': 'Delhi Capitals',
    'Kings XI Punjab': 'Punjab Kings',
    'Rising Pune Supergiant': 'Rising Pune Supergiants',
}


def assign_phase(over):
    """Standard T20 phase assignment (1-indexed overs)."""
    if over <= 6: return 'powerplay'
    elif over <= 15: return 'middle'
    else: return 'death'


def brier(p, y):
    return np.mean((p - y) ** 2)


def main():
    parser = argparse.ArgumentParser(description='Train IPL logit-bias calibrator from market data')
    parser.add_argument('--model-dir', default='models/t20_male_v2', help='Model directory')
    parser.add_argument('--market-data', default='data/ipl_model_vs_market_v3.parquet', help='Market data file')
    parser.add_argument('--features-dir', default='data/ipl_features_v3', help='Features directory')
    parser.add_argument('--dry-run', action='store_true', help='Print biases without saving')
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    league_dir = model_dir / 'league_calibrators' / 'ipl'

    # ── Load market data ──
    print("Loading market data...")
    obs = pd.read_parquet(args.market_data)
    print(f"  Market observations: {len(obs)} from {obs['event_id'].nunique()} matches")

    # ── Load PRODUCTION model and its calibrators ──
    print(f"Loading production model from {model_dir}...")
    prod_model = joblib.load(model_dir / 'champion_model.joblib')
    # Patch sklearn 1.7→1.8 SimpleImputer compatibility
    from bbl_pipeline.inference.predictor import _restore_simple_imputer_compatibility
    _restore_simple_imputer_compatibility(prod_model)
    print(f"  Model features: {len(prod_model.selected_features_)}")

    # Load isotonic calibrators (same chain as predictor uses)
    cal_path = model_dir / 'isotonic_calibrator.pkl'
    per_over_calibrators = {}
    phase_calibrators = {}
    if cal_path.exists():
        cal_data = joblib.load(cal_path)
        per_over_calibrators = cal_data.get('per_over_calibrators', {})
        phase_calibrators = cal_data.get('phase_calibrators', {})
        print(f"  Per-over calibrators: {len(per_over_calibrators)}")
        print(f"  Phase calibrators: {len(phase_calibrators)}")

    # ── Load features + raw metadata ──
    print("Loading features...")
    raw = pd.read_parquet('data/ipl_raw/matches')
    raw = raw.drop_duplicates(subset=['match_id', 'innings', 'over', 'ball'], keep='first')
    raw = raw.sort_values(['match_id', 'innings', 'over', 'ball']).reset_index(drop=True)

    train_full = pd.read_parquet(f'{args.features_dir}/training.parquet')
    assert len(raw) == len(train_full), f"Row mismatch: {len(raw)} vs {len(train_full)}"

    train_full['season'] = raw['season'].values
    train_full['match_id'] = raw['match_id'].values
    train_full['raw_innings'] = raw['innings'].values
    train_full['raw_over'] = raw['over'].values
    train_full['raw_date'] = pd.to_datetime(raw['date']).dt.strftime('%Y-%m-%d').values
    train_full['raw_batting_team'] = raw['batting_team'].map(lambda x: TEAM_ALIASES.get(x, x)).values

    # ── Score ALL data with production model ──
    meta_cols = ['is_winner', 'season', 'match_id', 'raw_innings', 'raw_over', 'raw_date', 'raw_batting_team']
    feature_cols = [c for c in train_full.columns if c not in meta_cols]
    avail = [c for c in prod_model.selected_features_ if c in feature_cols]
    print(f"  Scoring with {len(avail)} features (of {len(prod_model.selected_features_)} selected)")

    # Get 2026 season data
    mask_2026 = train_full['season'] == '2026'
    test_2026 = train_full[mask_2026].copy()
    print(f"  2026 rows: {len(test_2026)}")

    # Score with production model → P(batting_team wins) = raw_prob
    raw_probs = prod_model.predict_proba(test_2026[feature_cols])[:, 1]
    test_2026['raw_prob'] = raw_probs

    # Apply per-over isotonic calibration (same chain as predictor lines 792-799)
    def calibrate_row(row):
        p = row['raw_prob']
        inn = int(row['raw_innings'])
        over_1based = int(row['raw_over']) + 1
        # Per-over first (same priority as predictor)
        over_key = f'inn{inn}_over{over_1based}'
        if over_key in per_over_calibrators:
            return float(per_over_calibrators[over_key].predict([p])[0])
        # Phase fallback
        if over_1based <= 6: phase = 'powerplay'
        elif over_1based <= 15: phase = 'middle'
        else: phase = 'death'
        phase_key = f'inn{inn}_{phase}'
        if phase_key in phase_calibrators:
            return float(phase_calibrators[phase_key].predict([p])[0])
        return p

    test_2026['cal_prob'] = test_2026.apply(calibrate_row, axis=1)
    print(f"  Calibrated {len(test_2026)} rows through production isotonic chain")

    # ── Aggregate to per-over and match to market ──
    test_po = test_2026.groupby(['match_id', 'raw_innings', 'raw_over']).agg(
        cal_prob=('cal_prob', 'last'),  # last ball of over = final calibrated prob
        is_winner=('is_winner', 'first'),
        date=('raw_date', 'first'),
        batting_team=('raw_batting_team', 'first'),
    ).reset_index()

    # Support both v2 (old) and v3 (corrected Cricsheet-first) market data formats
    is_v3 = 'market_p_inn1' in obs.columns

    if is_v3:
        # v3 format: match_id is Cricsheet ID, merge directly
        # over is 1-indexed, innings is 1/2
        test_po['merge_key'] = (
            test_po['match_id'].astype(str) + '_' +
            test_po['raw_innings'].astype(str) + '_' +
            (test_po['raw_over'] + 1).astype(str)
        )
        obs['merge_key'] = (
            obs['match_id'].astype(str) + '_' +
            obs['innings'].astype(str) + '_' +
            obs['over'].astype(str)
        )
        merged = obs.merge(test_po[['merge_key', 'cal_prob']], on='merge_key', how='inner')

        # Convert market_p_inn1 to P(batting_team)
        # In inn1, batting_team IS inn1_team, so market_p_bat = market_p_inn1
        # In inn2, batting_team IS inn2_team, so market_p_bat = 1 - market_p_inn1
        merged['market_p_bat'] = merged['market_p_inn1'].copy()
        merged.loc[merged['innings'] == 2, 'market_p_bat'] = (
            1.0 - merged.loc[merged['innings'] == 2, 'market_p_inn1']
        )
        merged['actual_bat_wins'] = merged['actual_inn1_wins'].copy()
        merged.loc[merged['innings'] == 2, 'actual_bat_wins'] = (
            1.0 - merged.loc[merged['innings'] == 2, 'actual_inn1_wins']
        )
    else:
        # Legacy v2 format: merge by date + batting_team + innings + over
        test_po['merge_key'] = (
            test_po['date'] + '_' + test_po['batting_team'] + '_' +
            test_po['raw_innings'].astype(str) + '_' +
            (test_po['raw_over'] + 1).astype(str)
        )
        obs['merge_key'] = (
            obs['date'] + '_' + obs['batting_team'] + '_' +
            obs['innings'].astype(str) + '_' + obs['over'].astype(str)
        )
        merged = obs.merge(test_po[['merge_key', 'cal_prob']], on='merge_key', how='inner')

        merged['bat_is_t1'] = merged['batting_team'] == merged['team1']
        merged['market_p_bat'] = merged['market_p_t1'].copy()
        merged.loc[~merged['bat_is_t1'], 'market_p_bat'] = 1.0 - merged.loc[~merged['bat_is_t1'], 'market_p_bat']
        merged['actual_bat_wins'] = merged['actual_t1_wins'].copy()
        merged.loc[~merged['bat_is_t1'], 'actual_bat_wins'] = 1.0 - merged.loc[~merged['bat_is_t1'], 'actual_bat_wins']

    merged['phase'] = merged['over'].apply(assign_phase)
    n_matched = len(merged)
    n_matches = merged['event_id'].nunique()
    print(f"  Matched: {n_matched} obs from {n_matches} matches (format={'v3' if is_v3 else 'v2'})")

    actual = merged['actual_bat_wins'].values
    market = merged['market_p_bat'].values
    model_p = merged['cal_prob'].values   # production model calibrated P(batting_team)

    # ── Compute logit biases per segment (in P(batting_team) space) ──
    print(f"\n{'='*70}")
    print(f"  LOGIT-SPACE BIAS CORRECTION (P(batting_team) space)")
    print(f"  Using PRODUCTION model {model_dir} + isotonic calibration")
    print(f"{'='*70}")

    calibrators = {}
    segment_metrics = {}

    for inn in [1, 2]:
        for phase in ['powerplay', 'middle', 'death']:
            key = f'inn{inn}_{phase}'
            mask = (merged['innings'] == inn) & (merged['phase'] == phase)
            if mask.sum() < 5:
                print(f"  {key}: SKIP (only {mask.sum()} obs)")
                continue

            seg_model = model_p[mask.values]
            seg_market = market[mask.values]
            seg_actual = actual[mask.values]

            scaler = LogitBiasScaler()
            scaler.fit(seg_model, seg_market)
            calibrators[key] = scaler

            # Metrics (Brier is space-invariant: (p-y)^2 == ((1-p)-(1-y))^2)
            cal_probs = scaler.predict(seg_model)
            b_before = brier(seg_model, seg_actual)
            b_after = brier(cal_probs, seg_actual)
            b_market = brier(seg_market, seg_actual)

            segment_metrics[key] = {
                'n_obs': int(mask.sum()),
                'logit_bias': float(scaler.bias),
                'brier_before': float(b_before),
                'brier_after': float(b_after),
                'brier_market': float(b_market),
            }

            direction = "SHIFT UP" if scaler.bias > 0 else "SHIFT DOWN"
            avg_model = seg_model.mean()
            avg_market = seg_market.mean()
            print(f"  {key:20s} n={mask.sum():3d}  bias={scaler.bias:+.4f} ({direction})")
            print(f"    {'':20s} raw={b_before:.4f}  cal={b_after:.4f}  mkt={b_market:.4f}")
            print(f"    {'':20s} avg_model={avg_model:.3f}  avg_market={avg_market:.3f}")

    # Also add innings-level calibrators as fallback
    for inn in [1, 2]:
        key = f'innings_{inn}'
        mask = (merged['innings'] == inn)
        seg_model = model_p[mask.values]
        seg_market = market[mask.values]
        scaler = LogitBiasScaler()
        scaler.fit(seg_model, seg_market)
        calibrators[key] = scaler
        print(f"\n  {key:20s} n={mask.sum():3d}  bias={scaler.bias:+.4f} (fallback)")

    # Overall metrics
    all_cal = np.copy(model_p)
    for inn in [1, 2]:
        for phase in ['powerplay', 'middle', 'death']:
            key = f'inn{inn}_{phase}'
            mask = (merged['innings'] == inn).values & (merged['phase'] == phase).values
            if key in calibrators:
                all_cal[mask] = calibrators[key].predict(model_p[mask])

    b_raw = brier(model_p, actual)
    b_cal = brier(all_cal, actual)
    b_mkt = brier(market, actual)
    gap_closed = (1 - (b_cal - b_mkt) / (b_raw - b_mkt)) * 100

    print(f"\n  OVERALL:")
    print(f"    Market:     {b_mkt:.4f}")
    print(f"    Raw model:  {b_raw:.4f}  (+{(b_raw/b_mkt-1)*100:.1f}%)")
    print(f"    + LogitBias:{b_cal:.4f}  (+{(b_cal/b_mkt-1)*100:.1f}%)  Gap closed: {gap_closed:.1f}%")

    if args.dry_run:
        print("\n  [DRY RUN] Not saving. Remove --dry-run to save.")
        return

    # ── Save calibrator ──
    league_dir.mkdir(parents=True, exist_ok=True)

    # Back up existing calibrator
    old_cal_path = league_dir / 'league_calibrator.pkl'
    if old_cal_path.exists():
        backup_path = league_dir / f'league_calibrator_platt_backup_{datetime.now().strftime("%Y%m%d")}.pkl'
        if not backup_path.exists():
            import shutil
            shutil.copy2(old_cal_path, backup_path)
            print(f"\n  Backed up old calibrator to {backup_path}")

    cal_dict = {
        'method': 'logit_bias',
        'league': 'ipl',
        'innings_specific': True,
        'phase_specific': True,
        'calibrators': calibrators,
        'fitted': True,
        'trained_on': 'market_odds',
        'created_date': datetime.now().isoformat(),
        'segment_metrics': segment_metrics,
        'training_obs': n_matched,
        'training_matches': n_matches,
        'overall_metrics': {
            'brier_raw': float(b_raw),
            'brier_calibrated': float(b_cal),
            'brier_market': float(b_mkt),
            'gap_closed_pct': float(gap_closed),
        },
    }

    joblib.dump(cal_dict, league_dir / 'league_calibrator.pkl')
    print(f"\n  Saved logit-bias calibrator to {league_dir / 'league_calibrator.pkl'}")
    print(f"  Segments: {list(calibrators.keys())}")
    print("\nDone.")


if __name__ == '__main__':
    main()
