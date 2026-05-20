import sys, json, os, glob
sys.path.insert(0, 'src')

GT  = "Gujarat Titans"
SRH = "Sunrisers Hyderabad"

DATA  = "ipl_json"
files = sorted(glob.glob(os.path.join(DATA, "*.json")))

h2h_gt_wins = h2h_srh_wins = ahm_gt_wins = ahm_srh_wins = 0
gt_all_wins = gt_all_total = srh_all_wins = srh_all_total = 0

for f in files:
    try:
        d = json.load(open(f, encoding='utf-8'))
    except Exception:
        continue
    info   = d.get("info", {})
    teams  = info.get("teams", [])
    if len(teams) != 2:
        continue
    t1, t2 = teams[0], teams[1]
    city   = info.get("city", "")
    winner = info.get("outcome", {}).get("winner", "")

    is_gt  = lambda t: t == GT
    is_srh = lambda t: t == SRH

    if (is_gt(t1) and is_srh(t2)) or (is_gt(t2) and is_srh(t1)):
        if is_gt(winner):  h2h_gt_wins  += 1
        if is_srh(winner): h2h_srh_wins += 1
        if city == "Ahmedabad":
            if is_gt(winner):  ahm_gt_wins  += 1
            if is_srh(winner): ahm_srh_wins += 1

    if is_gt(t1) or is_gt(t2):
        gt_all_total += 1
        if is_gt(winner): gt_all_wins += 1

    if is_srh(t1) or is_srh(t2):
        srh_all_total += 1
        if is_srh(winner): srh_all_wins += 1

h2h_total = h2h_gt_wins + h2h_srh_wins
ahm_total = ahm_gt_wins + ahm_srh_wins
gt_wr     = gt_all_wins  / max(gt_all_total, 1)
srh_wr    = srh_all_wins / max(srh_all_total, 1)
h2h_wr_gt = h2h_gt_wins  / max(h2h_total, 1)
ahm_wr_gt = ahm_gt_wins  / max(ahm_total, 1) if ahm_total > 0 else gt_wr

print(f"GT  overall WR : {gt_wr:.3f}  ({gt_all_wins}/{gt_all_total})")
print(f"SRH overall WR : {srh_wr:.3f}  ({srh_all_wins}/{srh_all_total})")
print(f"H2H: {h2h_total} matches  GT:{h2h_gt_wins}  SRH:{h2h_srh_wins}  (GT h2h wr={h2h_wr_gt:.3f})")
print(f"At Ahmedabad: {ahm_total} matches  GT:{ahm_gt_wins}  SRH:{ahm_srh_wins}  (wr={ahm_wr_gt:.3f})")

# Blended pre-match win-rate (35% overall + 35% h2h + 30% venue)
gt_prematch  = 0.35 * gt_wr + 0.35 * h2h_wr_gt + 0.30 * ahm_wr_gt
srh_prematch = 1 - gt_prematch
print(f"\nBlended GT pre-match win rate: {gt_prematch:.3f}")

# ── Monte Carlo with ipl_v7 ────────────────────────────────────────────────────
from bbl_pipeline.simulation.engine import simulate
from bbl_pipeline.simulation.state  import MatchState
from bbl_pipeline.inference.predictor import Predictor

MODEL_DIR = "models/ipl_v7"
predictor = Predictor.load(MODEL_DIR, league="ipl")
print("Model loaded.")

def run_sim(batting, bowling, n=3000):
    bat_wr = gt_prematch  if batting == GT  else srh_prematch
    bow_wr = srh_prematch if batting == GT  else gt_prematch
    state  = MatchState(
        innings=1, score=0, wickets_lost=0, balls_remaining=120,
        league="ipl", batting_team=batting, bowling_team=bowling,
        venue="Narendra Modi Stadium, Ahmedabad",
        batting_team_win_rate=bat_wr, bowling_team_win_rate=bow_wr,
        batting_team_situation_wr=bat_wr, bowling_team_situation_wr=bow_wr,
    )
    return simulate(state, horizon=120, n_simulations=n,
                    model_dir=MODEL_DIR, predictor=predictor)

print("Simulating GT batting first …")
r1 = run_sim(GT, SRH)
print(f"  GT wins (bat first)  : {r1.mean_prob:.3f} +/- {r1.std_prob:.3f}")

print("Simulating SRH batting first …")
r2 = run_sim(SRH, GT)
gt_bowl = 1 - r2.mean_prob
print(f"  GT wins (bowl first) : {gt_bowl:.3f} +/- {r2.std_prob:.3f}")

gt_final  = 0.5 * r1.mean_prob + 0.5 * gt_bowl
srh_final = 1 - gt_final
pct_gt  = round(gt_final  * 100)
pct_srh = round(srh_final * 100)

print(f"\n=== GT  pre-match win probability : {pct_gt}% ===")
print(f"=== SRH pre-match win probability : {pct_srh}% ===")
