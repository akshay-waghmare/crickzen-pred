"""
Comprehensive Model Performance Analysis
Analyzes Brier scores by innings, phase, and calibration
"""
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.metrics import brier_score_loss
import joblib
import json

def expected_calibration_error(y_true, y_prob, n_bins=10):
    """Calculate Expected Calibration Error (ECE)."""
    bins = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(y_prob, bins[1:-1])
    
    ece = 0
    for i in range(n_bins):
        mask = bin_indices == i
        if mask.sum() > 0:
            bin_acc = y_true[mask].mean()
            bin_conf = y_prob[mask].mean()
            ece += mask.sum() / len(y_true) * abs(bin_acc - bin_conf)
    
    return ece

def calibration_table(y_true, y_prob, n_bins=10):
    """Generate calibration table showing predicted vs actual."""
    bins = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(y_prob, bins[1:-1])
    
    results = []
    for i in range(n_bins):
        mask = bin_indices == i
        if mask.sum() > 0:
            count = mask.sum()
            predicted = y_prob[mask].mean()
            actual = y_true[mask].mean()
            results.append({
                'bin': f"{bins[i]:.1f}-{bins[i+1]:.1f}",
                'count': count,
                'predicted_prob': predicted,
                'actual_prob': actual,
                'difference': actual - predicted
            })
    
    return pd.DataFrame(results)

def analyze_model(league_name, model_path, data_path, feature_store_path=None):
    """Analyze a single model's performance."""
    print(f"\n{'='*70}")
    print(f"{league_name.upper()} MODEL PERFORMANCE ANALYSIS")
    print(f"{'='*70}")
    
    # Load model
    model = joblib.load(model_path)
    print(f"✅ Loaded model from {model_path}")
    
    # Load data
    df = pd.read_parquet(data_path)
    print(f"📊 Loaded {len(df)} samples from {data_path}")
    
    # Prepare features
    target_col = 'is_winner'
    exclude_cols = [
        'is_winner', 'match_id', 'innings', 'over', 'ball', 'batting_team',
        'bowling_team', 'venue', 'season', 'current_score', 'wickets_lost',
        'target_runs', 'first_innings_score', 'runs_required', 'date', 'start_date'
    ]
    
    feature_cols = [col for col in df.columns if col not in exclude_cols and not col.startswith('_')]
    numeric_df = df[feature_cols].select_dtypes(include=[np.number])
    feature_cols = numeric_df.columns.tolist()
    
    X = df[feature_cols].fillna(0)
    y = df[target_col]
    
    # Get predictions
    y_prob = model.predict_proba(X)[:, 1]
    
    # Overall metrics
    overall_brier = brier_score_loss(y, y_prob)
    overall_ece = expected_calibration_error(y, y_prob)
    
    print(f"\n📈 OVERALL METRICS:")
    print(f"   Brier Score: {overall_brier:.4f}")
    print(f"   ECE:         {overall_ece:.4f}")
    print(f"   Samples:     {len(df)}")
    
    # Innings-wise analysis
    if 'innings' in df.columns:
        print(f"\n📊 INNINGS-WISE BRIER SCORES:")
        for innings in sorted(df['innings'].unique()):
            mask = df['innings'] == innings
            if mask.sum() > 0:
                innings_brier = brier_score_loss(y[mask], y_prob[mask])
                innings_ece = expected_calibration_error(y[mask], y_prob[mask])
                print(f"   Innings {innings}: Brier={innings_brier:.4f}, ECE={innings_ece:.4f}, N={mask.sum()}")
    
    # Phase-wise analysis
    if 'overs_remaining' in df.columns or 'is_powerplay' in df.columns:
        print(f"\n⚡ PHASE-WISE BRIER SCORES:")
        
        # Define phases
        if 'is_powerplay' in df.columns:
            powerplay = df['is_powerplay'] == 1
        else:
            # Assume first 6 overs
            powerplay = df['over'] <= 6 if 'over' in df.columns else pd.Series([False]*len(df))
        
        if 'is_death_overs' in df.columns:
            death = df['is_death_overs'] == 1
        else:
            # Assume last 4 overs
            death = df['over'] >= 17 if 'over' in df.columns else pd.Series([False]*len(df))
        
        middle = ~powerplay & ~death
        
        if powerplay.sum() > 0:
            pp_brier = brier_score_loss(y[powerplay], y_prob[powerplay])
            pp_ece = expected_calibration_error(y[powerplay], y_prob[powerplay])
            print(f"   Powerplay (1-6):   Brier={pp_brier:.4f}, ECE={pp_ece:.4f}, N={powerplay.sum()}")
        
        if middle.sum() > 0:
            mid_brier = brier_score_loss(y[middle], y_prob[middle])
            mid_ece = expected_calibration_error(y[middle], y_prob[middle])
            print(f"   Middle (7-16):     Brier={mid_brier:.4f}, ECE={mid_ece:.4f}, N={middle.sum()}")
        
        if death.sum() > 0:
            death_brier = brier_score_loss(y[death], y_prob[death])
            death_ece = expected_calibration_error(y[death], y_prob[death])
            print(f"   Death (17-20):     Brier={death_brier:.4f}, ECE={death_ece:.4f}, N={death.sum()}")
    
    # Calibration table
    print(f"\n🎯 CALIBRATION ANALYSIS (Predicted vs Actual):")
    calib_df = calibration_table(y, y_prob, n_bins=10)
    print(calib_df.to_string(index=False))
    
    # Save detailed results
    results = {
        'league': league_name,
        'overall': {
            'brier_score': float(overall_brier),
            'ece': float(overall_ece),
            'samples': int(len(df))
        },
        'innings': {},
        'phase': {},
        'calibration': calib_df.to_dict('records')
    }
    
    # Add innings results
    if 'innings' in df.columns:
        for innings in sorted(df['innings'].unique()):
            mask = df['innings'] == innings
            if mask.sum() > 0:
                results['innings'][f'innings_{innings}'] = {
                    'brier_score': float(brier_score_loss(y[mask], y_prob[mask])),
                    'ece': float(expected_calibration_error(y[mask], y_prob[mask])),
                    'samples': int(mask.sum())
                }
    
    # Add phase results
    if powerplay.sum() > 0:
        results['phase']['powerplay'] = {
            'brier_score': float(brier_score_loss(y[powerplay], y_prob[powerplay])),
            'ece': float(expected_calibration_error(y[powerplay], y_prob[powerplay])),
            'samples': int(powerplay.sum())
        }
    if middle.sum() > 0:
        results['phase']['middle'] = {
            'brier_score': float(brier_score_loss(y[middle], y_prob[middle])),
            'ece': float(expected_calibration_error(y[middle], y_prob[middle])),
            'samples': int(middle.sum())
        }
    if death.sum() > 0:
        results['phase']['death'] = {
            'brier_score': float(brier_score_loss(y[death], y_prob[death])),
            'ece': float(expected_calibration_error(y[death], y_prob[death])),
            'samples': int(death.sum())
        }
    
    return results

