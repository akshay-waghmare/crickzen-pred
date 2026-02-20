"""
Test cascaded calibration: Global OOF → League Temperature
"""
import joblib
import pandas as pd
import numpy as np
from sklearn.metrics import brier_score_loss, log_loss

# Load models and data
print("Loading models and data...")
global_model = joblib.load('models/t20_male_v1/champion_model.joblib')
global_cal = joblib.load('models/t20_male_v1/isotonic_calibrator.pkl')
league_cal = joblib.load('models/t20_male_v1/league_calibrators/bbl/isotonic_calibrator.pkl')

# Load BBL data
df = pd.read_parquet('data/bbl_features_v4/training.parquet')
print(f"Loaded {len(df):,} BBL samples")

# Get features
features = global_model.selected_features_
X = df[features]
y_true = df['is_winner'].values
innings = df['innings'].values

# Pipeline 1: Raw → League Cal (current approach)
print("\n=== PIPELINE 1: Raw → League Cal (Current) ===")
raw_probs = global_model.predict_proba(X)[:, 1]
brier_raw = brier_score_loss(y_true, raw_probs)
logloss_raw = log_loss(y_true, np.clip(raw_probs, 1e-7, 1-1e-7))

# Apply league calibration directly
league_cal_probs = np.zeros_like(raw_probs)
for inn in [1, 2]:
    mask = innings == inn
    cal_key = f'calibrator_innings{inn}'
    league_cal_probs[mask] = league_cal[cal_key].predict(raw_probs[mask])

brier_league = brier_score_loss(y_true, league_cal_probs)
logloss_league = log_loss(y_true, np.clip(league_cal_probs, 1e-7, 1-1e-7))

print(f"Raw:               Brier {brier_raw:.4f}, LogLoss {logloss_raw:.4f}")
print(f"→ League Cal:      Brier {brier_league:.4f}, LogLoss {logloss_league:.4f}")
print(f"Improvement:       Brier {(brier_league/brier_raw - 1)*100:+.2f}%, LogLoss {(logloss_league/logloss_raw - 1)*100:+.2f}%")

# Pipeline 2: Raw → Global OOF → League Cal (cascaded)
print("\n=== PIPELINE 2: Raw → Global OOF → League Cal (Cascaded) ===")

# Step 1: Apply global OOF calibration
global_oof_probs = np.zeros_like(raw_probs)
for inn in [1, 2]:
    mask = innings == inn
    cal_key = f'calibrator_innings{inn}'
    global_oof_probs[mask] = global_cal[cal_key].predict(raw_probs[mask])

brier_global_oof = brier_score_loss(y_true, global_oof_probs)
logloss_global_oof = log_loss(y_true, np.clip(global_oof_probs, 1e-7, 1-1e-7))

print(f"Raw:               Brier {brier_raw:.4f}, LogLoss {logloss_raw:.4f}")
print(f"→ Global OOF:      Brier {brier_global_oof:.4f}, LogLoss {logloss_global_oof:.4f}")

# Step 2: Apply league calibration on top of global OOF
cascaded_probs = np.zeros_like(global_oof_probs)
for inn in [1, 2]:
    mask = innings == inn
    cal_key = f'calibrator_innings{inn}'
    cascaded_probs[mask] = league_cal[cal_key].predict(global_oof_probs[mask])

brier_cascaded = brier_score_loss(y_true, cascaded_probs)
logloss_cascaded = log_loss(y_true, np.clip(cascaded_probs, 1e-7, 1-1e-7))

print(f"→ League Cal:      Brier {brier_cascaded:.4f}, LogLoss {logloss_cascaded:.4f}")
print(f"Total Improvement: Brier {(brier_cascaded/brier_raw - 1)*100:+.2f}%, LogLoss {(logloss_cascaded/logloss_raw - 1)*100:+.2f}%")

# Comparison
print("\n" + "="*60)
print("COMPARISON:")
print("="*60)
print(f"Pipeline 1 (Raw → League):          Brier {brier_league:.4f}, LogLoss {logloss_league:.4f}")
print(f"Pipeline 2 (Raw → Global → League): Brier {brier_cascaded:.4f}, LogLoss {logloss_cascaded:.4f}")
print(f"Winner:                             ", end="")
if brier_cascaded < brier_league:
    print(f"Pipeline 2 by {(1 - brier_cascaded/brier_league)*100:.2f}% (Brier)")
elif brier_league < brier_cascaded:
    print(f"Pipeline 1 by {(1 - brier_league/brier_cascaded)*100:.2f}% (Brier)")
else:
    print("Tie")

print("\nConclusion:")
if brier_cascaded < brier_league:
    print("✅ Cascaded calibration (Global OOF → League) is BETTER!")
    print("   Recommend using this approach for production.")
else:
    print("❌ Direct league calibration (skip global OOF) is BETTER!")
    print("   Keep current approach.")
