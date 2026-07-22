"""CrickZen model selection with format- and gender-aware global fallback."""
from __future__ import annotations
from pathlib import Path
from typing import Mapping

def resolve_model_config(league_key: str, config: Mapping[str, object], project_root: Path) -> dict[str, object]:
    result = dict(config)
    configured = project_root / str(config.get("model_dir", ""))
    is_hundred = "hundred" in str(config.get("league", "")).lower() or "hundred" in league_key.lower()
    if is_hundred:
        hundred_model = project_root / "models" / "hundred_all_v1"
        if not (hundred_model / "champion_model.joblib").exists():
            raise FileNotFoundError("Hundred model is not installed at models/hundred_all_v1")
        result["model_dir"] = "models/hundred_all_v1"
        result["feature_store_dir"] = "data/hundred_all_feature_store_v1"
        result["league"] = "hundred_all"
        result["model_source"] = "hundred_specific"
        result["model_candidate"] = "hundred_all_v1"
        result["fallback_format"] = "hundred"
        result.pop("mc_only", None)
        return result
    is_odi = "odi" in str(config.get("league", "")).lower() or "odi" in league_key.lower()
    if (configured / "champion_model.joblib").exists() and not config.get("prefer_combined_model") and not configured.name.lower().startswith("odi_mc"):
        result["model_source"] = "league_specific"
        return result
    prefix = "odi_all" if is_odi else "t20_all"
    # Candidate artifacts are deliberately opt-in.  A newer file on disk is
    # not a promotion decision: the public runtime must stay on the validated
    # v2 champion unless a controlled experiment explicitly enables it.
    candidates = [
        project_root / "models" / f"{prefix}_v2",
        project_root / "models" / f"{prefix}_v1",
    ]
    if config.get("allow_experimental_candidate"):
        candidates.insert(0, project_root / "models" / f"{prefix}_v3_feature_pruned_candidate")
    selected = next((p for p in candidates if (p / "champion_model.joblib").exists()), None)
    if selected is None:
        raise FileNotFoundError(f"No league model for {league_key} and no combined {prefix} fallback is installed")
    result["model_dir"] = str(selected.relative_to(project_root)).replace("\\", "/")
    version = "v2" if selected.name.endswith("_v2") or "v3_feature_pruned_candidate" in selected.name else "v1"
    result["feature_store_dir"] = f"data/{prefix}_feature_store_{version}"
    result.pop("mc_only", None)
    result["model_source"] = "combined_gender_aware_fallback"
    result["model_candidate"] = selected.name
    result["fallback_format"] = "odi" if is_odi else "t20"
    return result
