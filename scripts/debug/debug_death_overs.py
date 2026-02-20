#!/usr/bin/env python3
"""
Debug why the model produces wrong probabilities for death over easy chases.

Scenario: 181-5 (16.5), CRR=10.75, RR=2.84 -> Should be ~95% but model gives ~50%
"""
import pandas as pd
import numpy as np
import joblib

# Load model
model = joblib.load('models/bbl_v10/champion_model.joblib')

# Load training data
df = pd.read_parquet('data/bbl_features_v2/training.parquet')
df_inn2 = df[df['innings'] == 2].copy()

# Find easy chase scenarios in death overs (RR < CRR, should be high win prob)
easy_chase = (
    (df_inn2['required_run_rate'] < df_inn2['current_run_rate']) & 
    (df_inn2['required_run_rate'] < 6) &
    (df_inn2['current_run_rate'] > 8)
)

print("=== DEATH OVER EASY CHASE ANALYSIS ===")
print(f"Easy chase scenarios found: {easy_chase.sum()}\n")

if easy_chase.sum() > 0:
    easy_df = df_inn2[easy_chase].copy()
    
    # Get predictions
    X = easy_df.drop(['match_id', 'ball', 'innings', 'is_winner'], axis=1, errors='ignore')
    predictions = model.predict_proba(X)[:, 1]  # Get probability of class 1 (win)
    
    # Add predictions to dataframe
    easy_df['predicted_prob'] = predictions
    
    # Summary stats
    print(f"Actual win rate:      {easy_df['is_winner'].mean():.4f} ({easy_df['is_winner'].mean()*100:.1f}%)")
    print(f"Model avg prediction: {predictions.mean():.4f} ({predictions.mean()*100:.1f}%)")
    print(f"Calibration error:    {abs(predictions.mean() - easy_df['is_winner'].mean()):.4f}\n")
    
    # Distribution of predictions
    print("Prediction distribution:")
    print(f"  < 0.10: {(predictions < 0.10).sum()} ({(predictions < 0.10).sum()/len(predictions)*100:.1f}%)")
    print(f"  0.10-0.30: {((predictions >= 0.10) & (predictions < 0.30)).sum()} ({((predictions >= 0.10) & (predictions < 0.30)).sum()/len(predictions)*100:.1f}%)")
    print(f"  0.30-0.50: {((predictions >= 0.30) & (predictions < 0.50)).sum()} ({((predictions >= 0.30) & (predictions < 0.50)).sum()/len(predictions)*100:.1f}%)")
    print(f"  0.50-0.70: {((predictions >= 0.50) & (predictions < 0.70)).sum()} ({((predictions >= 0.50) & (predictions < 0.70)).sum()/len(predictions)*100:.1f}%)")
    print(f"  0.70-0.90: {((predictions >= 0.70) & (predictions < 0.90)).sum()} ({((predictions >= 0.70) & (predictions < 0.90)).sum()/len(predictions)*100:.1f}%)")
    print(f"  > 0.90: {(predictions > 0.90).sum()} ({(predictions > 0.90).sum()/len(predictions)*100:.1f}%)\n")
    
    # Check key features
    print("Key feature statistics:")
    print(f"  Required RR:  mean={easy_df['required_run_rate'].mean():.2f}, median={easy_df['required_run_rate'].median():.2f}")
    print(f"  Current RR:   mean={easy_df['current_run_rate'].mean():.2f}, median={easy_df['current_run_rate'].median():.2f}")
    print(f"  RR Diff:      mean={easy_df['run_rate_diff'].mean():.2f}, median={easy_df['run_rate_diff'].median():.2f}")
    
    if 'wickets_lost' in easy_df.columns:
        print(f"  Wickets lost: mean={easy_df['wickets_lost'].mean():.1f}, median={easy_df['wickets_lost'].median():.1f}")
    
    # Find worst predictions (high actual win rate but low prediction)
    easy_df_sorted = easy_df.sort_values('predicted_prob')
    worst_cases = easy_df_sorted.head(20)
    
    print("\n=== 20 WORST PREDICTIONS (Should be high prob but model gives low) ===")
    cols_to_show = ['required_run_rate', 'current_run_rate', 'run_rate_diff', 
                    'wickets_lost', 'is_winner', 'predicted_prob']
    cols_available = [c for c in cols_to_show if c in worst_cases.columns]
    
    for idx, row in worst_cases[cols_available].iterrows():
        print(f"RR:{row['required_run_rate']:.2f} CRR:{row['current_run_rate']:.2f} " +
              f"RRDiff:{row['run_rate_diff']:.2f} " +
              (f"Wkts:{row['wickets_lost']:.0f} " if 'wickets_lost' in cols_available else "") +
              f"-> Pred:{row['predicted_prob']:.3f} Actual:{row['is_winner']:.0f}")
    
    # Check if resource_win_prob is dominating
    if 'resource_win_prob' in easy_df.columns:
        print("\n=== RESOURCE WIN PROB CHECK ===")
        print(f"Resource win prob: mean={easy_df['resource_win_prob'].mean():.4f}, " +
              f"median={easy_df['resource_win_prob'].median():.4f}")
        
        # Correlation with predictions
        corr_resource = np.corrcoef(easy_df['resource_win_prob'], predictions)[0, 1]
        corr_rr_diff = np.corrcoef(easy_df['run_rate_diff'], predictions)[0, 1]
        
        print(f"\nCorrelation with model predictions:")
        print(f"  resource_win_prob: {corr_resource:.4f}")
        print(f"  run_rate_diff:     {corr_rr_diff:.4f}")
        
        if abs(corr_resource) > 0.7:
            print(f"\n⚠️  resource_win_prob is heavily influencing predictions (corr={corr_resource:.4f})")
            print("    This might be pulling predictions down in death overs")
    
    # Check feature importance
    print("\n=== FEATURE IMPORTANCE (Top 10) ===")
    feature_importance_file = 'models/bbl_v10/feature_importance.csv'
    try:
        feat_imp = pd.read_csv(feature_importance_file)
        print(feat_imp.head(10).to_string(index=False))
        
        # Check where RR features rank
        rr_features = ['required_run_rate', 'current_run_rate', 'run_rate_diff']
        for feat in rr_features:
            if feat in feat_imp['feature'].values:
                rank = feat_imp[feat_imp['feature'] == feat].index[0] + 1
                importance = feat_imp[feat_imp['feature'] == feat]['importance'].values[0]
                print(f"\n{feat}: Rank #{rank}, Importance: {importance:.4f}")
    except:
        print("Feature importance file not found")

print("\n=== HYPOTHESIS ===")
print("Possible issues:")
print("1. resource_win_prob feature might be poorly calibrated for death overs")
print("2. Model relies too heavily on historical stats vs situational features")
print("3. Death over feature engineering doesn't capture 'easy chase' scenarios")
print("4. Wicket penalty in resource calculation too aggressive for death overs")