def main():
    """Analyze all league models."""
    print(f"\n{'='*70}")
    print("MULTI-LEAGUE MODEL PERFORMANCE ANALYSIS")
    print(f"{'='*70}")
    
    all_results = []
    
    # WBBL
    if Path("models/wbbl_v3/champion_model.joblib").exists():
        results = analyze_model(
            "WBBL",
            "models/wbbl_v3/champion_model.joblib",
            "data/wbbl_features_v3/training_sampled.parquet"
        )
        all_results.append(results)
    
    # NPL
    if Path("models/npl_v1/champion_model.joblib").exists():
        results = analyze_model(
            "NPL",
            "models/npl_v1/champion_model.joblib",
            "data/npl_features_v1/training_sampled.parquet"
        )
        all_results.append(results)
    
    # ILT20
    if Path("models/ilt20_v3/champion_model.joblib").exists():
        results = analyze_model(
            "ILT20",
            "models/ilt20_v3/champion_model.joblib",
            "data/ilt_features_v2/training_sampled.parquet"
        )
        all_results.append(results)
    
    # Save combined results
    output_path = Path("data/model_performance_analysis.json")
    with open(output_path, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n✅ Analysis complete! Results saved to {output_path}")
    
    # Summary comparison
    print(f"\n{'='*70}")
    print("SUMMARY COMPARISON")
    print(f"{'='*70}")
    print(f"{'League':<10} {'Brier':<10} {'ECE':<10} {'Samples':<10}")
    print("-" * 40)
    for r in all_results:
        print(f"{r['league']:<10} {r['overall']['brier_score']:<10.4f} {r['overall']['ece']:<10.4f} {r['overall']['samples']:<10}")

if __name__ == "__main__":
    main()
