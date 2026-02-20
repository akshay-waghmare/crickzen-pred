"""
Analyze BBL calibration performance by innings and phase.

Shows which calibration strategy performs best for each specific game situation.
"""

import pandas as pd
import numpy as np
from pathlib import Path


def load_and_prepare_data():
    """Load the detailed OOF results."""
    results_file = Path("data/bbl_calibration_analysis/oof_detailed_results.csv")
    df = pd.read_csv(results_file)
    return df


def find_best_calibrator_by_situation(df: pd.DataFrame, metric: str = 'log_loss'):
    """
    Find the best calibration strategy for each innings × phase combination.
    
    Args:
        df: DataFrame with detailed results
        metric: 'log_loss', 'brier', or 'ece'
    """
    
    # Situations to analyze
    situations = {
        'Overall': metric,
        'Innings 1': f'{metric}_inn1',
        'Innings 2': f'{metric}_inn2',
        'Powerplay': f'{metric}_pp',
        'Middle Overs': f'{metric}_mid',
        'Death Overs': f'{metric}_death',
        'Inn1 - Powerplay': f'll_inn1_pp' if metric == 'log_loss' else f'{metric}_inn1_pp',
        'Inn1 - Middle': f'll_inn1_mid' if metric == 'log_loss' else f'{metric}_inn1_mid',
        'Inn1 - Death': f'll_inn1_death' if metric == 'log_loss' else f'{metric}_inn1_death',
        'Inn2 - Powerplay': f'll_inn2_pp' if metric == 'log_loss' else f'{metric}_inn2_pp',
        'Inn2 - Middle': f'll_inn2_mid' if metric == 'log_loss' else f'{metric}_inn2_mid',
        'Inn2 - Death': f'll_inn2_death' if metric == 'log_loss' else f'{metric}_inn2_death',
    }
    
    results = []
    
    for situation_name, metric_col in situations.items():
        if metric_col not in df.columns:
            continue
            
        # Calculate mean for each strategy
        strategy_means = df.groupby('strategy')[metric_col].mean().sort_values()
        
        best_strategy = strategy_means.index[0]
        best_value = strategy_means.iloc[0]
        raw_value = strategy_means.get('raw', np.nan)
        
        improvement = ((raw_value - best_value) / raw_value * 100) if not np.isnan(raw_value) else np.nan
        
        # Get top 3
        top3 = strategy_means.head(3)
        
        results.append({
            'Situation': situation_name,
            'Best Strategy': best_strategy,
            f'Best {metric.upper()}': f'{best_value:.4f}',
            f'Raw {metric.upper()}': f'{raw_value:.4f}' if not np.isnan(raw_value) else 'N/A',
            'Improvement %': f'{improvement:.2f}%' if not np.isnan(improvement) else 'N/A',
            '2nd Best': top3.index[1] if len(top3) > 1 else 'N/A',
            '3rd Best': top3.index[2] if len(top3) > 2 else 'N/A'
        })
    
    return pd.DataFrame(results)


def create_heatmap_data(df: pd.DataFrame, metric: str = 'log_loss'):
    """Create a heatmap showing performance of each strategy by situation."""
    
    situations = {
        'Overall': metric,
        'Inn1': f'{metric}_inn1',
        'Inn2': f'{metric}_inn2',
        'PP': f'{metric}_pp',
        'Mid': f'{metric}_mid',
        'Death': f'{metric}_death',
        'Inn1-PP': f'll_inn1_pp' if metric == 'log_loss' else f'{metric}_inn1_pp',
        'Inn1-Mid': f'll_inn1_mid' if metric == 'log_loss' else f'{metric}_inn1_mid',
        'Inn1-Death': f'll_inn1_death' if metric == 'log_loss' else f'{metric}_inn1_death',
        'Inn2-PP': f'll_inn2_pp' if metric == 'log_loss' else f'{metric}_inn2_pp',
        'Inn2-Mid': f'll_inn2_mid' if metric == 'log_loss' else f'{metric}_inn2_mid',
        'Inn2-Death': f'll_inn2_death' if metric == 'log_loss' else f'{metric}_inn2_death',
    }
    
    # Calculate mean for each strategy × situation
    heatmap_data = {}
    
    for situation_name, metric_col in situations.items():
        if metric_col not in df.columns:
            continue
        
        strategy_means = df.groupby('strategy')[metric_col].mean()
        heatmap_data[situation_name] = strategy_means
    
    heatmap_df = pd.DataFrame(heatmap_data).round(4)
    
    return heatmap_df


