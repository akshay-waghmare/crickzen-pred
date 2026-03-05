"""
Analyze divergence between ML model probabilities and market probabilities on recorded match states.

Compares model_final_prob vs market_batting_team_prob across multiple dimensions:
- Overall metrics (MAE, RMSE, correlation)
- By innings and phase
- By match situation (close game vs blowout)
- Identifies specific high-divergence scenarios
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
from typing import Dict, Tuple


COUNTRY_CODE_MAP = {
    "AUSTRALIA": "AUS",
    "INDIA": "IND",
    "ENGLAND": "ENG",
    "NEWZEALAND": "NZ",
    "SOUTHAFRICA": "SA",
    "PAKISTAN": "PAK",
    "WESTINDIES": "WI",
    "SRILANKA": "SL",
    "BANGLADESH": "BAN",
    "AFGHANISTAN": "AFG",
    "ZIMBABWE": "ZIM",
    "IRELAND": "IRE",
    "SCOTLAND": "SCO",
    "NETHERLANDS": "NED",
    "NAMIBIA": "NAM",
    "CANADA": "CAN",
    "OMAN": "OMA",
    "NEPAL": "NEP",
    "UNITEDARABEMIRATES": "UAE",
    "PAPUANEWGUINEA": "PNG",
    "HONGKONG": "HK",
    "UGANDA": "UGA",
    "UNITEDSTATESOFAMERICA": "USA",
    "ITALY": "ITA",
}


def _team_aliases(team: str) -> set:
    """Build comparable aliases for a team string (code / full name)."""
    if not team or not str(team).strip():
        return set()
    upper = str(team).upper().strip()
    compact = "".join(ch for ch in upper if ch.isalnum())
    aliases = {upper, compact}
    for country_name, code in COUNTRY_CODE_MAP.items():
        if country_name in compact or compact == code:
            aliases.add(code)
    return aliases


def _teams_match(left: str, right: str) -> bool:
    """Return True when two team strings represent the same team."""
    la = _team_aliases(left)
    ra = _team_aliases(right)
    return bool(la and ra and la & ra)


def repair_market_probs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Derive market_batting_team_prob from market_fav_prob + market_fav_team
    for rows where the original recording failed to map team names.
    
    This fixes data recorded before the alias-based _teams_match() was added.
    """
    needs_repair = (
        df['market_fav_prob'].notna()
        & df['market_fav_team'].notna()
        & df['market_batting_team_prob'].isna()
    )
    
    repaired = 0
    skipped = 0
    
    for idx in df.index[needs_repair]:
        fav_team = df.at[idx, 'market_fav_team']
        fav_prob = df.at[idx, 'market_fav_prob']
        bat_team = df.at[idx, 'batting_team']
        bowl_team = df.at[idx, 'bowling_team']
        
        if _teams_match(fav_team, bat_team):
            df.at[idx, 'market_batting_team_prob'] = fav_prob
            df.at[idx, 'market_bowling_team_prob'] = 1.0 - fav_prob
            repaired += 1
        elif _teams_match(fav_team, bowl_team):
            df.at[idx, 'market_batting_team_prob'] = 1.0 - fav_prob
            df.at[idx, 'market_bowling_team_prob'] = fav_prob
            repaired += 1
        else:
            skipped += 1
    
    if repaired > 0 or skipped > 0:
        print(f"  Market prob repair: {repaired} rows fixed, {skipped} skipped (unmatched team name)")
    
    return df


def load_recorded_matches(match_states_dir: Path, league: str) -> pd.DataFrame:
    """Load all recorded match state files for a league."""
    league_dir = match_states_dir / league
    parquet_files = list(league_dir.glob("*.parquet"))
    parquet_files = [f for f in parquet_files if f.name != "match_metadata.parquet"]
    
    if not parquet_files:
        raise ValueError(f"No match state files found in {league_dir}")
    
    print(f"\nLoading {len(parquet_files)} matches from {league}...")
    
    dfs = []
    for file in parquet_files:
        df = pd.read_parquet(file)
        df['match_file'] = file.stem
        dfs.append(df)
    
    combined = pd.concat(dfs, ignore_index=True)
    print(f"Loaded {len(combined):,} ball states from {len(parquet_files)} matches")
    
    # Repair market probs for older recordings that used exact string match
    combined = repair_market_probs(combined)
    
    return combined


