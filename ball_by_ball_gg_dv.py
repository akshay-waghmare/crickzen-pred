"""
Ball-by-ball win probability analysis for Gulf Giants vs Desert Vipers
Gulf Giants batting first - tracking their win probability ball by ball
"""
from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState

pred = Predictor.load('models/ilt20_v3', 'data/ilt_feature_store_v2')

# Ball-by-ball data extracted from commentary
# Format: (over, ball, score, wickets, description)
balls = [
    # Over 1 - Payne bowling to Nissanka/Gurbaz
    (0, 1, 0, 0, "Dot - Nissanka blocks"),
    (0, 2, 0, 0, "Dot - Nissanka inside edges to pad"),
    (0, 3, 0, 0, "Dot - Nissanka cuts, inside edge"),
    (0, 4, 6, 0, "SIX - Nissanka pulls over deep sq leg"),
    (0, 5, 10, 0, "FOUR - Nissanka whips to fine leg"),
    (0, 6, 14, 0, "FOUR - Nissanka slaps through covers"),
    
    # Over 2 - Tanvir bowling
    (1, 1, 14, 0, "Dot - Gurbaz leaves"),
    (1, 2, 14, 0, "Dot - Gurbaz swings and misses"),
    (1, 3, 16, 0, "2 runs - Gurbaz steers to third man"),
    (1, 4, 16, 1, "WICKET - Gurbaz BOWLED!"),
    (1, 5, 16, 1, "Dot - Vince blocks"),
    (1, 6, 16, 2, "WICKET - Vince edges to keeper!"),
    
    # Over 3 - Ferguson bowling
    (2, 1, 20, 2, "FOUR - Nissanka lofts over cover"),
    (2, 2, 20, 2, "Dot - Nissanka digs out yorker"),
    (2, 3, 21, 2, "1 run - Nissanka skies, dropped! (+ wide)"),
    (2, 4, 21, 2, "Dot - Mayers jams yorker"),
    (2, 5, 21, 2, "Dot - LBW appeal, inside edge"),
    (2, 6, 21, 2, "Dot - Mayers guides to point"),
    
    # Over 4 - Tanvir bowling
    (3, 1, 21, 2, "Dot - Nissanka swings and misses"),
    (3, 2, 21, 2, "Dot - Nissanka beaten outside edge"),
    (3, 3, 21, 3, "WICKET - Nissanka caught at mid-on!"),
    (3, 4, 21, 3, "Dot - Erasmus beaten outside edge"),
    (3, 5, 21, 3, "Dot - Erasmus beaten again"),
    (3, 6, 22, 3, "1 run - Erasmus punches to deep point"),
    
    # Over 5 - Ferguson bowling
    (4, 1, 23, 3, "1 run - Erasmus drives to deep point"),
    (4, 2, 23, 3, "Dot - Mayers beaten outside edge"),
    (4, 3, 23, 3, "Dot - Mayers beaten again"),
    (4, 4, 26, 3, "3 runs - Mayers skies, drops short of Hetmyer"),
    (4, 5, 26, 3, "Dot - Erasmus stopped by diving Holden"),
    (4, 6, 27, 3, "1 run - Erasmus slashes to deep point"),
    
    # Over 6 - Tanvir bowling (end of powerplay)
    (5, 1, 28, 3, "1 run - Erasmus taps to mid-on"),
    (5, 2, 28, 3, "Dot - Mayers jams yorker"),
    (5, 3, 29, 3, "1 leg bye - Mayers hit on thigh"),
    (5, 4, 29, 3, "Dot - Erasmus late on drive"),
    (5, 5, 29, 4, "WICKET - Erasmus edges to slip!"),
    (5, 6, 29, 4, "Dot - Asif Khan beaten, squared up"),
    
    # Over 7 - Curran bowling
    (6, 1, 29, 4, "Dot - Mayers chops to point"),
    (6, 2, 30, 4, "1 run - Mayers punches to deep cover"),
    (6, 3, 31, 4, "1 run - Asif tucks to mid-wicket"),
    (6, 4, 32, 4, "1 run - Mayers top edges, falls safe"),
    (6, 5, 32, 4, "Dot - Asif defends to cover"),
    (6, 6, 33, 4, "1 run - Asif edges to third man"),
]

