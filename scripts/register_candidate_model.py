"""Register an immutable model artifact for a shadow evaluation window."""

from __future__ import annotations

import argparse
from pathlib import Path

from bbl_pipeline.analysis.candidate_manifest import (
    build_candidate_manifest,
    write_candidate_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Register a candidate model artifact")
    parser.add_argument("--model-dir", required=True, help="Directory containing champion_model.joblib")
    parser.add_argument("--candidate-id", required=True, help="Unique candidate id")
    parser.add_argument("--league", default="", help="League/format scope")
    parser.add_argument("--source-revision", default="unknown", help="Git/source revision")
    parser.add_argument("--activated-at", default=None, help="ISO-8601 activation timestamp")
    parser.add_argument(
        "--feature-order",
        action="append",
        default=None,
        help="Model feature name; repeat once per feature when metadata does not include order",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Manifest path (default: <model-dir>/candidate_manifest.json)",
    )
    args = parser.parse_args()
    manifest = build_candidate_manifest(
        args.model_dir,
        candidate_id=args.candidate_id,
        league=args.league,
        source_revision=args.source_revision,
        activated_at=args.activated_at,
        feature_order=args.feature_order,
    )
    output = Path(args.output) if args.output else Path(args.model_dir) / "candidate_manifest.json"
    path = write_candidate_manifest(manifest, output)
    print(f"candidate_id={manifest['candidate_id']}")
    print(f"model_artifact_sha256={manifest['model_artifact']['sha256']}")
    print(f"manifest={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
