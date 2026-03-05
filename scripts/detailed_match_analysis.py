"""
Analyze model vs market predictions with actual outcomes for all T20 World Cup 2026 recorded matches.

Repairs market_batting_team_prob from market_fav_prob + market_fav_team for older recordings
that used exact string equality instead of alias matching.
"""

import pandas as pd
import numpy as np
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# Team alias mapping (mirrors MatchStateLogger._team_aliases)
# ──────────────────────────────────────────────────────────────────────────────
COUNTRY_CODE_MAP = {
    "AUSTRALIA": "AUS", "INDIA": "IND", "ENGLAND": "ENG",
    "NEWZEALAND": "NZ", "SOUTHAFRICA": "SA", "PAKISTAN": "PAK",
    "WESTINDIES": "WI", "SRILANKA": "SL", "BANGLADESH": "BAN",
    "AFGHANISTAN": "AFG", "ZIMBABWE": "ZIM", "IRELAND": "IRE",
    "SCOTLAND": "SCO", "NETHERLANDS": "NED", "NAMIBIA": "NAM",
    "CANADA": "CAN", "OMAN": "OMA", "NEPAL": "NEP",
    "UNITEDARABEMIRATES": "UAE", "PAPUANEWGUINEA": "PNG",
    "HONGKONG": "HK", "UGANDA": "UGA", "UNITEDSTATESOFAMERICA": "USA",
    "ITALY": "ITA",
}

def _team_aliases(team: str) -> set:
    if not team or not str(team).strip():
        return set()
    upper = str(team).upper().strip()
    compact = "".join(ch for ch in upper if ch.isalnum())
    aliases = {upper, compact}
    for country_name, code in COUNTRY_CODE_MAP.items():
        if country_name in compact or compact == code:
            aliases.add(code)
    return aliases

def _teams_match(left: str, right: str) -> bool:
    la, ra = _team_aliases(left), _team_aliases(right)
    return bool(la and ra and la & ra)

def repair_market_probs(df: pd.DataFrame) -> pd.DataFrame:
    """Derive market_batting_team_prob from market_fav_prob + market_fav_team."""
    needs_repair = (
        df['market_fav_prob'].notna()
        & df['market_fav_team'].notna()
        & df['market_batting_team_prob'].isna()
    )
    repaired = 0
    for idx in df.index[needs_repair]:
        fav_team = df.at[idx, 'market_fav_team']
        fav_prob = df.at[idx, 'market_fav_prob']
        bat_team = df.at[idx, 'batting_team']
        bowl_team = df.at[idx, 'bowling_team']
        if _teams_match(fav_team, bat_team):
            df.at[idx, 'market_batting_team_prob'] = fav_prob
            df.at[idx, 'market_bowling_team_prob'] = 1.0 - fav_prob
            repaired += 1
        elif _teams_match(fav_team, bowl_team):
            df.at[idx, 'market_batting_team_prob'] = 1.0 - fav_prob
            df.at[idx, 'market_bowling_team_prob'] = fav_prob
            repaired += 1
    return df

