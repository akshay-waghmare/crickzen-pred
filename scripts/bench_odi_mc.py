"""Quick benchmark for ODI MC simulation latency (SC-004: < 500ms per ball)."""
import time
from bbl_pipeline.simulation.engine import simulate_vectorized
from bbl_pipeline.simulation.state import MatchState

scenarios = [
    ("Inn1 Start", dict(total_balls=300, innings=1, score=0, wickets_lost=0, balls_remaining=300, league="odi", batting_team="A", bowling_team="B")),
    ("Inn1 PP", dict(total_balls=300, innings=1, score=45, wickets_lost=1, balls_remaining=240, league="odi", batting_team="A", bowling_team="B")),
    ("Inn1 Mid", dict(total_balls=300, innings=1, score=150, wickets_lost=3, balls_remaining=120, league="odi", batting_team="A", bowling_team="B")),
    ("Inn1 Death", dict(total_balls=300, innings=1, score=230, wickets_lost=5, balls_remaining=60, league="odi", batting_team="A", bowling_team="B")),
    ("Inn2 Start", dict(total_balls=300, innings=2, score=0, wickets_lost=0, balls_remaining=300, league="odi", batting_team="A", bowling_team="B", target_runs=280)),
    ("Inn2 Mid", dict(total_balls=300, innings=2, score=120, wickets_lost=2, balls_remaining=150, league="odi", batting_team="A", bowling_team="B", target_runs=280)),
    ("Inn2 Death", dict(total_balls=300, innings=2, score=220, wickets_lost=4, balls_remaining=60, league="odi", batting_team="A", bowling_team="B", target_runs=280)),
]

header = f"{'Scenario':<15} {'Time(ms)':<10} {'WinPct':<8} {'Status'}"
print(header)
print("-" * 50)
all_pass = True
for name, kwargs in scenarios:
    state = MatchState(**kwargs)
    start = time.perf_counter()
    result = simulate_vectorized(state, n_simulations=5000)
    elapsed_ms = (time.perf_counter() - start) * 1000
    status = "PASS" if elapsed_ms < 500 else "FAIL"
    if elapsed_ms >= 500:
        all_pass = False
    print(f"{name:<15} {elapsed_ms:<10.1f} {result.mean_prob*100:<8.1f} {status}")

print()
if all_pass:
    print("Performance: ALL PASS (< 500ms per ball with 5000 sims)")
else:
    print("Performance: SOME FAILED (>= 500ms)")
