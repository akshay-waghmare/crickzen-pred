import sys
import os
import json
import pickle
import argparse
from pathlib import Path

def get_project_root() -> Path:
    # This script is at .github/extensions/league-enablement/audit_helper.py
    return Path(__file__).resolve().parent.parent.parent.parent

def audit_model(league_code: str, model_dir_str: str = None, feature_store_str: str = None):
    root = get_project_root()
    registry_path = root / "models" / "model_registry.json"
    
    warnings = []
    
    # Resolve model directory
    model_dir = None
    if model_dir_str:
        model_dir = Path(model_dir_str)
        if not model_dir.is_absolute():
            model_dir = root / model_dir
    else:
        # Load from registry
        if registry_path.exists():
            try:
                with open(registry_path, "r", encoding="utf-8") as f:
                    reg = json.load(f)
                active_models = reg.get("active_models", {})
                # Try case insensitive search
                match_key = None
                for k in active_models.keys():
                    if k.lower() == league_code.lower():
                        match_key = k
                        break
                if match_key:
                    model_dir = root / active_models[match_key].get("path", "")
                    print(f"[INFO] Resolved model path from registry: {model_dir}", file=sys.stderr)
            except Exception as e:
                warnings.append(f"Failed to read model_registry.json: {e}")

    if not model_dir or not model_dir.exists():
        return {
            "success": False,
            "error": f"Model directory not found: {model_dir_str or f'registry entry for {league_code}'}",
            "warnings": warnings
        }

    # Resolve feature store directory
    feature_store_dir = None
    if feature_store_str:
        feature_store_dir = Path(feature_store_str)
        if not feature_store_dir.is_absolute():
            feature_store_dir = root / feature_store_dir
    else:
        # Load from registry
        if registry_path.exists():
            try:
                with open(registry_path, "r", encoding="utf-8") as f:
                    reg = json.load(f)
                active_models = reg.get("active_models", {})
                match_key = None
                for k in active_models.keys():
                    if k.lower() == league_code.lower():
                        match_key = k
                        break
                if match_key:
                    fs_path = active_models[match_key].get("feature_store", {}).get("path", "")
                    if fs_path:
                        feature_store_dir = root / fs_path
                        print(f"[INFO] Resolved feature store path from registry: {feature_store_dir}", file=sys.stderr)
            except Exception as e:
                pass

    # Detect model type and configuration
    routing_cfg = None
    routing_cfg_path = model_dir / "routing_config.json"
    is_phase_router = False
    
    if routing_cfg_path.exists():
        try:
            with open(routing_cfg_path, "r", encoding="utf-8") as f:
                routing_cfg = json.load(f)
            if routing_cfg.get("type") == "inn2_phase_router":
                is_phase_router = True
        except Exception as e:
            warnings.append(f"Failed to parse routing_config.json: {e}")

    result = {
        "success": True,
        "league": league_code,
        "model_dir": str(model_dir.relative_to(root) if model_dir.is_relative_to(root) else model_dir),
        "feature_store_dir": str(feature_store_dir.relative_to(root) if feature_store_dir and feature_store_dir.is_relative_to(root) else feature_store_dir) if feature_store_dir else None,
        "is_phase_router": is_phase_router,
        "routing_config": routing_cfg,
        "artifacts": {},
        "metrics": {},
        "warnings": warnings
    }

    # Inspect files
    if is_phase_router:
        result["model_type"] = "phase_router"
        # Verify phase models
        for phase in ["pp", "mid", "death"]:
            p_model = model_dir / f"champion_model_{phase}.joblib"
            result["artifacts"][f"champion_model_{phase}"] = p_model.exists()
            if not p_model.exists():
                warnings.append(f"Missing phase model artifact: champion_model_{phase}.joblib")
                
        # Check phase calibrators
        phase_cals = model_dir / "phase_oof_calibrators.pkl"
        result["artifacts"]["phase_oof_calibrators"] = phase_cals.exists()
        if phase_cals.exists():
            try:
                # Read using pickle or joblib
                import joblib
                try:
                    cals = joblib.load(phase_cals)
                except Exception:
                    with open(phase_cals, "rb") as f:
                        cals = pickle.load(f)
                
                cal_info = {}
                for phase, bundle in cals.items():
                    cal_info[phase] = {
                        "has_phase_iso": "phase_iso" in bundle,
                        "per_over_count": len(bundle.get("per_over", {})),
                        "per_cell_count": len(bundle.get("per_cell", {}))
                    }
                result["calibrator_metadata"] = cal_info
            except Exception as e:
                warnings.append(f"Failed to parse phase_oof_calibrators.pkl: {e}")
        else:
            warnings.append("Missing phase_oof_calibrators.pkl")
            
        # Get metrics from CSV files
        oof_csv = model_dir / "oof_results.csv"
        oos_csv = model_dir / "oos_comparison.csv"
        
        if oof_csv.exists():
            try:
                import pandas as pd
                df = pd.read_csv(oof_csv)
                result["metrics"]["oof_by_phase"] = df.to_dict(orient="records")
            except Exception as e:
                warnings.append(f"Failed to load oof_results.csv: {e}")
                
        if oos_csv.exists():
            try:
                import pandas as pd
                df = pd.read_csv(oos_csv)
                result["metrics"]["oos_by_phase"] = df.to_dict(orient="records")
            except Exception as e:
                warnings.append(f"Failed to load oos_comparison.csv: {e}")
    else:
        result["model_type"] = "single_model"
        champion_model = model_dir / "champion_model.joblib"
        result["artifacts"]["champion_model"] = champion_model.exists()
        if not champion_model.exists():
            warnings.append("Missing base model: champion_model.joblib")
            
        # Check isotonic calibrators
        iso_cal = model_dir / "isotonic_calibrator.pkl"
        result["artifacts"]["isotonic_calibrator"] = iso_cal.exists()
        
        if iso_cal.exists():
            try:
                import joblib
                try:
                    c_data = joblib.load(iso_cal)
                except Exception:
                    with open(iso_cal, "rb") as f:
                        c_data = pickle.load(f)
                
                if isinstance(c_data, dict):
                    result["calibrator_metadata"] = {
                        "type": c_data.get("type", "unknown"),
                        "created_date": c_data.get("created_date"),
                        "n_features": c_data.get("n_features"),
                        "has_phase_calibrators": "phase_calibrators" in c_data,
                        "phase_calibrator_count": len(c_data.get("phase_calibrators", {})),
                        "has_per_over_calibrators": "per_over_calibrators" in c_data,
                        "per_over_calibrator_count": len(c_data.get("per_over_calibrators", {}))
                    }
                    # Gather overall metrics
                    result["metrics"]["oof_overall"] = {
                        "brier_raw": c_data.get("oof_brier_raw"),
                        "brier_calibrated": c_data.get("oof_brier_calibrated"),
                        "ece_raw": c_data.get("oof_ece_raw"),
                        "ece_calibrated": c_data.get("oof_ece_calibrated")
                    }
                    if "innings1_metrics" in c_data:
                        result["metrics"]["innings1"] = c_data["innings1_metrics"]
                    if "innings2_metrics" in c_data:
                        result["metrics"]["innings2"] = c_data["innings2_metrics"]
                else:
                    result["calibrator_metadata"] = {"type": "legacy_bare"}
            except Exception as e:
                warnings.append(f"Failed to parse isotonic_calibrator.pkl: {e}")
                
        # Also check oof_calibration_results.csv
        oof_results_csv = model_dir / "oof_calibration_results.csv"
        if oof_results_csv.exists():
            try:
                import pandas as pd
                df = pd.read_csv(oof_results_csv)
                # Keep only key rows to limit size
                key_df = df[df["method"].isin(["raw", "brier_optimized", "innings_phase", "innings_specific", "combined"])]
                result["metrics"]["oof_calibration_comparison"] = key_df.to_dict(orient="records")
            except Exception as e:
                warnings.append(f"Failed to load oof_calibration_results.csv: {e}")

    # Inspect Feature Store
    if feature_store_dir and feature_store_dir.exists():
        result["feature_store_status"] = "found"
        try:
            fs_files = [p.name for p in feature_store_dir.glob("*.parquet")]
            result["feature_store_files"] = fs_files
            if not fs_files:
                warnings.append(f"Feature store folder is empty or has no parquet files: {feature_store_dir}")
        except Exception as e:
            warnings.append(f"Failed to inspect feature store folder: {e}")
    else:
        result["feature_store_status"] = "not_found"
        warnings.append("No feature store directory resolved or found")

    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", required=True, help="League code (e.g. bbl, ntb, ipl)")
    parser.add_argument("--model-dir", help="Model directory relative path")
    parser.add_argument("--feature-store-dir", help="Feature store directory relative path")
    
    args = parser.parse_args()
    try:
        audit_res = audit_model(args.league, args.model_dir, args.feature_store_dir)
        print(json.dumps(audit_res, indent=2))
    except Exception as e:
        print(json.dumps({"success": False, "error": f"Unhandled exception in audit helper: {e}"}))
        sys.exit(1)
