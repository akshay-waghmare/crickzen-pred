"""Analyze feature importance including new bat/bowl first features."""
import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.feature_selection import mutual_info_classif
import warnings
warnings.filterwarnings('ignore')

# Load data
df = pd.read_parquet('data/training_sampled.parquet')
X = df.drop('is_winner', axis=1)
y = df['is_winner']

print(f"Data: {len(df)} samples, {X.shape[1]} features")
print("=" * 70)

# Calculate Mutual Information
print("\nMutual Information Scores:")
print("-" * 70)

mi_scores = mutual_info_classif(X, y, random_state=42)
mi_df = pd.DataFrame({'feature': X.columns, 'mi_score': mi_scores})
mi_df = mi_df.sort_values('mi_score', ascending=False)

for _, row in mi_df.iterrows():
    print(f"  {row['feature']:<35} MI={row['mi_score']:.4f}")

# Focus on new features
print("\n" + "=" * 70)
print("NEW BAT/BOWL FIRST FEATURES:")
print("-" * 70)

new_features = ['batting_team_situation_wr', 'bowling_team_situation_wr', 'situation_advantage']
for feat in new_features:
    if feat in mi_df['feature'].values:
        score = mi_df[mi_df['feature'] == feat]['mi_score'].values[0]
        print(f"  {feat}: MI={score:.4f}")

# Train model and check feature importance
print("\n" + "=" * 70)
print("XGBoost Feature Importance (Gain):")
print("-" * 70)

model = XGBClassifier(
    n_estimators=700, max_depth=2, learning_rate=0.010,
    subsample=0.5, colsample_bytree=0.5, min_child_weight=30,
    reg_alpha=3.0, reg_lambda=4.0, random_state=42
)
model.fit(X, y)

importance_df = pd.DataFrame({
    'feature': X.columns,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)

for _, row in importance_df.iterrows():
    marker = " <-- NEW" if row['feature'] in new_features else ""
    print(f"  {row['feature']:<35} {row['importance']:.4f}{marker}")
