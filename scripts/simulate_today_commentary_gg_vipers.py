"""Simulate win-probability ball-by-ball from commentary text.

This uses the same inference path as live prediction: `Predictor.predict()`.

Usage:
    # From a file
    python scripts/simulate_today_commentary_gg_vipers.py --commentary-file path\\to\\commentary.txt --model-dir models\\ilt20_v3_tuned

    # From stdin (paste into terminal then Ctrl+Z Enter on Windows)
    Get-Content .\\commentary.txt -Raw | python scripts\\simulate_today_commentary_gg_vipers.py --model-dir models\\ilt20_v3_tuned

    # Sample input (only for quick sanity checks)
    python scripts\\simulate_today_commentary_gg_vipers.py --use-sample
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import pandas as pd

from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState


SAMPLE_COMMENTARY = r"""
0.6
D Payne to P Nissanka
4
0.5
D Payne to P Nissanka
4
0.4
D Payne to P Nissanka
6
0.3
D Payne to P Nissanka
0
0.2
D Payne to P Nissanka
0
0.1
D Payne to P Nissanka
0

1.6
Tanvir to J Vince
W
1.5
Tanvir to J Vince
0
1.4
Tanvir to R Gurbaz
W
1.3
Tanvir to R Gurbaz
2
1.2
Tanvir to R Gurbaz
0
1.1
Tanvir to R Gurbaz
0

2.6
L Ferguson to K Mayers
0
2.5
L Ferguson to K Mayers
0
2.4
L Ferguson to K Mayers
0
2.3
L Ferguson to P Nissanka
1
2.3
L Ferguson to P Nissanka
WD
2.2
L Ferguson to P Nissanka
0
2.1
L Ferguson to P Nissanka
4

3.6
Tanvir to G Erasmus
1
3.5
Tanvir to G Erasmus
0
3.4
Tanvir to G Erasmus
0
3.3
Tanvir to P Nissanka
W
3.2
Tanvir to P Nissanka
0
3.1
Tanvir to P Nissanka
0

4.6
L Ferguson to G Erasmus
1
4.5
L Ferguson to G Erasmus
0
4.4
L Ferguson to K Mayers
3
4.3
L Ferguson to K Mayers
0
4.2
L Ferguson to K Mayers
0
4.1
L Ferguson to G Erasmus
1

5.6
Tanvir to A Khan
0
5.5
Tanvir to G Erasmus
W
5.4
Tanvir to G Erasmus
0
5.3
Tanvir to K Mayers
1lb
5.2
Tanvir to K Mayers
0
5.1
Tanvir to G Erasmus
1

