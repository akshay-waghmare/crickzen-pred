import joblib
import numpy as np
import pandas as pd


def _safe_select_features(model, X: pd.DataFrame) -> pd.DataFrame:
    if hasattr(model, "feature_names_in_"):
        required = list(model.feature_names_in_)
    elif hasattr(model, "selected_features_") and model.selected_features_ is not None:
        required = list(model.selected_features_)
    else:
        required = list(X.columns)

    X2 = X.copy()
    for col in required:
        if col not in X2.columns:
            X2[col] = 0.0
    return X2[required].fillna(0.0)


def _pick_col(candidates, columns):
    for c in candidates:
        if c in columns:
            return c
    return None


def main():
    model_path = "models/t20i_champion_v2/champion_model.joblib"
    data_path = "data/t20i_features_v1/training.parquet"

    model = joblib.load(model_path)
    df = pd.read_parquet(data_path)

    # Heuristic filters for "early" first-innings states
    # (keep loose; we just want representative powerplay-like states)
    innings_col = _pick_col(["innings", "innings_num", "innings_number"], df.columns)
    over_col = _pick_col(["over", "over_number", "over_num"], df.columns)
    wickets_col = _pick_col(["wickets", "total_wickets", "wickets_down"], df.columns)

    early = df
    if innings_col:
        early = early[early[innings_col] == 1]
    if over_col:
        early = early[early[over_col] <= 4]
    if wickets_col:
        early = early[early[wickets_col] <= 2]

    # Keep numeric features only
    X = early.select_dtypes(include=[np.number]).copy()

    # Drop obvious labels if present
    for target_col in ["y", "label", "won", "win", "result", "outcome", "is_win"]:
        if target_col in X.columns:
            X = X.drop(columns=[target_col])

    if len(X) == 0:
        raise SystemExit("No numeric feature rows found after filtering.")

    # Sample for speed
    X = X.sample(n=min(5000, len(X)), random_state=42)
    X_aligned = _safe_select_features(model, X)

    base_prob = model.predict_proba(X_aligned)[:, 1]

    # Identify the feature(s) most likely driving early boundary jumps
    proj_col = _pick_col(
        [
            "projected_score",
            "proj_score",
            "innings_projected_score",
            "expected_score",
            "expected_innings_score",
        ],
        X_aligned.columns,
    )
    crr_col = _pick_col(
        [
            "current_run_rate",
            "crr",
            "innings_crr",
        ],
        X_aligned.columns,
    )

    print("Model:", type(model))
    if hasattr(model, "selected_features_"):
        print("Selected features:", len(model.selected_features_))

    # Global importance (whatever the ensemble exposes)
    if hasattr(model, "get_feature_importance"):
        imp = model.get_feature_importance().sort_values("importance", ascending=False)
        print("\nTop 15 feature importances:")
        print(imp.head(15).to_string(index=False))

    print("\nEarly-overs sample rows:", len(X_aligned))
    print("Available columns of interest:", {"projected_score": proj_col, "current_run_rate": crr_col})

    def summarize_delta(delta: np.ndarray, name: str):
        print(
            f"{name}: mean={delta.mean()*100:+.2f}pp  "
            f"p50={np.median(delta)*100:+.2f}pp  p90={np.quantile(delta,0.9)*100:+.2f}pp  "
            f"p99={np.quantile(delta,0.99)*100:+.2f}pp"
        )

    # Counterfactual sensitivity checks
    # 1) +10 to projected score (roughly what a single early 6 can do via projection)
    if proj_col:
        Xp = X_aligned.copy()
        Xp[proj_col] = Xp[proj_col] + 10.0
        prob_p = model.predict_proba(Xp)[:, 1]
        summarize_delta(prob_p - base_prob, "ΔP(projected_score +10)")

        Xp2 = X_aligned.copy()
        Xp2[proj_col] = Xp2[proj_col] + 20.0
        prob_p2 = model.predict_proba(Xp2)[:, 1]
        summarize_delta(prob_p2 - base_prob, "ΔP(projected_score +20)")

    # 2) +1.0 to CRR (a boundary early can shift CRR a lot)
    if crr_col:
        Xc = X_aligned.copy()
        Xc[crr_col] = Xc[crr_col] + 1.0
        prob_c = model.predict_proba(Xc)[:, 1]
        summarize_delta(prob_c - base_prob, "ΔP(CRR +1.0)")

        Xc2 = X_aligned.copy()
        Xc2[crr_col] = Xc2[crr_col] + 2.0
        prob_c2 = model.predict_proba(Xc2)[:, 1]
        summarize_delta(prob_c2 - base_prob, "ΔP(CRR +2.0)")

    # 3) If there are explicit boundary flags, test them
    boundary_flag_cols = [c for c in X_aligned.columns if any(k in c.lower() for k in ["is_six", "is_four", "boundary"])]
    boundary_flag_cols = boundary_flag_cols[:5]
    if boundary_flag_cols:
        print("\nBoundary-like flag columns:", boundary_flag_cols)
        for c in boundary_flag_cols:
            Xb = X_aligned.copy()
            # flip / set to 1
            Xb[c] = 1.0
            prob_b = model.predict_proba(Xb)[:, 1]
            summarize_delta(prob_b - base_prob, f"ΔP({c}=1)")


if __name__ == "__main__":
    main()
