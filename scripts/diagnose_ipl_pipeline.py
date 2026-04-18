#!/usr/bin/env python
"""
IPL Pipeline Diagnostic Script
===============================
Reproducible health checks for the IPL prediction pipeline.

Checks:
  1. IPL calibrator exists and is temperature scaling
  2. Match state recordings exist and data completeness
  3. Calibration chain columns (which are null)
  4. Market data columns (which are null)
  5. Team alias matching simulation for IPL franchises
  6. Launcher config for --record-states

Usage:
    python scripts/diagnose_ipl_pipeline.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"

results: list[tuple[str, str, str]] = []  # (check_name, status, detail)


def check(name: str, ok: bool, detail: str = ""):
    status = PASS if ok else FAIL
    results.append((name, status, detail))
    print(f"  {status}  {name}" + (f" - {detail}" if detail else ""))


def warn(name: str, detail: str = ""):
    results.append((name, WARN, detail))
    print(f"  {WARN}  {name}" + (f" - {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# 1. IPL Calibrator
# ---------------------------------------------------------------------------
def check_ipl_calibrator():
    print("\n" + "=" * 60)
    print("1. IPL CALIBRATOR")
    print("=" * 60)

    cal_dir = PROJECT_ROOT / "models" / "t20_male_v2" / "league_calibrators" / "ipl"
    check("Calibrator directory exists", cal_dir.exists(), str(cal_dir))

    pkl_path = cal_dir / "league_calibrator.pkl"
    check("league_calibrator.pkl exists", pkl_path.exists())

    metrics_path = cal_dir / "calibration_metrics.json"
    check("calibration_metrics.json exists", metrics_path.exists())

    if metrics_path.exists():
        with open(metrics_path) as f:
            metrics = json.load(f)
        method = metrics.get("method", "unknown")
        check("Method is temperature scaling", method == "temperature", f"method={method}")
        samples = metrics.get("overall", {}).get("samples", 0)
        check("Sufficient training samples", samples > 10000, f"samples={samples:,}")
        brier_raw = metrics.get("overall", {}).get("brier_raw", 0)
        brier_cal = metrics.get("overall", {}).get("brier_calibrated", 0)
        improvement = (brier_raw - brier_cal) / brier_raw * 100 if brier_raw else 0
        check(
            "Calibration improves Brier",
            brier_cal <= brier_raw,
            f"raw={brier_raw:.4f} → cal={brier_cal:.4f} ({improvement:+.2f}%)",
        )
        fitted = metrics.get("fitted_at", "unknown")
        print(f"       Fitted at: {fitted}")

    if pkl_path.exists():
        try:
            import joblib
            cal = joblib.load(pkl_path)
            cal_method = cal.get("method", "unknown")
            check("PKL method matches JSON", cal_method == "temperature", f"pkl method={cal_method}")
            calibrators = cal.get("calibrators", {})
            check("Has innings_1 calibrator", "innings_1" in calibrators)
            check("Has innings_2 calibrator", "innings_2" in calibrators)
            for key, scaler in calibrators.items():
                if hasattr(scaler, "temperature"):
                    print(f"       {key} temperature T = {scaler.temperature:.4f}")
        except Exception as e:
            check("Load league_calibrator.pkl", False, str(e))


# ---------------------------------------------------------------------------
# 2. Match State Recordings
# ---------------------------------------------------------------------------
def check_match_states():
    print("\n" + "=" * 60)
    print("2. MATCH STATE RECORDINGS")
    print("=" * 60)

    states_dir = PROJECT_ROOT / "data" / "match_states" / "ipl"
    check("States directory exists", states_dir.exists(), str(states_dir))

    if not states_dir.exists():
        return

    parquet_files = list(states_dir.glob("*.parquet"))
    check("Has parquet files", len(parquet_files) > 0, f"{len(parquet_files)} files")

    if not parquet_files:
        return

    try:
        import pandas as pd
    except ImportError:
        warn("pandas not available — skipping data inspection")
        return

    for f in parquet_files:
        if f.name == "match_metadata.parquet":
            continue
        df = pd.read_parquet(f)
        print(f"\n  --- {f.name}: {len(df)} rows, {len(df.columns)} cols ---")

        # 3. Calibration chain
        cal_cols = [
            "model_raw_prob",
            "model_calibrated_combined",
            "model_calibrated_innings",
            "model_calibrated_phase",
            "model_calibrated_per_over",
            "model_league_calibrated",
            "model_final_prob",
        ]
        print("\n  Calibration chain:")
        for c in cal_cols:
            if c in df.columns:
                nn = df[c].notna().sum()
                pct = nn / len(df) * 100
                ok = nn > 0
                status = PASS if ok else FAIL
                print(f"    {status} {c}: {nn}/{len(df)} ({pct:.0f}%)")
            else:
                print(f"    {FAIL} {c}: COLUMN MISSING")

        # 4. Market data
        market_cols = [
            "market_fav_team",
            "market_back_odds",
            "market_lay_odds",
            "market_fav_prob",
            "market_batting_team_prob",
            "market_bowling_team_prob",
            "deviation",
            "deviation_abs",
            "deviation_bucket",
            "deviation_direction",
        ]
        print("\n  Market data:")
        for c in market_cols:
            if c in df.columns:
                nn = df[c].notna().sum()
                pct = nn / len(df) * 100
                ok = nn > 0
                status = PASS if ok else FAIL
                print(f"    {status} {c}: {nn}/{len(df)} ({pct:.0f}%)")

        # Team info
        if "batting_team" in df.columns:
            bt = df["batting_team"].unique().tolist()
            print(f"\n  batting_team values: {bt}")
        if "bowling_team" in df.columns:
            blt = df["bowling_team"].unique().tolist()
            print(f"  bowling_team values: {blt}")
            empty_bowl = df["bowling_team"].isin(["", None]).sum() + df["bowling_team"].isna().sum()
            check("bowling_team populated", empty_bowl == 0, f"{empty_bowl}/{len(df)} empty/null")
        if "market_fav_team" in df.columns:
            mft = df["market_fav_team"].unique().tolist()
            print(f"  market_fav_team values: {mft}")


# ---------------------------------------------------------------------------
# 5. Team Alias Matching Simulation
# ---------------------------------------------------------------------------
def check_team_aliases():
    print("\n" + "=" * 60)
    print("3. TEAM ALIAS MATCHING (IPL Franchises)")
    print("=" * 60)

    try:
        from bbl_pipeline.inference.match_state_logger import MatchStateLogger
        logger = MatchStateLogger.__new__(MatchStateLogger)
        logger.log = type("FakeLog", (), {"warning": lambda *a, **k: None})()
    except Exception as e:
        warn("Cannot import MatchStateLogger", str(e))
        return

    ipl_franchises = {
        "MI": "Mumbai Indians",
        "CSK": "Chennai Super Kings",
        "RCB": "Royal Challengers Bengaluru",
        "DC": "Delhi Capitals",
        "KKR": "Kolkata Knight Riders",
        "PBKS": "Punjab Kings",
        "RR": "Rajasthan Royals",
        "SRH": "Sunrisers Hyderabad",
        "GT": "Gujarat Titans",
        "LSG": "Lucknow Super Giants",
    }

    for code, full_name in ipl_franchises.items():
        aliases_code = logger._team_aliases(code)
        aliases_full = logger._team_aliases(full_name)
        matched = bool(aliases_code and aliases_full and aliases_code.intersection(aliases_full))
        check(
            f"{code} <-> {full_name}",
            matched,
            f"code_aliases={sorted(aliases_code)[:3]}, name_aliases={sorted(aliases_full)[:3]}"
            + (" -> MATCH" if matched else " -> NO OVERLAP"),
        )


# ---------------------------------------------------------------------------
# 6. Predictor league_calibrated attribute
# ---------------------------------------------------------------------------
def check_predictor_attribute():
    print("\n" + "=" * 60)
    print("4. PREDICTOR last_league_calibrated ATTRIBUTE")
    print("=" * 60)

    predictor_path = PROJECT_ROOT / "src" / "bbl_pipeline" / "inference" / "predictor.py"
    if not predictor_path.exists():
        check("predictor.py exists", False)
        return

    content = predictor_path.read_text(encoding="utf-8")
    has_attr = "last_league_calibrated" in content
    check(
        "predictor.py sets last_league_calibrated",
        has_attr and "self.last_league_calibrated" in content,
        "Attribute is set after league calibration" if has_attr else "MISSING - logger reads None",
    )


# ---------------------------------------------------------------------------
# 7. Launcher config
# ---------------------------------------------------------------------------
def check_launcher():
    print("\n" + "=" * 60)
    print("5. LAUNCHER CONFIG")
    print("=" * 60)

    launcher_path = PROJECT_ROOT / "scripts" / "launcher.py"
    check("launcher.py exists", launcher_path.exists())
    if not launcher_path.exists():
        return

    content = launcher_path.read_text(encoding="utf-8")
    has_ipl = '"IPL"' in content or "'IPL'" in content
    check("IPL config present", has_ipl)

    has_record = "record_var" in content or "--record-states" in content
    check("--record-states support", has_record)

    is_conditional = "record_var.get()" in content
    if is_conditional:
        warn(
            "--record-states is conditional on GUI checkbox",
            "User must manually enable recording - consider making it default",
        )


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def print_summary():
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passes = sum(1 for _, s, _ in results if s == PASS)
    fails = sum(1 for _, s, _ in results if s == FAIL)
    warns = sum(1 for _, s, _ in results if s == WARN)
    total = len(results)
    print(f"  {PASS}: {passes}/{total}")
    print(f"  {FAIL}: {fails}/{total}")
    print(f"  {WARN}: {warns}/{total}")

    if fails:
        print(f"\n  FAILED CHECKS:")
        for name, status, detail in results:
            if status == FAIL:
                print(f"    • {name}: {detail}")


if __name__ == "__main__":
    print("IPL Pipeline Diagnostic Report")
    print(f"Project root: {PROJECT_ROOT}")
    check_ipl_calibrator()
    check_match_states()
    check_team_aliases()
    check_predictor_attribute()
    check_launcher()
    print_summary()