def print_detailed_comparison(df: pd.DataFrame):
    """Print detailed comparison of all strategies."""
    
    print("\n" + "="*100)
    print("DETAILED PERFORMANCE COMPARISON BY INNINGS AND PHASE")
    print("="*100)
    
    # Group by situation
    innings_phases = [
        ('Innings 1 - Powerplay', 'll_inn1_pp', 'brier_inn1_pp', 'ece_inn1_pp', 'n_inn1_pp'),
        ('Innings 1 - Middle', 'll_inn1_mid', 'brier_inn1_mid', 'ece_inn1_mid', 'n_inn1_mid'),
        ('Innings 1 - Death', 'll_inn1_death', 'brier_inn1_death', 'ece_inn1_death', 'n_inn1_death'),
        ('Innings 2 - Powerplay', 'll_inn2_pp', 'brier_inn2_pp', 'ece_inn2_pp', 'n_inn2_pp'),
        ('Innings 2 - Middle', 'll_inn2_mid', 'brier_inn2_mid', 'ece_inn2_mid', 'n_inn2_mid'),
        ('Innings 2 - Death', 'll_inn2_death', 'brier_inn2_death', 'ece_inn2_death', 'n_inn2_death'),
    ]
    
    for situation_name, ll_col, brier_col, ece_col, n_col in innings_phases:
        if ll_col not in df.columns:
            continue
            
        print(f"\n{'='*100}")
        print(f"{situation_name.upper()}")
        print(f"{'='*100}")
        
        # Calculate stats for each strategy
        stats = df.groupby('strategy').agg({
            ll_col: ['mean', 'std'],
            brier_col: ['mean', 'std'],
            ece_col: ['mean', 'std'],
            n_col: 'mean'
        }).round(4)
        
        # Flatten column names
        stats.columns = ['LL_mean', 'LL_std', 'Brier_mean', 'Brier_std', 'ECE_mean', 'ECE_std', 'N_samples']
        stats = stats.sort_values('LL_mean')
        
        print(f"\nSample size: ~{stats['N_samples'].iloc[0]:.0f} balls per fold")
        print(f"\n{stats.to_string()}")
        
        # Show best strategy
        best = stats.index[0]
        raw_ll = stats.loc['raw', 'LL_mean'] if 'raw' in stats.index else np.nan
        best_ll = stats.loc[best, 'LL_mean']
        improvement = ((raw_ll - best_ll) / raw_ll * 100) if not np.isnan(raw_ll) else 0
        
        print(f"\n🏆 BEST: {best}")
        print(f"   Log Loss: {best_ll:.4f} ± {stats.loc[best, 'LL_std']:.4f}")
        print(f"   Improvement over raw: {improvement:.2f}%")


def main():
    print("Loading BBL OOF calibration results...")
    df = load_and_prepare_data()
    
    print(f"Loaded {len(df)} results from {df['fold'].nunique()} folds")
    print(f"Strategies: {sorted(df['strategy'].unique())}")
    
    # Log Loss Analysis
    print("\n" + "="*100)
    print("LOG LOSS: BEST CALIBRATOR BY SITUATION")
    print("="*100)
    
    ll_results = find_best_calibrator_by_situation(df, 'log_loss')
    print("\n" + ll_results.to_string(index=False))
    
    # Save
    output_dir = Path("data/bbl_calibration_analysis")
    ll_results.to_csv(output_dir / "best_calibrator_by_situation_logloss.csv", index=False)
    
    # Brier Analysis
    print("\n\n" + "="*100)
    print("BRIER SCORE: BEST CALIBRATOR BY SITUATION")
    print("="*100)
    
    brier_results = find_best_calibrator_by_situation(df, 'brier')
    print("\n" + brier_results.to_string(index=False))
    brier_results.to_csv(output_dir / "best_calibrator_by_situation_brier.csv", index=False)
    
    # ECE Analysis
    print("\n\n" + "="*100)
    print("ECE: BEST CALIBRATOR BY SITUATION")
    print("="*100)
    
    ece_results = find_best_calibrator_by_situation(df, 'ece')
    print("\n" + ece_results.to_string(index=False))
    ece_results.to_csv(output_dir / "best_calibrator_by_situation_ece.csv", index=False)
    
    # Create heatmaps
    print("\n\n" + "="*100)
    print("HEATMAP: LOG LOSS BY STRATEGY × SITUATION")
    print("="*100)
    
    ll_heatmap = create_heatmap_data(df, 'log_loss')
    print("\n" + ll_heatmap.to_string())
    ll_heatmap.to_csv(output_dir / "logloss_heatmap.csv")
    
    # Detailed comparison
    print_detailed_comparison(df)
    
    # Summary recommendations
    print("\n\n" + "="*100)
    print("CALIBRATION RECOMMENDATIONS")
    print("="*100)
    
    print("\nBased on Log Loss performance:")
    for _, row in ll_results.iterrows():
        if 'Inn' in row['Situation']:
            print(f"  {row['Situation']:<25} → {row['Best Strategy']:<25} (LL: {row['Best LOG_LOSS']})")
    
    print("\nKey Insights:")
    overall_best = ll_results[ll_results['Situation'] == 'Overall']['Best Strategy'].iloc[0]
    print(f"  • Overall best: {overall_best}")
    
    inn1_strategies = ll_results[ll_results['Situation'].str.contains('Inn1', na=False)]['Best Strategy'].unique()
    inn2_strategies = ll_results[ll_results['Situation'].str.contains('Inn2', na=False)]['Best Strategy'].unique()
    
    print(f"  • Innings 1 needs: {', '.join(inn1_strategies)}")
    print(f"  • Innings 2 needs: {', '.join(inn2_strategies)}")
    
    print(f"\n✅ Results saved to {output_dir}/")


if __name__ == "__main__":
    main()
