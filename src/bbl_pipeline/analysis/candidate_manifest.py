"""Candidate model registration and artifact fingerprinting.

The manifest is intentionally small and JSON-only.  It identifies the exact
model artifact and metadata used for a shadow window without serialising or
loading model objects into the review ledger.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


def sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Return the SHA-256 digest of one file."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _read_metadata(model_dir: Path) -> dict[str, Any]:
    metadata_path = model_dir / "champion_metadata.json"
    if not metadata_path.exists():
        return {}
    try:
        value = json.loads(metadata_path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def build_candidate_manifest(
    model_dir: str | Path,
    *,
    candidate_id: str,
    league: str | None = None,
    source_revision: str | None = None,
    activated_at: str | None = None,
    feature_order: list[str] | None = None,
) -> dict[str, Any]:
    """Build a manifest for an immutable candidate model directory."""
    root = Path(model_dir).resolve()
    model_path = root / "champion_model.joblib"
    if not model_path.exists():
        raise FileNotFoundError(f"Candidate model not found: {model_path}")

    metadata_path = root / "champion_metadata.json"
    metadata = _read_metadata(root)
    base_params = metadata.get("base_model_params")
    metadata_feature_order = base_params.get("feature_order") if isinstance(base_params, dict) else None
    selected_feature_order = feature_order or (
        metadata_feature_order if isinstance(metadata_feature_order, list) else []
    )
    if not selected_feature_order:
        # Older metadata files often omit feature order even though the
        # persisted estimator exposes it. Registration is the one place where
        # loading the artifact is acceptable; inference remains JSON/manifest
        # driven after registration.
        try:
            import joblib

            estimator = joblib.load(model_path)
            if hasattr(estimator, "feature_names_in_"):
                feature_names = getattr(estimator, "feature_names_in_", None)
                selected_feature_order = list(feature_names) if feature_names is not None else []
            elif hasattr(estimator, "selected_features_"):
                selected_features = getattr(estimator, "selected_features_", None)
                selected_feature_order = list(selected_features) if selected_features is not None else []
            elif isinstance(estimator, dict):
                selected_feature_order = list(estimator.get("features") or [])
        except Exception:
            selected_feature_order = []
    if not selected_feature_order:
        raise ValueError(
            "Candidate feature order is unavailable; pass --feature-order values or add it to champion_metadata.json"
        )
    artifacts = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "candidate_manifest.json":
            continue
        artifacts.append({
            "path": path.relative_to(root).as_posix(),
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        })

    feature_order_payload = json.dumps(selected_feature_order, separators=(",", ":"), ensure_ascii=True)
    return {
        "schema_version": "prediction-candidate-manifest-v1",
        "candidate_id": candidate_id,
        "model_dir": str(root),
        "league": league or "",
        "source_revision": source_revision or "unknown",
        "activated_at": activated_at or datetime.now(timezone.utc).isoformat(),
        "model_artifact": {
            "path": model_path.relative_to(root).as_posix(),
            "sha256": sha256_file(model_path),
        },
        "metadata_artifact": (
            {
                "path": metadata_path.relative_to(root).as_posix(),
                "sha256": sha256_file(metadata_path),
            }
            if metadata_path.exists()
            else None
        ),
        "feature_order": selected_feature_order,
        "feature_order_sha256": hashlib.sha256(feature_order_payload.encode("utf-8")).hexdigest(),
        "artifacts": artifacts,
    }


def write_candidate_manifest(manifest: Mapping[str, Any], output_path: str | Path) -> Path:
    """Write a manifest atomically enough for operator use and return its path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def validate_candidate_manifest(manifest: Mapping[str, Any], model_dir: str | Path) -> dict[str, Any]:
    """Verify the registered model artifact still matches the manifest."""
    root = Path(model_dir).resolve()
    model_path = root / "champion_model.joblib"
    expected = str((manifest.get("model_artifact") or {}).get("sha256") or "")
    actual = sha256_file(model_path) if model_path.exists() else ""
    if not expected or actual != expected:
        raise ValueError(
            f"Candidate artifact fingerprint mismatch for {model_path}: expected {expected or 'missing'}, got {actual or 'missing'}"
        )
    for artifact in manifest.get("artifacts") or []:
        relative_path = str(artifact.get("path") or "")
        expected_artifact = str(artifact.get("sha256") or "")
        artifact_path = root / relative_path
        if not relative_path or not artifact_path.exists() or sha256_file(artifact_path) != expected_artifact:
            raise ValueError(f"Candidate artifact fingerprint mismatch for {artifact_path}")
    return {
        "candidate_id": str(manifest.get("candidate_id") or model_path.parent.name),
        "source_revision": str(manifest.get("source_revision") or "unknown"),
        "feature_order_sha256": str(manifest.get("feature_order_sha256") or ""),
        "model_artifact_sha256": actual,
    }
