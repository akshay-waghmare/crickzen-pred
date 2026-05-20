"""
Empirical horseshoe-style edge analysis for IPL model-vs-market data.

This is a dependency-free approximation of the horseshoe use case:
  - control for market probability with logit(market_p_inn1)
  - estimate one extra signal at a time with match-level bootstraps
  - shrink unstable effects toward zero using a horseshoe-like global/local rule
  - validate each signal with leave-one-match-out Brier delta vs market-only

It is not a replacement for a full Bayesian sampler. It is a fast feature-trust
layer for deciding which segment-specific signals deserve a proper model test.

Usage:
  python scripts/analyze_ipl_horseshoe_edge.py \
    --market data/ipl_market_vs_model_corrected_2026.parquet \
    --features data/ipl_features_v6/training.parquet \
    --output-dir experiments/ipl_horseshoe_edge_v1
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.preprocessing import StandardScaler


EPS = 1e-6
DEFAULT_SIGNALS = [
    "model_edge_full",
    "model_edge_iso",
    "model_edge_raw",
    "resource_edge",
    "target_above_par",
    "inn1_defendability",
    "dls_pressure_index",
    "required_run_rate",
    "current_run_rate",
    "wickets_lost",
    "wickets_remaining",
    "venue_chase_success",
    "team_strength_diff",
    "score_vs_par",
    "rrr_times_wickets",
    "chase_difficulty",
    "batting_team_win_rate",
    "bowling_team_win_rate",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IPL horseshoe-style market edge inference")
    parser.add_argument(
        "--market",
        default="data/ipl_market_vs_model_corrected_2026.parquet",
        help="Market/model comparison parquet with market_p_inn1 and actual_inn1_wins",
    )
    parser.add_argument(
        "--features",
        default="data/ipl_features_v6/training.parquet",
        help="IPL v6 feature parquet with match_id, innings, over, ball",
    )
    parser.add_argument(
        "--output-dir",
        default="experiments/ipl_horseshoe_edge_v1",
        help="Output directory",
    )
    parser.add_argument("--bootstraps", type=int, default=300, help="Match-level bootstrap repeats")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--min-rows",
        type=int,
        default=25,
        help="Minimum rows required for a segment",
    )
    parser.add_argument(
        "--min-matches",
        type=int,
        default=4,
        help="Minimum matches required for a segment",
    )
    return parser.parse_args()


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p.astype(float), EPS, 1.0 - EPS)
    return np.log(p / (1.0 - p))


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


def safe_fit_predict(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_pred: np.ndarray,
    c: float = 100.0,
) -> tuple[np.ndarray, np.ndarray] | tuple[None, None]:
    if len(np.unique(y_train)) < 2:
        return None, None
    try:
        model = LogisticRegression(C=c, max_iter=1000, solver="lbfgs")
        model.fit(X_train, y_train)
        pred = model.predict_proba(X_pred)[:, 1]
        coef = np.r_[model.intercept_, model.coef_[0]]
        return pred, coef
    except Exception:
        return None, None


def prepare_joined_dataset(market_path: Path, features_path: Path) -> pd.DataFrame:
    market = pd.read_parquet(market_path).copy()
    features = pd.read_parquet(features_path).copy()

    required_market = {"cs_match_id", "innings", "over", "market_p_inn1", "actual_inn1_wins"}
    missing = required_market - set(market.columns)
    if missing:
        raise ValueError(f"Market file missing columns: {sorted(missing)}")

    required_features = {"match_id", "innings", "over", "ball", "resource_win_prob"}
    missing = required_features - set(features.columns)
    if missing:
        raise ValueError(f"Feature file missing columns: {sorted(missing)}")

    features["match_id"] = features["match_id"].astype(str)
    market["cs_match_id"] = market["cs_match_id"].astype(str)

    # Market rows are end-of-over states with over=1..20. Feature rows use
    # zero-based over, so use the last ball from over=(market_over - 1).
    features = features.sort_values(["match_id", "innings", "over", "ball"])
    end_over = (
        features.groupby(["match_id", "innings", "over"], as_index=False)
        .tail(1)
        .copy()
    )
    end_over["market_over"] = end_over["over"].astype(int) + 1

    joined = market.merge(
        end_over,
        left_on=["cs_match_id", "innings", "over"],
        right_on=["match_id", "innings", "market_over"],
        how="inner",
        suffixes=("_market", ""),
    )

    joined["y"] = joined["actual_inn1_wins"].astype(int)
    joined["market_logit"] = logit(joined["market_p_inn1"].to_numpy())

    if "full_p_inn1" in joined:
        joined["model_edge_full"] = joined["full_p_inn1"] - joined["market_p_inn1"]
    if "iso_p_inn1" in joined:
        joined["model_edge_iso"] = joined["iso_p_inn1"] - joined["market_p_inn1"]
    if "raw_p_inn1" in joined:
        joined["model_edge_raw"] = joined["raw_p_inn1"] - joined["market_p_inn1"]

    joined["resource_p_inn1"] = np.where(
        joined["innings"].eq(1),
        joined["resource_win_prob"],
        1.0 - joined["resource_win_prob"],
    )
    joined["resource_edge"] = joined["resource_p_inn1"] - joined["market_p_inn1"]
    joined["wickets_remaining"] = 10.0 - joined["wickets_lost"].astype(float)

    if "phase_market" in joined.columns:
        joined["phase"] = joined["phase_market"]
    elif "phase" not in joined.columns:
        joined["phase"] = np.where(
            joined["over"].astype(int) <= 6,
            "powerplay",
            np.where(joined["over"].astype(int) <= 15, "middle", "death"),
        )

    return joined


def segment_masks(df: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        "innings_2_powerplay": df["innings"].eq(2) & df["phase"].eq("powerplay"),
        "innings_2_middle": df["innings"].eq(2) & df["phase"].eq("middle"),
        "innings_2_death": df["innings"].eq(2) & df["phase"].eq("death"),
        "innings_2_overs_4_12": df["innings"].eq(2) & df["over_market"].between(4, 12),
    }


def standardize_signal(values: pd.Series) -> tuple[np.ndarray, float, float]:
    x = pd.to_numeric(values, errors="coerce").astype(float)
    med = float(x.median()) if x.notna().any() else 0.0
    x = x.fillna(med).replace([np.inf, -np.inf], med)
    mu = float(x.mean())
    sd = float(x.std(ddof=0))
    if sd < EPS:
        return np.zeros(len(x)), mu, sd
    return ((x - mu) / sd).to_numpy(), mu, sd


def bootstrap_effects(
    df: pd.DataFrame,
    signal: str,
    n_bootstrap: int,
    rng: np.random.Generator,
) -> dict | None:
    x_signal, x_mean, x_sd = standardize_signal(df[signal])
    if np.nanstd(x_signal) < EPS:
        return None

    y = df["y"].to_numpy().astype(int)
    matches = df["cs_match_id"].astype(str).to_numpy()
    unique_matches = np.unique(matches)
    base = df["market_logit"].to_numpy().reshape(-1, 1)
    X_all = np.column_stack([base, x_signal])

    pred, coef = safe_fit_predict(X_all, y, X_all)
    if pred is None:
        return None

    coefs = []
    signs = []
    for _ in range(n_bootstrap):
        sampled_matches = rng.choice(unique_matches, size=len(unique_matches), replace=True)
        idx_parts = [np.where(matches == m)[0] for m in sampled_matches]
        idx = np.concatenate(idx_parts)
        _, boot_coef = safe_fit_predict(X_all[idx], y[idx], X_all[idx])
        if boot_coef is None:
            continue
        beta = float(boot_coef[-1])
        coefs.append(beta)
        signs.append(np.sign(beta))

    if len(coefs) < max(25, n_bootstrap // 4):
        return None

    coefs_arr = np.array(coefs, dtype=float)
    beta = float(coef[-1])
    se = float(np.std(coefs_arr, ddof=1))
    sign_stability = float(max(np.mean(coefs_arr > 0), np.mean(coefs_arr < 0)))

    return {
        "feature": signal,
        "effect": beta,
        "bootstrap_mean": float(np.mean(coefs_arr)),
        "bootstrap_se": se,
        "ci_low": float(np.quantile(coefs_arr, 0.05)),
        "ci_high": float(np.quantile(coefs_arr, 0.95)),
        "sign_stability": sign_stability,
        "feature_mean": x_mean,
        "feature_std": x_sd,
    }


def apply_horseshoe_shrinkage(effect_df: pd.DataFrame) -> pd.DataFrame:
    if effect_df.empty:
        return effect_df
    out = effect_df.copy()
    eps = 1e-8
    for segment, idx in out.groupby("segment").groups.items():
        part = out.loc[idx]
        z = part["effect"].abs() / (part["bootstrap_se"] + eps)
        # Small global scale means most effects are expected to be noise.
        tau = float(np.median(z) / np.sqrt(len(part) + 1.0))
        tau = max(tau, 0.05)
        local = z.clip(lower=eps)
        keep = (tau * tau * local * local) / (1.0 + tau * tau * local * local)
        out.loc[idx, "global_tau"] = tau
        out.loc[idx, "keep_weight"] = keep
        out.loc[idx, "shrunk_effect"] = part["effect"] * keep
        out.loc[idx, "shrunk_z"] = out.loc[idx, "shrunk_effect"].abs() / (
            part["bootstrap_se"] + eps
        )
        out.loc[idx, "survives_shrinkage"] = (
            (out.loc[idx, "keep_weight"] >= 0.35)
            & (out.loc[idx, "shrunk_z"] >= 1.0)
            & (part["sign_stability"] >= 0.70)
        )
    return out


def loo_metrics_for_signal(df: pd.DataFrame, signal: str) -> dict | None:
    x_signal, _, _ = standardize_signal(df[signal])
    if np.nanstd(x_signal) < EPS:
        return None
    y = df["y"].to_numpy().astype(int)
    matches = df["cs_match_id"].astype(str).to_numpy()
    unique_matches = np.unique(matches)
    if len(unique_matches) < 3:
        return None

    market_logit = df["market_logit"].to_numpy()
    pred_market = np.full(len(df), np.nan)
    pred_signal = np.full(len(df), np.nan)

    for m in unique_matches:
        train = matches != m
        test = matches == m
        if len(np.unique(y[train])) < 2:
            continue
        X_base_train = market_logit[train].reshape(-1, 1)
        X_base_test = market_logit[test].reshape(-1, 1)
        X_sig_train = np.column_stack([market_logit[train], x_signal[train]])
        X_sig_test = np.column_stack([market_logit[test], x_signal[test]])

        p_base, _ = safe_fit_predict(X_base_train, y[train], X_base_test)
        p_sig, _ = safe_fit_predict(X_sig_train, y[train], X_sig_test)
        if p_base is None or p_sig is None:
            continue
        pred_market[test] = p_base
        pred_signal[test] = p_sig

    valid = ~np.isnan(pred_market) & ~np.isnan(pred_signal)
    if valid.sum() < 10:
        return None

    b_base = float(brier_score_loss(y[valid], pred_market[valid]))
    b_sig = float(brier_score_loss(y[valid], pred_signal[valid]))
    ll_base = float(log_loss(y[valid], np.clip(pred_market[valid], EPS, 1 - EPS)))
    ll_sig = float(log_loss(y[valid], np.clip(pred_signal[valid], EPS, 1 - EPS)))
    return {
        "feature": signal,
        "loo_n": int(valid.sum()),
        "loo_market_brier": b_base,
        "loo_signal_brier": b_sig,
        "loo_brier_delta": b_sig - b_base,
        "loo_market_logloss": ll_base,
        "loo_signal_logloss": ll_sig,
        "loo_logloss_delta": ll_sig - ll_base,
    }


def analyze_segment(
    df: pd.DataFrame,
    segment: str,
    signals: list[str],
    n_bootstrap: int,
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, dict]:
    rows = []
    loo_rows = []
    available_signals = [
        s for s in signals if s in df.columns and pd.to_numeric(df[s], errors="coerce").nunique() > 1
    ]
    for signal in available_signals:
        effect = bootstrap_effects(df, signal, n_bootstrap, rng)
        if effect:
            effect["segment"] = segment
            rows.append(effect)
        loo = loo_metrics_for_signal(df, signal)
        if loo:
            loo["segment"] = segment
            loo_rows.append(loo)

    effects = pd.DataFrame(rows)
    if not effects.empty:
        effects = apply_horseshoe_shrinkage(effects)

    loo_df = pd.DataFrame(loo_rows)
    if not effects.empty and not loo_df.empty:
        effects = effects.merge(loo_df, on=["segment", "feature"], how="left")

    y = df["y"].to_numpy().astype(int)
    market = df["market_p_inn1"].to_numpy().astype(float)
    segment_meta = {
        "segment": segment,
        "rows": int(len(df)),
        "matches": int(df["cs_match_id"].nunique()),
        "actual_rate": float(y.mean()),
        "market_mean": float(market.mean()),
        "market_brier": float(brier_score_loss(y, market)),
        "market_logloss": float(log_loss(y, np.clip(market, EPS, 1 - EPS))),
    }
    return effects, segment_meta


def write_report(output_dir: Path, effects: pd.DataFrame, meta: list[dict]) -> None:
    lines = [
        "# IPL Horseshoe-Style Edge Analysis",
        "",
        "Empirical shrinkage test after controlling for market probability.",
        "",
        "Interpretation:",
        "- `effect` is the standardized logistic coefficient after `logit(market_p_inn1)` is included.",
        "- `keep_weight` is the horseshoe-style survival weight; near zero means noisy/shrunk.",
        "- Negative `loo_brier_delta` means the signal improved leave-one-match-out Brier vs market-only.",
        "",
        "## Segment Summary",
        "",
        "| Segment | Rows | Matches | Actual | Market Mean | Market Brier | Market LogLoss |",
        "|---------|------|---------|--------|-------------|--------------|----------------|",
    ]
    for row in meta:
        lines.append(
            f"| {row['segment']} | {row['rows']} | {row['matches']} | "
            f"{row['actual_rate']:.3f} | {row['market_mean']:.3f} | "
            f"{row['market_brier']:.4f} | {row['market_logloss']:.4f} |"
        )

    lines += ["", "## Signals That Survive Shrinkage", ""]
    survived = effects[effects["survives_shrinkage"]].copy() if not effects.empty else pd.DataFrame()
    if survived.empty:
        lines.append("_No signal passed the shrinkage survival gate._")
    else:
        survived = survived.sort_values(
            ["segment", "loo_brier_delta", "keep_weight"],
            ascending=[True, True, False],
        )
        lines += [
            "| Segment | Feature | Effect | Keep | Sign Stable | LOO Brier Delta |",
            "|---------|---------|--------|------|-------------|-----------------|",
        ]
        for row in survived.itertuples():
            loo_delta = getattr(row, "loo_brier_delta", np.nan)
            lines.append(
                f"| {row.segment} | `{row.feature}` | {row.effect:+.4f} | "
                f"{row.keep_weight:.3f} | {row.sign_stability:.2f} | {loo_delta:+.5f} |"
            )

    lines += ["", "## Top Ranked By Segment", ""]
    if effects.empty:
        lines.append("_No effects estimated._")
    else:
        ranked = effects.sort_values(
            ["segment", "survives_shrinkage", "keep_weight", "shrunk_z"],
            ascending=[True, False, False, False],
        )
        for segment in ranked["segment"].drop_duplicates():
            lines += [f"### {segment}", ""]
            part = ranked[ranked["segment"] == segment].head(10)
            lines += [
                "| Feature | Effect | Shrunk | Keep | Sign | LOO ΔBrier |",
                "|---------|--------|--------|------|------|------------|",
            ]
            for row in part.itertuples():
                loo_delta = getattr(row, "loo_brier_delta", np.nan)
                lines.append(
                    f"| `{row.feature}` | {row.effect:+.4f} | {row.shrunk_effect:+.4f} | "
                    f"{row.keep_weight:.3f} | {row.sign_stability:.2f} | {loo_delta:+.5f} |"
                )
            lines.append("")

    (output_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    joined = prepare_joined_dataset(Path(args.market), Path(args.features))
    joined.to_parquet(output_dir / "joined_market_features.parquet", index=False)

    all_effects = []
    meta = []
    masks = segment_masks(joined)
    for segment, mask in masks.items():
        seg_df = joined.loc[mask].copy().reset_index(drop=True)
        n_matches = seg_df["cs_match_id"].nunique()
        if len(seg_df) < args.min_rows or n_matches < args.min_matches:
            print(f"Skipping {segment}: rows={len(seg_df)}, matches={n_matches}")
            continue
        print(f"Analyzing {segment}: rows={len(seg_df)}, matches={n_matches}")
        effects, segment_meta = analyze_segment(
            seg_df, segment, DEFAULT_SIGNALS, args.bootstraps, rng
        )
        if not effects.empty:
            all_effects.append(effects)
        meta.append(segment_meta)

    effects_df = pd.concat(all_effects, ignore_index=True) if all_effects else pd.DataFrame()
    if not effects_df.empty:
        effects_df = effects_df.sort_values(
            ["segment", "survives_shrinkage", "keep_weight", "shrunk_z"],
            ascending=[True, False, False, False],
        )
    effects_df.to_csv(output_dir / "horseshoe_effects.csv", index=False)
    pd.DataFrame(meta).to_csv(output_dir / "segment_summary.csv", index=False)
    (output_dir / "config.json").write_text(json.dumps(vars(args), indent=2), encoding="utf-8")
    write_report(output_dir, effects_df, meta)

    print(f"Artifacts written to: {output_dir}")
    if not effects_df.empty:
        print(effects_df.head(20)[[
            "segment", "feature", "effect", "keep_weight", "survives_shrinkage",
            "loo_brier_delta"
        ]].to_string(index=False))


if __name__ == "__main__":
    main()