# ──────────────────────────────────────────────────────────────────────────────
# Actual match outcomes
# ──────────────────────────────────────────────────────────────────────────────
MATCH_RESULTS = {
    "sa-vs-uae-34th-match-t20-world-cup-2026": {
        "date": "Feb 18", "team_a": "SA", "team_b": "UAE",
        "winner": "SA", "result": "SA won by 6 wkts",
        "winning_code": "SA",
    },
    "nam-vs-pak-35th-match-t20-world-cup-2026": {
        "date": "Feb 18", "team_a": "PAK", "team_b": "NAM",
        "winner": "Pakistan", "result": "PAK won by 102 runs",
        "winning_code": "PAK",
    },
    "ind-vs-ned-36th-match-t20-world-cup-2026": {
        "date": "Feb 18", "team_a": "IND", "team_b": "NED",
        "winner": "India", "result": "IND won by 17 runs",
        "winning_code": "IND",
    },
    "ita-vs-wi-37th-match-t20-world-cup-2026": {
        "date": "Feb 19", "team_a": "WI", "team_b": "ITA",
        "winner": "West Indies", "result": "WI won by 42 runs",
        "winning_code": "WI",
    },
    "sl-vs-zim-38th-match-t20-world-cup-2026": {
        "date": "Feb 19", "team_a": "SL", "team_b": "ZIM",
        "winner": "Zimbabwe", "result": "ZIM won by 6 wkts",
        "winning_code": "ZIM",
    },
    "afg-vs-can-39th-match-t20-world-cup-2026": {
        "date": "Feb 19", "team_a": "AFG", "team_b": "CAN",
        "winner": "Afghanistan", "result": "AFG won by 82 runs",
        "winning_code": "AFG",
    },
    "aus-vs-oma-40th-match-t20-world-cup-2026": {
        "date": "Feb 20", "team_a": "AUS", "team_b": "OMA",
        "winner": "Australia", "result": "AUS won by 9 wkts",
        "winning_code": "AUS",
    },
    "nz-vs-pak-41st-t20i--super-8-group-2nd-match-t20-world-cup-2026": {
        "date": "Feb 21", "team_a": "NZ", "team_b": "PAK",
        "winner": "Abandoned", "result": "Abandoned (rain)",
        "winning_code": None,
    },
    "eng-vs-sl-42nd-t20i--super-8-group-2nd-match-t20-world-cup-2026": {
        "date": "Feb 22", "team_a": "ENG", "team_b": "SL",
        "winner": "England", "result": "ENG won by 51 runs",
        "winning_code": "ENG",
    },
    "ind-vs-sa-43rd-t20i--super-8-group-1st-match-t20-world-cup-2026": {
        "date": "Feb 22", "team_a": "IND", "team_b": "SA",
        "winner": "South Africa", "result": "SA won by 76 runs",
        "winning_code": "SA",
    },
}


def analyze_match(match_id: str, match_info: dict) -> list | None:
    """Analyze a single match: model vs market vs actual outcome."""
    match_file = Path(f"data/match_states/t20i/{match_id}.parquet")
    if not match_file.exists():
        return None

    df = pd.read_parquet(match_file)
    df = repair_market_probs(df)

    with_market = df[df['market_batting_team_prob'].notna()].copy()
    if len(with_market) < 2:
        return None

    winning_code = match_info["winning_code"]
    if winning_code is None:  # abandoned
        return None

    results_by_innings = []
    for inn in [1, 2]:
        inn_df = with_market[with_market['innings'] == inn]
        if len(inn_df) == 0:
            continue

        batting = inn_df.iloc[0]['batting_team']
        bowling = inn_df.iloc[0]['bowling_team']
        batting_won = _teams_match(winning_code, batting)

        actual = 1.0 if batting_won else 0.0
        eps = 1e-15  # clamp for log

        model_probs = inn_df['model_final_prob'].values
        market_probs = inn_df['market_batting_team_prob'].values

        # Brier score: mean (prob - actual)^2
        model_brier = np.mean((model_probs - actual) ** 2)
        market_brier = np.mean((market_probs - actual) ** 2)

        # MAE
        model_mae = np.mean(np.abs(model_probs - actual))
        market_mae = np.mean(np.abs(market_probs - actual))

        # LogLoss: -mean[ y*log(p) + (1-y)*log(1-p) ]
        def _logloss(probs, y):
            p = np.clip(probs, eps, 1 - eps)
            return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))

        model_logloss = _logloss(model_probs, actual)
        market_logloss = _logloss(market_probs, actual)

        # ECE (10-bin): |avg_prob - actual| weighted by bin count
        def _ece(probs, y, n_bins=10):
            bin_edges = np.linspace(0, 1, n_bins + 1)
            ece_val = 0.0
            for lo, hi in zip(bin_edges[:-1], bin_edges[1:]):
                mask = (probs >= lo) & (probs < hi)
                if mask.sum() == 0:
                    continue
                avg_prob = probs[mask].mean()
                avg_outcome = y  # single outcome for entire innings
                ece_val += mask.sum() * abs(avg_prob - avg_outcome)
            return ece_val / len(probs)

        model_ece = _ece(model_probs, actual)
        market_ece = _ece(market_probs, actual)

        # Last-ball error
        last = inn_df.iloc[-1]
        model_last_err = abs(last['model_final_prob'] - actual)
        market_last_err = abs(last['market_batting_team_prob'] - actual)

        # Direction at last ball
        model_correct_dir = (last['model_final_prob'] > 0.5) == batting_won
        market_correct_dir = (last['market_batting_team_prob'] > 0.5) == batting_won

        results_by_innings.append({
            'match_id': match_id,
            'date': match_info['date'],
            'result': match_info['result'],
            'innings': inn,
            'batting': batting,
            'bowling': bowling,
            'batting_won': batting_won,
            'n_balls': len(inn_df),
            'model_brier': model_brier,
            'market_brier': market_brier,
            'model_mae': model_mae,
            'market_mae': market_mae,
            'model_logloss': model_logloss,
            'market_logloss': market_logloss,
            'model_ece': model_ece,
            'market_ece': market_ece,
            'model_last_err': model_last_err,
            'market_last_err': market_last_err,
            'model_correct_dir': model_correct_dir,
            'market_correct_dir': market_correct_dir,
            'model_first': inn_df.iloc[0]['model_final_prob'],
            'market_first': inn_df.iloc[0]['market_batting_team_prob'],
            'model_last': last['model_final_prob'],
            'market_last': last['market_batting_team_prob'],
        })

    return results_by_innings


