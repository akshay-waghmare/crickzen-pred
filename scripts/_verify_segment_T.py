"""Verify segment-aware T scaling applies correctly to all 6 segments."""
from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState

p = Predictor.load('models/ipl_v7', 'data/ipl_feature_store_v3', league='ipl')

tests = [
    # label,           inn, over(0idx), score, wkts, tgt, fis,  expect_T_applied
    ('Inn1 PP  ov3',   1, 2,  55, 2, 0,   0,   True),
    ('Inn1 Mid ov10',  1, 9,  95, 3, 0,   0,   False),
    ('Inn1 Death ov17',1, 16, 145,4, 0,   0,   False),
    ('Inn2 PP  ov3',   2, 2,  35, 2, 160, 160, True),
    ('Inn2 Mid ov10',  2, 9,  85, 3, 160, 160, True),
    # Inn2 Death — use close match so constraint layer doesn't kick in
    ('Inn2 Death ov17',2, 16, 148,5, 160, 160, False),
]

print(f"  {'Segment':<22} {'PerOverCal':>10} {'ProdT':>8}  {'Shadow':>16}  {'T applied?':<12}")
print('-' * 78)
all_ok = True
for label, inn, ov, score, wkts, tgt, fis, should_apply in tests:
    s = MatchState(
        match_id='test', venue='Narendra Modi Stadium, Ahmedabad',
        batting_team='Punjab Kings', bowling_team='Gujarat Titans',
        innings=inn, over=ov, ball=0, current_score=score, wickets_lost=wkts,
        batsman_1='', batsman_2='', bowler='',
        target_runs=tgt, first_innings_score=fis, total_overs=20,
        toss_winner='Gujarat Titans', toss_decision='bowl',
        inn1_wickets_lost=4, inn1_pp_runs=52, inn1_death_rr=10.5
    )
    prod = p.predict(s, ball_history=[])
    raw_cal = p.last_calibrated_per_over
    shadow = getattr(p, 'last_shadow_prob', prod)
    t_used = getattr(p, 'last_t_applied', 1.0)
    t_applied = t_used != 1.0
    ok = t_applied == should_apply
    all_ok = all_ok and ok
    t_str = f'YES({t_used})' if t_applied else 'NO (1.0) '
    shadow_str = f'{shadow:.1%} ({(shadow-prod)*100:+.1f}pp)' if abs(shadow - prod) > 0.002 else 'same as prod'
    print(f"  {label:<22} {raw_cal:>10.1%} {prod:>8.1%}  {shadow_str:>16}  {t_str}  [{'OK' if ok else 'FAIL'}]")

print()
print('ALL SEGMENTS OK' if all_ok else 'FAILURES DETECTED')