def compute_divergence_metrics(df: pd.DataFrame) -> Dict[str, float]:
    """Compute divergence metrics between model and market probabilities."""
    model_prob = df['model_final_prob'].values
    market_prob = df['market_batting_team_prob'].values
    
    # Filter out NaN values
    mask = ~(np.isnan(model_prob) | np.isnan(market_prob))
    model_prob = model_prob[mask]
    market_prob = market_prob[mask]
    
    if len(model_prob) == 0:
        return {
            'mae': np.nan,
            'rmse': np.nan,
            'correlation': np.nan,
            'directional_agreement': np.nan,
            'n_samples': 0
        }
    
    # Absolute error
    abs_error = np.abs(model_prob - market_prob)
    mae = np.mean(abs_error)
    rmse = np.sqrt(np.mean(abs_error ** 2))
    
    # Correlation
    if len(np.unique(model_prob)) > 1 and len(np.unique(market_prob)) > 1:
        correlation = stats.pearsonr(model_prob, market_prob)[0]
    else:
        correlation = np.nan
    
    # Directional agreement (both favor batting team >50% or both favor bowling team <50%)
    model_favors_batting = model_prob > 0.5
    market_favors_batting = market_prob > 0.5
    directional_agreement = np.mean(model_favors_batting == market_favors_batting)
    
    return {
        'mae': mae,
        'rmse': rmse,
        'correlation': correlation,
        'directional_agreement': directional_agreement,
        'n_samples': len(model_prob)
    }


def add_phase_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Add phase labels (powerplay, middle, death)."""
    # Use existing match_phase column if available
    if 'match_phase' in df.columns:
        df['phase'] = df['match_phase'].str.lower()
    else:
        # Fallback: compute from over_number
        def get_phase(row):
            over = row['over_number']
            if over <= 6:
                return 'powerplay'
            elif over <= 16:
                return 'middle'
            else:
                return 'death'
        
        df['phase'] = df.apply(get_phase, axis=1)
    
    return df


def add_situation_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Add match situation labels based on model probability."""
    def get_situation(prob):
        if pd.isna(prob):
            return 'unknown'
        elif 0.4 <= prob <= 0.6:
            return 'close'
        elif prob > 0.8 or prob < 0.2:
            return 'dominant'
        else:
            return 'moderate'
    
    df['situation'] = df['model_final_prob'].apply(get_situation)
    return df


def analyze_by_segment(df: pd.DataFrame, segment_cols: list) -> pd.DataFrame:
    """Analyze divergence metrics by segment."""
    results = []
    
    for segment_values, group in df.groupby(segment_cols):
        metrics = compute_divergence_metrics(group)
        
        result = dict(zip(segment_cols, segment_values if isinstance(segment_values, tuple) else [segment_values]))
        result.update(metrics)
        results.append(result)
    
    return pd.DataFrame(results)


