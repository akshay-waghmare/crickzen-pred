from pathlib import Path
from dashboard.app.model_resolution import resolve_model_config

def _install(root: Path, relative: str) -> None:
    path = root / relative
    path.mkdir(parents=True)
    (path / "champion_model.joblib").write_bytes(b"model")

def test_specific_model_wins(tmp_path):
    _install(tmp_path, "models/ipl_v1")
    resolved = resolve_model_config("IPL", {"league": "ipl", "model_dir": "models/ipl_v1"}, tmp_path)
    assert resolved["model_source"] == "league_specific"

def test_odi_falls_back_to_combined_model(tmp_path):
    _install(tmp_path, "models/odi_all_v2")
    resolved = resolve_model_config("ODI Women", {"league": "odi_female", "model_dir": "models/odi_mc_v1", "mc_only": True}, tmp_path)
    assert resolved["model_dir"] == "models/odi_all_v2"
    assert resolved["model_source"] == "combined_gender_aware_fallback"
    assert "mc_only" not in resolved


def test_odi_candidate_does_not_override_the_validated_v2_champion(tmp_path):
    _install(tmp_path, "models/odi_all_v2")
    _install(tmp_path, "models/odi_all_v3_feature_pruned_candidate")

    resolved = resolve_model_config("ODI Male", {"league": "odi_male", "model_dir": "models/odi_mc_v1"}, tmp_path)

    assert resolved["model_dir"] == "models/odi_all_v2"

def test_unknown_t20_league_uses_combined_model(tmp_path):
    _install(tmp_path, "models/t20_all_v1")
    resolved = resolve_model_config("Shpageeza", {"league": "shpageeza", "model_dir": "models/missing"}, tmp_path)
    assert resolved["model_dir"] == "models/t20_all_v1"

def test_configured_league_presets_use_combined_t20_model(tmp_path):
    _install(tmp_path, "models/t20_all_v2")
    resolved = resolve_model_config("NTB", {"league": "ntb", "model_dir": "models/ntb_v1_phase", "prefer_combined_model": True}, tmp_path)
    assert resolved["model_dir"] == "models/t20_all_v2"
    assert resolved["model_source"] == "combined_gender_aware_fallback"


def test_hundred_uses_the_dedicated_model_and_feature_store(tmp_path):
    _install(tmp_path, "models/hundred_all_v1")
    resolved = resolve_model_config(
        "Hundred",
        {
            "league": "hundred_all",
            "model_dir": "models/hundred_all_v1",
            "feature_store_dir": "data/hundred_all_feature_store_v1",
        },
        tmp_path,
    )
    assert resolved["model_dir"] == "models/hundred_all_v1"
    assert resolved["feature_store_dir"] == "data/hundred_all_feature_store_v1"
    assert resolved["league"] == "hundred_all"
    assert resolved["model_source"] == "hundred_specific"
