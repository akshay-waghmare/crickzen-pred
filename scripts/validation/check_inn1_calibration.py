import pandas as pd

df = pd.read_parquet('data/bbl_features_v2/training.parquet')

# Filter to first innings
innings1 = df[df['innings'] == 1].copy()

print('\n' + '=' * 70)
print('FIRST INNINGS TRAINING DATA ANALYSIS')
print('=' * 70)
print(f'\nTotal first innings samples: {len(innings1):,}')
print(f'Overall win rate: {innings1["is_winner"].mean():.1%}\n')

# Check early powerplay scenarios (14-15 overs remaining = 5-6 overs bowled, score 40-50, 0-2 wickets)
early_pp = innings1[
    (innings1['overs_remaining'] >= 14) & (innings1['overs_remaining'] <= 15) & 
    (innings1['projected_score'] >= 165) & (innings1['projected_score'] <= 185) &
    (innings1['wickets_lost'] <= 2)
]

print('Similar scenarios to current match (proj 165-185, 0-2 wickets, 14-15 overs left):')
print(f'  Number of scenarios: {len(early_pp)}')
if len(early_pp) > 0:
    print(f'  Actual win rate: {early_pp["is_winner"].mean():.1%}')
    
    # Get average projected score
    print(f'  Average projected score: {early_pp["projected_score"].mean():.1f}')

print('\n' + '=' * 70)
print('WIN RATE BY OVERS REMAINING (First Innings):')
print('=' * 70)
for over_range in [(15, 20), (10, 15), (5, 10), (0, 5)]:
    over_data = innings1[
        (innings1['overs_remaining'] >= over_range[0]) & 
        (innings1['overs_remaining'] < over_range[1])
    ]
    if len(over_data) > 0:
        print(f'  {over_range[0]:2d}-{over_range[1]:2d} overs left: '
              f'{over_data["is_winner"].mean():.1%} '
              f'({len(over_data):,} samples)')

# Check resource_win_prob vs actual outcomes
print('\n' + '=' * 70)
print('RESOURCE WIN PROB vs ACTUAL (First Innings):')
print('=' * 70)
for prob_range in [(0.0, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 1.0)]:
    data = innings1[
        (innings1['resource_win_prob'] >= prob_range[0]) & 
        (innings1['resource_win_prob'] < prob_range[1])
    ]
    if len(data) > 0:
        print(f'  Resource prob {prob_range[0]:.1f}-{prob_range[1]:.1f}: '
              f'Actual win rate {data["is_winner"].mean():.1%} '
              f'({len(data):,} samples)')