def find_high_divergence_scenarios(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """Find specific scenarios with highest model-market divergence."""
    df = df.copy()
    df['divergence'] = np.abs(df['model_final_prob'] - df['market_batting_team_prob'])
    
    # Filter out NaN divergence
    df = df[df['divergence'].notna()].copy()
    
    # Sort by divergence
    top_divergence = df.nlargest(top_n, 'divergence')
    
    # Select key columns
    display_cols = [
        'match_file', 'innings', 'over_number', 'ball_in_over', 'phase', 'situation',
        'total_runs', 'wickets', 'batting_team', 'bowling_team',
        'model_final_prob', 'market_batting_team_prob', 'divergence',
        'model_prob_delta', 'market_prob_delta'
    ]
    
    available_cols = [c for c in display_cols if c in top_divergence.columns]
    
    return top_divergence[available_cols]


def probability_bin_analysis(df: pd.DataFrame, n_bins: int = 10) -> pd.DataFrame:
    """Analyze model vs market by probability bins."""
    df = df.copy()
    df = df[df['model_final_prob'].notna() & df['market_batting_team_prob'].notna()]
    
    # Create bins based on model probability
    df['model_bin'] = pd.cut(df['model_final_prob'], bins=n_bins, labels=False)
    
    results = []
    for bin_idx in range(n_bins):
        bin_df = df[df['model_bin'] == bin_idx]
        
        if len(bin_df) == 0:
            continue
        
        bin_min = bin_df['model_final_prob'].min()
        bin_max = bin_df['model_final_prob'].max()
        
        results.append({
            'bin': f"{bin_min:.2f}-{bin_max:.2f}",
            'model_mean': bin_df['model_final_prob'].mean(),
            'market_mean': bin_df['market_batting_team_prob'].mean(),
            'divergence': np.abs(bin_df['model_final_prob'].mean() - bin_df['market_batting_team_prob'].mean()),
            'n_samples': len(bin_df)
        })
    
    return pd.DataFrame(results)


def generate_report(df: pd.DataFrame, output_dir: Path):
    """Generate comprehensive divergence analysis report."""
    print("\n" + "="*80)
    print("MODEL vs MARKET PROBABILITY DIVERGENCE ANALYSIS")
    print("="*80)
    
    # Overall metrics
    print("\n1. OVERALL METRICS")
    print("-" * 80)
    overall_metrics = compute_divergence_metrics(df)
    print(f"Total samples:              {overall_metrics['n_samples']:,}")
    print(f"Mean Absolute Error (MAE):  {overall_metrics['mae']:.4f}")
    print(f"Root Mean Squared Error:    {overall_metrics['rmse']:.4f}")
    print(f"Correlation:                {overall_metrics['correlation']:.4f}")
    print(f"Directional Agreement:      {overall_metrics['directional_agreement']:.2%}")
    
    # By innings
    print("\n2. BY INNINGS")
    print("-" * 80)
    innings_results = analyze_by_segment(df, ['innings'])
    print(innings_results.to_string(index=False))
    
    # By phase
    print("\n3. BY PHASE")
    print("-" * 80)
    phase_results = analyze_by_segment(df, ['phase'])
    phase_order = {'powerplay': 0, 'middle': 1, 'death': 2}
    phase_results['_sort'] = phase_results['phase'].map(phase_order)
    phase_results = phase_results.sort_values('_sort').drop('_sort', axis=1)
    print(phase_results.to_string(index=False))
    
    # By innings × phase
    print("\n4. BY INNINGS × PHASE")
    print("-" * 80)
    innings_phase_results = analyze_by_segment(df, ['innings', 'phase'])
    innings_phase_results['_sort_phase'] = innings_phase_results['phase'].map(phase_order)
    innings_phase_results = innings_phase_results.sort_values(['innings', '_sort_phase']).drop('_sort_phase', axis=1)
    print(innings_phase_results.to_string(index=False))
    
    # By match situation
    print("\n5. BY MATCH SITUATION")
    print("-" * 80)
    situation_results = analyze_by_segment(df, ['situation'])
    print(situation_results.to_string(index=False))
    
    # Probability bin analysis
    print("\n6. PROBABILITY BIN ANALYSIS")
    print("-" * 80)
    bin_results = probability_bin_analysis(df, n_bins=10)
    print(bin_results.to_string(index=False))
    
    # High divergence scenarios
    print("\n7. TOP 20 HIGH DIVERGENCE SCENARIOS")
    print("-" * 80)
    high_divergence = find_high_divergence_scenarios(df, top_n=20)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 200)
    print(high_divergence.to_string(index=False))
    
    # Save detailed results
    results_file = output_dir / "model_vs_market_divergence.csv"
    
    # Combine all segment analyses
    overall_df = pd.DataFrame([{'segment': 'overall', **overall_metrics}])
    innings_df = innings_results.copy()
    innings_df['segment'] = 'innings_' + innings_df['innings'].astype(str)
    phase_df = phase_results.copy()
    phase_df['segment'] = 'phase_' + phase_df['phase']
    innings_phase_df = innings_phase_results.copy()
    innings_phase_df['segment'] = 'inn' + innings_phase_df['innings'].astype(str) + '_' + innings_phase_df['phase']
    situation_df = situation_results.copy()
    situation_df['segment'] = 'situation_' + situation_df['situation']
    
    all_results = pd.concat([
        overall_df,
        innings_df[['segment', 'mae', 'rmse', 'correlation', 'directional_agreement', 'n_samples']],
        phase_df[['segment', 'mae', 'rmse', 'correlation', 'directional_agreement', 'n_samples']],
        innings_phase_df[['segment', 'mae', 'rmse', 'correlation', 'directional_agreement', 'n_samples']],
        situation_df[['segment', 'mae', 'rmse', 'correlation', 'directional_agreement', 'n_samples']]
    ], ignore_index=True)
    
    all_results.to_csv(results_file, index=False)
    print(f"\n✅ Detailed results saved to: {results_file}")
    
    # Save high divergence scenarios
    high_div_file = output_dir / "high_divergence_scenarios.csv"
    high_divergence.to_csv(high_div_file, index=False)
    print(f"✅ High divergence scenarios saved to: {high_div_file}")
    
    # Save probability bin analysis
    bin_file = output_dir / "probability_bin_comparison.csv"
    bin_results.to_csv(bin_file, index=False)
    print(f"✅ Probability bin analysis saved to: {bin_file}")


def main():
    # Configuration
    match_states_dir = Path("data/match_states")
    output_dir = Path("data")
    league = "t20i"  # Change to "odi_2026" or "t20i_female" for other formats
    
    # Load data
    df = load_recorded_matches(match_states_dir, league)
    
    # Required columns check
    required_cols = ['model_final_prob', 'market_batting_team_prob', 'innings', 'over_number']
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")
    
    # Add phase and situation labels
    df = add_phase_labels(df)
    df = add_situation_labels(df)
    
    # Generate report
    generate_report(df, output_dir)
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