6.6
S Curran to A Khan
1
6.5
S Curran to A Khan
0
6.4
S Curran to K Mayers
1
6.3
S Curran to A Khan
1
6.2
S Curran to K Mayers
1
6.1
S Curran to K Mayers
0
""".strip()


@dataclass(frozen=True)
class Delivery:
    over: int
    ball: int
    bowler: str
    batter: str
    outcome: str


_OB_RE = re.compile(r"^(?P<over>\d+)\.(?P<ball>\d+)$")
_TO_RE = re.compile(r"^(?P<bowler>.+?)\s+to\s+(?P<batter>.+?)$")


def parse_deliveries(text: str) -> List[Delivery]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    deliveries: List[Delivery] = []
    i = 0
    while i < len(lines):
        m_ob = _OB_RE.match(lines[i])
        if not m_ob:
            i += 1
            continue

        over = int(m_ob.group('over'))
        ball = int(m_ob.group('ball'))

        # Expect: next line is "X to Y", next line is outcome token.
        if i + 2 >= len(lines):
            break

        m_to = _TO_RE.match(lines[i + 1])
        if not m_to:
            i += 1
            continue

        bowler = m_to.group('bowler').strip()
        batter = m_to.group('batter').strip()
        outcome = lines[i + 2].strip()

        deliveries.append(Delivery(over=over, ball=ball, bowler=bowler, batter=batter, outcome=outcome))
        i += 3

    # Commentary is often pasted newest-first (e.g. 0.6, 0.5, 0.4 ...).
    # Simulate in chronological order, and for duplicate over.ball entries
    # ensure wides/noballs are applied BEFORE the legal delivery (same ball number).
    def _tie_break(d: Delivery) -> int:
        token = d.outcome.strip().upper()
        return 0 if token in {'WD', 'NB'} else 1

    deliveries.sort(key=lambda d: (d.over, d.ball, _tie_break(d)))
    return deliveries


def outcome_to_runs_wicket_legal(outcome: str) -> Tuple[int, int, bool]:
    token = outcome.strip().upper()

    if token == 'W':
        return 0, 1, True

    if token == 'WD':
        return 1, 0, False

    m = re.match(r"^(?P<runs>\d+)(?P<extra>LB|B)$", token)
    if m:
        return int(m.group('runs')), 0, True

    if token.isdigit():
        return int(token), 0, True

    # Fallback: treat unknown as 0, legal
    return 0, 0, True


def align_features_for_model(predictor: Predictor, X: pd.DataFrame) -> pd.DataFrame:
    expected_features: Optional[List[str]] = None
    model = predictor.model

    if hasattr(model, 'feature_names_in_'):
        expected_features = list(model.feature_names_in_)
    elif hasattr(model, 'selected_features_'):
        expected_features = list(model.selected_features_)

    if not expected_features:
        return X

    for feat in expected_features:
        if feat not in X.columns:
            if 'rate' in feat.lower() or 'avg' in feat.lower():
                X[feat] = 0.0
            elif feat.lower().startswith('is_'):
                X[feat] = 0
            elif 'pct' in feat.lower() or 'prob' in feat.lower():
                X[feat] = 0.5
            else:
                X[feat] = 0.0

    return X[expected_features]


def simulate(
    predictor: Predictor,
    deliveries: Iterable[Delivery],
    venue: str,
    batting_team: str,
    bowling_team: str,
    innings: int,
) -> pd.DataFrame:
    total_score = 0
    total_wkts = 0

    rows = []

    for d in deliveries:
        runs, wk, _legal = outcome_to_runs_wicket_legal(d.outcome)
        total_score += runs
        total_wkts += wk

        state = MatchState(
            match_id='commentary_sim',
            venue=venue,
            batting_team=batting_team,
            bowling_team=bowling_team,
            innings=innings,
            over=d.over,
            ball=d.ball,
            current_score=total_score,
            wickets_lost=total_wkts,
            batsman_1=d.batter,
            batsman_2='Unknown',
            bowler=d.bowler,
            target_runs=None,
        )

        final_prob = float(predictor.predict(state))

        rows.append(
            {
                'over_ball': f"{d.over}.{d.ball}",
                'batting': batting_team,
                'score': total_score,
                'wickets': total_wkts,
                'event': d.outcome,
                'striker': d.batter,
                'bowler': d.bowler,
                'final_win_prob': final_prob,
            }
        )

    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-dir', default='models/ilt20_v3_tuned')
    parser.add_argument('--feature-store-dir', default='data/ilt_feature_store_v2')
    parser.add_argument('--commentary-file', default=None)
    parser.add_argument('--use-sample', action='store_true', help='Use embedded sample commentary (debug only)')
    parser.add_argument('--venue', default='Dubai International Cricket Stadium')
    parser.add_argument('--batting-team', default='Gulf Giants')
    parser.add_argument('--bowling-team', default='Desert Vipers')
    parser.add_argument('--innings', type=int, default=1)
    parser.add_argument('--out-csv', default=None)
    args = parser.parse_args()

    text: Optional[str] = None
    if args.commentary_file:
        text = Path(args.commentary_file).read_text(encoding='utf-8')
    elif args.use_sample:
        text = SAMPLE_COMMENTARY
    else:
        # Try stdin (for piping/paste). If nothing is provided, error with guidance.
        if not sys.stdin.isatty():
            text = sys.stdin.read()
        else:
            raise SystemExit(
                "No commentary provided. Use --commentary-file <path>, pipe text via stdin, or pass --use-sample."
            )

    predictor = Predictor.load(args.model_dir, args.feature_store_dir)
    deliveries = parse_deliveries(text)

    if not deliveries:
        raise RuntimeError('No deliveries parsed. Check input format.')

    df = simulate(
        predictor=predictor,
        deliveries=deliveries,
        venue=args.venue,
        batting_team=args.batting_team,
        bowling_team=args.bowling_team,
        innings=args.innings,
    )

    # Print a clean table
    pd.set_option('display.width', 200)
    pd.set_option('display.max_columns', 50)
    print(df.to_string(index=False))

    if args.out_csv:
        out_path = Path(args.out_csv)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=False)
        print(f"\nSaved: {out_path}")

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