print("=" * 100)
print("GULF GIANTS vs DESERT VIPERS - 1st INNINGS BALL-BY-BALL ANALYSIS")
print("Gulf Giants batting first")
print("=" * 100)
print()
print(f"{'Over':<6} {'Score':<8} {'Wkts':<6} {'GG Win%':<10} {'DV Win%':<10} {'Description':<50}")
print("-" * 100)

for over, ball, score, wickets, desc in balls:
    over_display = f"{over}.{ball}"
    
    state = MatchState(
        match_id='gg_vs_dv',
        venue='Dubai International Cricket Stadium',
        batting_team='Gulf Giants',
        bowling_team='Desert Vipers',
        innings=1,
        over=over, ball=ball,
        current_score=score,
        wickets_lost=wickets,
        target_runs=None,
        batsman_1='Test', batsman_2='Test', bowler='Test'
    )
    
    gg_prob = pred.predict(state)
    dv_prob = 1 - gg_prob
    
    # Highlight wickets and key moments
    if "WICKET" in desc:
        marker = "🔴"
    elif "SIX" in desc or "FOUR" in desc:
        marker = "🟢"
    else:
        marker = "  "
    
    print(f"{over_display:<6} {score}/{wickets:<5} {'':<2} {gg_prob*100:>6.1f}%    {dv_prob*100:>6.1f}%    {marker} {desc:<48}")

print("-" * 100)
print()

# Summary by over
print("=" * 100)
print("SUMMARY BY OVER END")
print("=" * 100)
print(f"{'Over':<8} {'Score':<10} {'GG Win%':<12} {'DV Win%':<12} {'Notes':<40}")
print("-" * 100)

over_ends = [
    (1, 14, 0, "Strong start - Nissanka 14*(6)"),
    (2, 16, 2, "Collapse! Gurbaz & Vince out"),
    (3, 21, 2, "Nissanka dropped, survives"),
    (4, 22, 3, "Nissanka out - 3/22"),
    (5, 27, 3, "Mayers off mark, Erasmus steady"),
    (6, 29, 4, "Erasmus out! 4/29 at PP end"),
    (7, 33, 4, "34/4 - End of available data"),
]

for over, score, wickets, notes in over_ends:
    state = MatchState(
        match_id='gg_vs_dv',
        venue='Dubai International Cricket Stadium',
        batting_team='Gulf Giants',
        bowling_team='Desert Vipers',
        innings=1,
        over=over, ball=0,
        current_score=score,
        wickets_lost=wickets,
        target_runs=None,
        batsman_1='Test', batsman_2='Test', bowler='Test'
    )
    
    gg_prob = pred.predict(state)
    dv_prob = 1 - gg_prob
    
    print(f"End {over:<4} {score}/{wickets:<6} {gg_prob*100:>8.1f}%     {dv_prob*100:>8.1f}%     {notes}")

print("-" * 100)
print()

# Key moments analysis
print("=" * 100)
print("KEY MOMENTS ANALYSIS")
print("=" * 100)
key_moments = [
    ("Start", 0, 0, 0, 0),
    ("After Nissanka 6+4+4", 0, 6, 14, 0),
    ("Gurbaz BOWLED (1.4)", 1, 4, 16, 1),
    ("Vince OUT (1.6)", 1, 6, 16, 2),
    ("Nissanka OUT (3.3)", 3, 3, 21, 3),
    ("Erasmus OUT (5.5)", 5, 5, 29, 4),
    ("End of Over 7", 6, 6, 34, 4),
]

print(f"{'Moment':<30} {'Score':<10} {'GG Win%':<12} {'DV Win%':<12} {'Swing':<10}")
print("-" * 100)

prev_gg = None
for moment, over, ball, score, wickets in key_moments:
    state = MatchState(
        match_id='gg_vs_dv',
        venue='Dubai International Cricket Stadium',
        batting_team='Gulf Giants',
        bowling_team='Desert Vipers',
        innings=1,
        over=over, ball=ball,
        current_score=score,
        wickets_lost=wickets,
        target_runs=None,
        batsman_1='Test', batsman_2='Test', bowler='Test'
    )
    
    gg_prob = pred.predict(state)
    dv_prob = 1 - gg_prob
    
    swing = ""
    if prev_gg is not None:
        diff = (gg_prob - prev_gg) * 100
        if abs(diff) > 1:
            swing = f"{diff:+.1f}%"
    
    print(f"{moment:<30} {score}/{wickets:<6} {gg_prob*100:>8.1f}%     {dv_prob*100:>8.1f}%     {swing}")
    prev_gg = gg_prob

print("-" * 100)
