"""
Analyze BBL model confidence for high and low scoring matches (second innings).
"""
import pandas as pd
import numpy as np
from pathlib import Path
import joblib
from sklearn.metrics import brier_score_loss

def analyze_extremes(df, model, calibrators):
    results = []
    y_true = df['is_winner'].values
    raw_prob = model.predict_proba(df)[:, 1]
    # Phase calibration
    phase_probs = []
    for idx, row in df.iterrows():
        if row['is_powerplay'] == 1:
            phase_key = 'inn2_powerplay'
        elif row['is_death_overs'] == 1:
            phase_key = 'inn2_death'
        else:
            phase_key = 'inn2_middle'
        if phase_key in calibrators['phase_calibrators']:
            cal = calibrators['phase_calibrators'][phase_key]
            phase_probs.append(cal.predict([raw_prob[len(phase_probs)]])[0])
        else:
            phase_probs.append(raw_prob[len(phase_probs)])
    phase_probs = np.array(phase_probs)
    # Resource win prob
    resource_prob = df['resource_win_prob'].values if 'resource_win_prob' in df.columns else None
    # Metrics
    def metrics(label, mask):
        if mask.sum() == 0:
            return None
        d = {}
        d['Label'] = label
        d['N'] = mask.sum()
        d['Actual'] = y_true[mask].mean()
        d['Raw'] = raw_prob[mask].mean()
        d['Phase'] = phase_probs[mask].mean()
        d['Resource'] = resource_prob[mask].mean() if resource_prob is not None else np.nan
        d['Raw_Brier'] = brier_score_loss(y_true[mask], raw_prob[mask])
        d['Phase_Brier'] = brier_score_loss(y_true[mask], phase_probs[mask])
        d['Resource_Brier'] = brier_score_loss(y_true[mask], resource_prob[mask]) if resource_prob is not None else np.nan
        return d
    # High scoring: target >= 180
    if 'projected_score' in df.columns:
        high_mask = (df['projected_score'] >= 180) & (df['innings'] == 2)
        res = metrics('High Target (>=180)', high_mask)
        if res: results.append(res)
    # Low scoring: target <= 130
        low_mask = (df['projected_score'] <= 130) & (df['innings'] == 2)
        res = metrics('Low Target (<=130)', low_mask)
        if res: results.append(res)
    # Normal: 140-170
        norm_mask = (df['projected_score'] >= 140) & (df['projected_score'] <= 170) & (df['innings'] == 2)
        res = metrics('Normal Target (140-170)', norm_mask)
        if res: results.append(res)
    return pd.DataFrame(results)

def main():
    model_dir = Path('models/bbl_v12')
    features_file = Path('data/bbl_features_v4/training.parquet')
    print(f"📊 Loading training data from {features_file}")
    df = pd.read_parquet(features_file)
    print(f"📊 Loading model from {model_dir}")
    model = joblib.load(model_dir / 'champion_model.joblib')
    calibrators = joblib.load(model_dir / 'isotonic_calibrator.pkl')
    print(f"\n📈 Total samples: {len(df):,}")
    # Only second innings
    df_inn2 = df[df['innings'] == 2].copy()
    print(f"Second innings samples: {len(df_inn2):,}")
    results_df = analyze_extremes(df_inn2, model, calibrators)
    print("\n" + results_df.to_string(index=False))
    # Save
    results_df.to_csv(model_dir / 'extremes_analysis.csv', index=False)
    print(f"\n💾 Saved to {model_dir / 'extremes_analysis.csv'}")

if __name__ == '__main__':
    main()
