"""
Extract and compare features from predict() vs predict_batch() to find discrepancies.
"""
from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState as InferenceState
from bbl_pipeline.simulation.state import MatchState as SimState
import pandas as pd
import numpy as np

print('=== Feature Extraction: predict() vs predict_batch() ===')
print()

predictor = Predictor.load(
    model_dir='models/t20_female_v3',
    feature_store_dir='data/t20_female_feature_store_v3',
    league='wpl'
)

# Test state: 0/0, start of match
inference_state = InferenceState(
    match_id='test',
    innings=1,
    over=0,
    ball=0,
    current_score=0,
    wickets_lost=0,
    target_runs=None,
    batting_team='GGW',
    bowling_team='UPW',
    batsman_1='Unknown',
    batsman_2='Unknown',
    bowler='Unknown',
    venue='Unknown'
)

# Get features from predict() via RealTimeFeatureMapper
scraped_data = {
    'innings_num': inference_state.innings,
    'over_number': inference_state.over,
    'ball_number': inference_state.ball,
    'total_score': inference_state.current_score,
    'total_wickets': inference_state.wickets_lost,
    'current_batsman': inference_state.batsman_1,
    'non_striker': inference_state.batsman_2,
    'current_bowler': inference_state.bowler,
    'batting_team': inference_state.batting_team,
    'bowling_team': inference_state.bowling_team,
    'venue': inference_state.venue,
    'target_score': inference_state.target_runs,
    'runs_needed': 0,
}

X_predict = predictor.feature_mapper.create_feature_dataframe(scraped_data)
print('Features from predict() [RealTimeFeatureMapper]:')
print('  Columns:', len(X_predict.columns))

# Build FeatureContext with historical stats
ctx = predictor.build_feature_context(
    batting_team='GGW',
    bowling_team='UPW',
    venue='Unknown',
    league='wpl',
    innings=1
)

# Now call predict_batch with a single state to get its features
sim_state = SimState(
    innings=1,
    score=0,
    wickets_lost=0,
    balls_remaining=120,
    target_runs=None,
    batting_team='GGW',
    bowling_team='UPW',
    venue='Unknown',
    league='wpl'
)

# Call predict_batch to get the actual probabilities
batch_prob = predictor.predict_batch([sim_state], feature_context=ctx, league='wpl')

# Get predict() probability
predict_prob = predictor.predict(inference_state, debug=False)

print()
print('=== PREDICTION COMPARISON ===')
print(f'  predict():        {predict_prob:.4f} ({predict_prob*100:.2f}%)')
print(f'  predict_batch():  {batch_prob[0]:.4f} ({batch_prob[0]*100:.2f}%)')
print(f'  GAP:              {abs(predict_prob - batch_prob[0]):.4f} ({abs(predict_prob - batch_prob[0])*100:.2f}pp)')

# Now let's get ALL model features and compare
print()
print('=== MODEL FEATURES (Top 25 used by model) ===')
print()

# Get expected features from model
expected_features = None
if hasattr(predictor.model, 'selected_features_'):
    expected_features = predictor.model.selected_features_
elif hasattr(predictor.model, 'feature_names_in_'):
    expected_features = list(predictor.model.feature_names_in_)

if expected_features:
    print(f"Model uses {len(expected_features)} features:")
    print()
    print(f"{'Feature':<30} {'predict() val':<15}")
    print("-" * 50)
    for feat in expected_features:
        if feat in X_predict.columns:
            val = X_predict[feat].iloc[0]
            print(f"{feat:<30} {val:<15.6f}")
        else:
            print(f"{feat:<30} {'MISSING!':<15}")

print()
print('=== RESOURCE FEATURES FROM CALCULATOR (used by predict()) ===')
resource_features = predictor.resource_calculator.calculate_all_features(
    innings=1,
    over=0,
    ball=0,
    current_score=0,
    wickets_lost=0,
    target_runs=None
)
for k, v in sorted(resource_features.items()):
    print(f'  {k}: {v}')

print()
print('=== VECTORIZED FEATURES IN predict_batch() (calculated differently) ===')
print('These are approximations that differ from ResourceFeatureCalculator:')
print('  - resource_win_prob: Uses simplified sigmoid, not DLS tables')
print('  - expected_final_score: Uses linear projection, not weighted regression')
print('  - score_vs_par: Different formula than calculator')

print()
print('=== SOLUTION: predict_batch should use ResourceFeatureCalculator ===')
print('The gap comes from simplified formulas in predict_batch() vs full')
print('ResourceFeatureCalculator.calculate_all_features() used by predict().')
