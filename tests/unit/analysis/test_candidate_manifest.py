import json

import pytest

from bbl_pipeline.analysis.candidate_manifest import (
    build_candidate_manifest,
    validate_candidate_manifest,
    write_candidate_manifest,
)


def test_candidate_manifest_fingerprints_and_validates_artifact(tmp_path):
    model_dir = tmp_path / "candidate-v1"
    model_dir.mkdir()
    (model_dir / "champion_model.joblib").write_bytes(b"model-artifact")
    (model_dir / "champion_metadata.json").write_text(
        json.dumps({"base_model_params": {"feature_order": ["a", "b"]}}),
        encoding="utf-8",
    )

    manifest = build_candidate_manifest(
        model_dir,
        candidate_id="candidate-v1",
        source_revision="abc123",
    )
    path = write_candidate_manifest(manifest, tmp_path / "manifest.json")

    assert path.exists()
    assert manifest["model_artifact"]["sha256"]
    assert manifest["feature_order"] == ["a", "b"]
    validated = validate_candidate_manifest(manifest, model_dir)
    assert validated["candidate_id"] == "candidate-v1"
    assert validated["source_revision"] == "abc123"


def test_candidate_manifest_rejects_changed_model(tmp_path):
    model_dir = tmp_path / "candidate-v1"
    model_dir.mkdir()
    model_path = model_dir / "champion_model.joblib"
    model_path.write_bytes(b"before")
    manifest = build_candidate_manifest(
        model_dir,
        candidate_id="candidate-v1",
        feature_order=["required_run_rate"],
    )
    model_path.write_bytes(b"after")

    with pytest.raises(ValueError, match="fingerprint mismatch"):
        validate_candidate_manifest(manifest, model_dir)
