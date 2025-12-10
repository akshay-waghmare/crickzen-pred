"""Show feature importance for the champion model."""
import joblib
import pandas as pd

model = joblib.load('models/champion_final/champion_model.joblib')

# Get feature importances from XGBoost component
xgb_importance = model.xgb_model_.feature_importances_

# Get coefficients from LogReg component (it's a Pipeline, access the 'clf' step)
logreg_coef = abs(model.logreg_model_.named_steps['clf'].coef_[0])

# Create DataFrame
df = pd.DataFrame({
    'feature': model.selected_features_,
    'xgb_importance': xgb_importance,
    'logreg_coef': logreg_coef
})

# Normalize both to 0-1 scale for comparison
df['xgb_norm'] = df['xgb_importance'] / df['xgb_importance'].max()
df['logreg_norm'] = df['logreg_coef'] / df['logreg_coef'].max()

# Combined importance (weighted by ensemble weights 50/50)
df['combined'] = 0.5 * df['xgb_norm'] + 0.5 * df['logreg_norm']

# Sort by combined importance
df = df.sort_values('combined', ascending=False)

print('=' * 80)
print('FEATURE IMPORTANCE - XGBLogRegEnsemble (Champion Model)')
print('=' * 80)
header = f"{'Rank':<5} {'Feature':<32} {'XGB':<10} {'LogReg':<10} {'Combined':<10}"
print(header)
print('-' * 80)

for i, row in enumerate(df.itertuples(), 1):
    bar = '█' * int(row.combined * 20)
    line = f"{i:<5} {row.feature:<32} {row.xgb_norm:.4f}    {row.logreg_norm:.4f}    {row.combined:.4f} {bar}"
    print(line)

print('=' * 80)
print("\nTop 5 most important features:")
for i, row in enumerate(df.head(5).itertuples(), 1):
    print(f"  {i}. {row.feature}")