def main():
    print("\n" + "=" * 100)
    print("T20 WORLD CUP 2026: MODEL vs MARKET vs ACTUAL OUTCOME")
    print("All recorded matches with repaired market probabilities")
    print("=" * 100)

    all_innings = []
    for match_id, info in MATCH_RESULTS.items():
        rows = analyze_match(match_id, info)
        if rows:
            all_innings.extend(rows)

    if not all_innings:
        print("No matches with sufficient data found.")
        return

    df = pd.DataFrame(all_innings)

    # ── Per-match summary ──────────────────────────────────────────────────
    print(f"\n{'Match':<28} {'Inn':>3} {'Bat':>4} {'Won':>4} {'Balls':>5}"
          f"  {'Mod Brier':>9} {'Mkt Brier':>9}"
          f"  {'Mod LL':>8} {'Mkt LL':>8}"
          f"  {'Mod ECE':>8} {'Mkt ECE':>8}"
          f"  {'Last Mod':>8} {'Last Mkt':>8}")
    print("-" * 155)

    for _, r in df.iterrows():
        short_name = r['match_id'].split('-t20-world')[0].split('-t20i')[0][:26]
        won_mark = "W" if r['batting_won'] else "L"
        print(f"{short_name:<28} {r['innings']:>3} {r['batting']:>4} {won_mark:>4} {r['n_balls']:>5}"
              f"  {r['model_brier']:>9.4f} {r['market_brier']:>9.4f}"
              f"  {r['model_logloss']:>8.4f} {r['market_logloss']:>8.4f}"
              f"  {r['model_ece']:>8.4f} {r['market_ece']:>8.4f}"
              f"  {r['model_last']:>8.1%} {r['market_last']:>8.1%}")

    # ── Aggregated metrics ─────────────────────────────────────────────────
    print("\n" + "=" * 100)
    print("AGGREGATE METRICS")
    print("=" * 100)

    # Weight by n_balls for overall Brier / MAE
    total_balls = df['n_balls'].sum()
    model_brier_overall = np.average(df['model_brier'], weights=df['n_balls'])
    market_brier_overall = np.average(df['market_brier'], weights=df['n_balls'])
    model_mae_overall = np.average(df['model_mae'], weights=df['n_balls'])
    market_mae_overall = np.average(df['market_mae'], weights=df['n_balls'])

    # LogLoss and ECE weighted
    model_ll_overall = np.average(df['model_logloss'], weights=df['n_balls'])
    market_ll_overall = np.average(df['market_logloss'], weights=df['n_balls'])
    model_ece_overall = np.average(df['model_ece'], weights=df['n_balls'])
    market_ece_overall = np.average(df['market_ece'], weights=df['n_balls'])

    print(f"\n  Total ball states analysed: {total_balls}")
    print(f"  Matches (innings-level):   {len(df)}")
    print(f"\n  {'Metric':<25} {'Model':>10} {'Market':>10} {'Winner':>10}")
    print(f"  {'-'*55}")
    print(f"  {'Brier Score (wtd)':<25} {model_brier_overall:>10.4f} {market_brier_overall:>10.4f}"
          f" {'Model' if model_brier_overall < market_brier_overall else 'Market':>10}")
    print(f"  {'LogLoss (wtd)':<25} {model_ll_overall:>10.4f} {market_ll_overall:>10.4f}"
          f" {'Model' if model_ll_overall < market_ll_overall else 'Market':>10}")
    print(f"  {'ECE (wtd)':<25} {model_ece_overall:>10.4f} {market_ece_overall:>10.4f}"
          f" {'Model' if model_ece_overall < market_ece_overall else 'Market':>10}")
    print(f"  {'MAE (wtd)':<25} {model_mae_overall:>10.4f} {market_mae_overall:>10.4f}"
          f" {'Model' if model_mae_overall < market_mae_overall else 'Market':>10}")

    # Direction accuracy
    model_dir_pct = df['model_correct_dir'].mean()
    market_dir_pct = df['market_correct_dir'].mean()
    print(f"  {'Direction accuracy':<25} {model_dir_pct:>10.1%} {market_dir_pct:>10.1%}"
          f" {'Model' if model_dir_pct > market_dir_pct else 'Market':>10}")

    # Last-ball error
    avg_model_last = df['model_last_err'].mean()
    avg_market_last = df['market_last_err'].mean()
    print(f"  {'Last-ball MAE':<25} {avg_model_last:>10.4f} {avg_market_last:>10.4f}"
          f" {'Model' if avg_model_last < avg_market_last else 'Market':>10}")

    # Per-innings winner count
    model_wins_brier = (df['model_brier'] < df['market_brier']).sum()
    market_wins_brier = (df['model_brier'] > df['market_brier']).sum()
    model_wins_ll = (df['model_logloss'] < df['market_logloss']).sum()
    market_wins_ll = (df['model_logloss'] > df['market_logloss']).sum()
    model_wins_ece = (df['model_ece'] < df['market_ece']).sum()
    market_wins_ece = (df['model_ece'] > df['market_ece']).sum()
    print(f"\n  Innings-level head-to-head:")
    print(f"    Brier:   Model {model_wins_brier} – Market {market_wins_brier}")
    print(f"    LogLoss: Model {model_wins_ll} – Market {market_wins_ll}")
    print(f"    ECE:     Model {model_wins_ece} – Market {market_wins_ece}")

    # ── Key observations ───────────────────────────────────────────────────
    df['brier_diff'] = df['model_brier'] - df['market_brier']
    best_for_model = df.loc[df['brier_diff'].idxmin()]
    worst_for_model = df.loc[df['brier_diff'].idxmax()]

    print(f"\n  Best model innings:  {best_for_model['batting']} Inn{int(best_for_model['innings'])} "
          f"({best_for_model['match_id'].split('-t20-world')[0].split('-t20i')[0]}) "
          f"Brier diff {best_for_model['brier_diff']:+.4f}")
    print(f"  Worst model innings: {worst_for_model['batting']} Inn{int(worst_for_model['innings'])} "
          f"({worst_for_model['match_id'].split('-t20-world')[0].split('-t20i')[0]}) "
          f"Brier diff {worst_for_model['brier_diff']:+.4f}")


if __name__ == "__main__":
    main()
