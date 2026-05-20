"""Test v14 with the window-guarded resource baseline.

This is a reversible experiment. It does not modify production v14 artifacts.

Candidates:
  - v14_original
  - v14_window_resource_replace: replace resource_win_prob with the guarded v2
  - v14_window_resource_delta: keep resource_win_prob and add v2-v1 delta

The guarded v2 resource is OOS-safe:
  - pre-2025 training rows use season-fold OOF context-resource predictions.
  - 2025+ test rows use an adjuster fit only on seasons < 2025.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ipl_resource_baseline_v2_experiment import (  # noqa: E402
    BASE_PROB,
    fit_candidate_oof,
    prepare_data,
)
from ipl_v13_mid_split_common import ordered_unique  # noqa: E402
from ipl_v15_context_resource_experiment import (  # noqa: E402
    build_bucket_report,
    build_delta_summary,
    build_v14_features,
    evaluate_oof_version,
    evaluate_oos_version,
    print_table,
)


OUT_DIR = Path("models/ipl_v14_window_guarded_resource")
WINDOW_RESOURCE = "resource_win_prob_window_guarded"
WINDOW_RESOURCE_DELTA = "resource_delta_window_guarded"


def add_window_guarded_resource(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    """Add OOS-safe guarded resource feature using the context_global adjuster."""

    fit_mask = df["season"] < "2025"
    apply_mask = df["season"] >= "2025"
    context_pred, adjuster = fit_candidate_oof(
        df,
        "context_global",
        fit_mask=fit_mask,
        apply_mask=apply_mask,
    )

    target_below = df["target_below_par_v2"].astype(float).gt(0.0)
    early_first_half = df["over"].between(0, 12)
    late_mid = df["over"].between(13, 15)

    use_context = (early_first_half & ~target_below) | (late_mid & target_below)
    df = df.copy()
    df["resource_context_global_oof"] = context_pred
    df[WINDOW_RESOURCE] = np.where(
        use_context,
        df["resource_context_global_oof"].astype(float),
        df[BASE_PROB].astype(float),
    )
    df[WINDOW_RESOURCE_DELTA] = (
        df[WINDOW_RESOURCE].astype(float) - df[BASE_PROB].astype(float)
    )
    return df, adjuster.coefficients()


def replace_resource_feature(features: list[str]) -> list[str]:
    return ordered_unique([
        WINDOW_RESOURCE if feature == BASE_PROB else feature
        for feature in features
    ])


def build_feature_versions(v14: dict[str, list[str]]) -> dict[str, dict[str, list[str]]]:
    return {
        "v14_original": v14,
        "v14_window_resource_replace": {
            phase: replace_resource_feature(features)
            for phase, features in v14.items()
        },
        "v14_window_resource_delta": {
            phase: ordered_unique(features + [WINDOW_RESOURCE_DELTA])
            for phase, features in v14.items()
        },
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Loading IPL inn2 data and adding window-guarded resource feature...")
    df = prepare_data()
    df, coefficients = add_window_guarded_resource(df)

    v14_features = build_v14_features()
    versions = build_feature_versions(v14_features)

    oos_metrics = []
    oof_metrics = []
    payloads = {}
    for version, features in versions.items():
        print(f"Evaluating {version}...")
        oos, payload = evaluate_oos_version(df, features)
        oos["version"] = version
        oos_metrics.append(oos)
        payloads[version] = payload

        oof = evaluate_oof_version(df[df["season"] < "2025"].copy(), features)
        oof["version"] = version
        oof_metrics.append(oof)

    oos_metrics_df = pd.concat(oos_metrics, ignore_index=True)
    oof_metrics_df = pd.concat(oof_metrics, ignore_index=True)
    bucket_report = build_bucket_report(payloads)
    summary = build_delta_summary(oos_metrics_df, bucket_report)

    oos_metrics_df.to_csv(OUT_DIR / "oos_phase_metrics.csv", index=False)
    oof_metrics_df.to_csv(OUT_DIR / "pre2025_oof_phase_metrics.csv", index=False)
    bucket_report.to_csv(OUT_DIR / "oos_bucket_report.csv", index=False)
    summary.to_csv(OUT_DIR / "candidate_summary.csv", index=False)

    metadata = {
        "resource_feature": WINDOW_RESOURCE,
        "delta_feature": WINDOW_RESOURCE_DELTA,
        "formula": (
            "Use context_global resource in overs 0-12 for non-below-par targets "
            "and overs 13-15 for below-par targets; otherwise use resource_win_prob."
        ),
        "fit_policy": "context_global adjuster fit pre-2025 with season-fold OOF for train rows; 2025+ transformed by pre-2025 adjuster",
        "context_coefficients": coefficients,
        "feature_versions": versions,
    }
    (OUT_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print_table(oos_metrics_df, "OOS phase metrics")
    print_table(bucket_report, "OOS favourite bucket report")
    print_table(summary, "Candidate summary")
    print(f"\nSaved outputs to {OUT_DIR}")


if __name__ == "__main__":
    main()
