"""
Train phase-specific Platt scalers for IPL league calibration.

Key fix: Train on isotonic-CALIBRATED predictions (matching production pipeline),
not raw model predictions (which the old approach used).

Production calibration chain:
  Raw model → Per-over isotonic → Phase isotonic → League calibrator
  
This script simulates steps 1-3, then fits phase×innings Platt scalers
as the league calibrator.

Usage:
    python scripts/train_ipl_phase_calibrators.py
    
    # With cross-validation (recommended):
    python scripts/train_ipl_phase_calibrators.py --cv 5
"""

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.model_selection import StratifiedKFold

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bbl_pipeline.training.league_calibrator import PlattScaler, TemperatureScaler


def get_phase(over_number: int) -> str:
    """Determine phase from over number (1-indexed)."""
    if over_number <= 6:
        return "powerplay"
    elif over_number <= 15:
        return "middle"
    else:
        return "death"


def apply_calibration_chain(raw_probs: np.ndarray, df: pd.DataFrame, 
                             calibrator_data: dict) -> np.ndarray:
    """
    Simulate the production calibration chain:
    raw → per-over isotonic → phase isotonic (fallback) → innings isotonic (fallback)
    """
    per_over_cals = calibrator_data.get('per_over_calibrators', {})
    phase_cals = calibrator_data.get('phase_calibrators', {})
    innings_cals = {
        1: calibrator_data.get('calibrator_innings1'),
        2: calibrator_data.get('calibrator_innings2'),
    }
    
    calibrated = np.copy(raw_probs)
    
    for i in range(len(df)):
        inn = int(df.iloc[i]['innings'])
        over = int(df.iloc[i]['over_number'])
        raw_p = raw_probs[i]
        
        # Priority: per-over > phase > innings (matching predictor.py lines 792-799)
        over_key = f"inn{inn}_over{over}"
        phase = get_phase(over)
        phase_key = f"inn{inn}_{phase}"
        
        if over_key in per_over_cals:
            cal = per_over_cals[over_key]
            calibrated[i] = float(cal.predict([raw_p])[0])
        elif phase_key in phase_cals:
            cal = phase_cals[phase_key]
            calibrated[i] = float(cal.predict([raw_p])[0])
        elif inn in innings_cals and innings_cals[inn] is not None:
            cal = innings_cals[inn]
            calibrated[i] = float(cal.predict([raw_p])[0])
    
    return np.clip(calibrated, 1e-7, 1 - 1e-7)


def fit_phase_platt_calibrators(
    calibrated_probs: np.ndarray,
    y_true: np.ndarray,
    df: pd.DataFrame,
    min_samples: int = 300,
) -> dict:
    """
    Fit Platt scalers per innings×phase (6 total), with innings-level fallback.
    """
    calibrators = {}
    metrics = {}
    
    # Derive phase column
    phases = df['over_number'].apply(get_phase).values
    innings = df['innings'].values
    
    # Fit innings-level as fallback
    for inn in [1, 2]:
        mask = innings == inn
        if mask.sum() >= min_samples:
            scaler = PlattScaler()
            scaler.fit(calibrated_probs[mask], y_true[mask])
            calibrators[f"innings_{inn}"] = scaler
            
            pred = scaler.predict(calibrated_probs[mask])
            metrics[f"innings_{inn}"] = {
                "brier_before": float(brier_score_loss(y_true[mask], calibrated_probs[mask])),
                "brier_after": float(brier_score_loss(y_true[mask], pred)),
                "samples": int(mask.sum()),
            }
            print(f"  innings_{inn}: Brier {metrics[f'innings_{inn}']['brier_before']:.4f} → {metrics[f'innings_{inn}']['brier_after']:.4f} ({mask.sum()} samples)")
    
    # Fit phase×innings
    for inn in [1, 2]:
        for phase in ["powerplay", "middle", "death"]:
            key = f"inn{inn}_{phase}"
            mask = (innings == inn) & (phases == phase)
            n = mask.sum()
            
            if n >= min_samples:
                scaler = PlattScaler()
                scaler.fit(calibrated_probs[mask], y_true[mask])
                calibrators[key] = scaler
                
                pred = scaler.predict(calibrated_probs[mask])
                metrics[key] = {
                    "brier_before": float(brier_score_loss(y_true[mask], calibrated_probs[mask])),
                    "brier_after": float(brier_score_loss(y_true[mask], pred)),
                    "samples": int(n),
                }
                print(f"  {key}: Brier {metrics[key]['brier_before']:.4f} → {metrics[key]['brier_after']:.4f} ({n} samples)")
            else:
                print(f"  {key}: SKIP ({n} < {min_samples} samples, will use innings fallback)")
    
    return calibrators, metrics


def evaluate_oof(
    df: pd.DataFrame,
    model,
    feature_cols: list,
    calibrator_data: dict,
    n_splits: int = 5,
) -> dict:
    """
    Out-of-fold evaluation of phase-specific Platt calibrators.
    """
    print(f"\n{'='*60}")
    print(f"  OOF EVALUATION ({n_splits}-fold CV)")
    print(f"{'='*60}")
    
    y = df['is_winner'].values
    phases = df['over_number'].apply(get_phase).values
    innings = df['innings'].values
    
    # Get raw predictions
    X = df[feature_cols]
    raw_probs = model.predict_proba(X)[:, 1]
    
    # Apply calibration chain (in-sample for simplicity - isotonic was already OOF-trained)
    calibrated = apply_calibration_chain(raw_probs, df, calibrator_data)
    
    oof_preds_old = np.zeros(len(df))  # Current temperature scaling
    oof_preds_new = np.zeros(len(df))  # New phase Platt
    oof_preds_uncal = np.copy(calibrated)  # No league calibration
    
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    
    for fold, (train_idx, val_idx) in enumerate(skf.split(df, y)):
        cal_train = calibrated[train_idx]
        y_train = y[train_idx]
        df_train = df.iloc[train_idx]
        
        # Fit old-style temperature scalers (innings only)
        old_cals = {}
        for inn in [1, 2]:
            mask = innings[train_idx] == inn
            if mask.sum() > 100:
                ts = TemperatureScaler()
                ts.fit(cal_train[mask], y_train[mask])
                old_cals[f"innings_{inn}"] = ts
        
        # Fit new-style phase Platt scalers
        new_cals, _ = fit_phase_platt_calibrators(
            cal_train, y_train, df_train, min_samples=200
        )
        
        # Predict on validation
        for i in val_idx:
            inn = int(innings[i])
            phase = phases[i]
            p = calibrated[i]
            
            # Old: innings temperature
            key = f"innings_{inn}"
            if key in old_cals and hasattr(old_cals[key], 'predict'):
                oof_preds_old[i] = old_cals[key].predict(np.array([p]))[0]
            else:
                oof_preds_old[i] = p
            
            # New: phase Platt (fallback to innings)
            phase_key = f"inn{inn}_{phase}"
            innings_key = f"innings_{inn}"
            if phase_key in new_cals and hasattr(new_cals[phase_key], 'predict'):
                oof_preds_new[i] = new_cals[phase_key].predict(np.array([p]))[0]
            elif innings_key in new_cals and hasattr(new_cals[innings_key], 'predict'):
                oof_preds_new[i] = new_cals[innings_key].predict(np.array([p]))[0]
            else:
                oof_preds_new[i] = p
    
    # Clip
    oof_preds_old = np.clip(oof_preds_old, 1e-7, 1 - 1e-7)
    oof_preds_new = np.clip(oof_preds_new, 1e-7, 1 - 1e-7)
    
    # Results
    results = {}
    for name, preds in [("No league cal", oof_preds_uncal), 
                         ("Temperature (current)", oof_preds_old),
                         ("Phase Platt (new)", oof_preds_new)]:
        brier = brier_score_loss(y, preds)
        ll = log_loss(y, preds)
        results[name] = {"brier": brier, "logloss": ll}
        print(f"\n  {name}:")
        print(f"    Overall Brier: {brier:.4f}  LogLoss: {ll:.4f}")
        
        for inn in [1, 2]:
            mask = innings == inn
            b = brier_score_loss(y[mask], preds[mask])
            print(f"    Inn{inn} Brier: {b:.4f}")
        
        for inn in [1, 2]:
            for phase in ["powerplay", "middle", "death"]:
                mask = (innings == inn) & (phases == phase)
                if mask.sum() > 0:
                    b = brier_score_loss(y[mask], preds[mask])
                    print(f"    Inn{inn}/{phase}: Brier {b:.4f} ({mask.sum()} rows)")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Train phase-specific IPL Platt calibrators")
    parser.add_argument("--cv", type=int, default=0, help="Number of CV folds (0 = no CV)")
    parser.add_argument("--model-dir", default="models/t20_male_v2", help="Global model directory")
    parser.add_argument("--data", default="data/ipl_features_v1/training.parquet", help="Training data")
    parser.add_argument("--dry-run", action="store_true", help="Don't save calibrators")
    args = parser.parse_args()
    
    model_dir = Path(args.model_dir)
    data_path = Path(args.data)
    
    print(f"{'='*60}")
    print(f"  IPL PHASE-SPECIFIC PLATT CALIBRATION")
    print(f"{'='*60}")
    
    # Load model
    model = joblib.load(model_dir / "champion_model.joblib")
    feature_cols = getattr(model, 'selected_features_', None) or getattr(model, 'feature_columns_', None)
    print(f"✅ Model loaded ({len(feature_cols)} features)")
    
    # Load calibrator chain
    cal_data = joblib.load(model_dir / "isotonic_calibrator.pkl")
    print(f"✅ Calibrator chain loaded (type: {cal_data.get('type')})")
    
    # Load data
    df = pd.read_parquet(data_path)
    print(f"✅ Data loaded: {len(df):,} rows")
    
    # Ensure required columns
    assert 'innings' in df.columns, "Missing innings column"
    assert 'is_winner' in df.columns, "Missing is_winner column"
    
    # Derive over_number from overs_remaining if not present
    if 'over_number' not in df.columns:
        total_overs = 20
        balls_bowled = (total_overs * 6 - np.round(df['overs_remaining'].values * 6)).astype(int)
        df['over_number'] = np.clip((balls_bowled - 1) // 6 + 1, 1, total_overs)
        print(f"  Derived over_number from overs_remaining (range: {df['over_number'].min()}-{df['over_number'].max()})")
    
    # Derive phase from existing columns or over_number
    if 'phase' not in df.columns:
        if 'is_middle_overs' in df.columns:
            df['phase'] = 'powerplay'
            df.loc[df['is_middle_overs'] == 1, 'phase'] = 'middle'
            df.loc[df['is_death_overs'] == 1, 'phase'] = 'death'
        else:
            df['phase'] = df['over_number'].apply(get_phase)
    
    y = df['is_winner'].values
    
    # Get raw predictions
    X = df[feature_cols]
    raw_probs = model.predict_proba(X)[:, 1]
    print(f"  Raw model Brier: {brier_score_loss(y, raw_probs):.4f}")
    
    # Apply calibration chain (simulating production pipeline)
    print("\n📊 Applying isotonic calibration chain...")
    calibrated = apply_calibration_chain(raw_probs, df, cal_data)
    print(f"  Calibrated Brier: {brier_score_loss(y, calibrated):.4f}")
    
    # OOF evaluation if requested
    if args.cv > 0:
        oof_results = evaluate_oof(df, model, feature_cols, cal_data, args.cv)
    
    # Fit final calibrators on full data
    print(f"\n{'='*60}")
    print(f"  FITTING FINAL CALIBRATORS (full data)")
    print(f"{'='*60}")
    calibrators, seg_metrics = fit_phase_platt_calibrators(calibrated, y, df)
    
    if args.dry_run:
        print("\n⚠️ Dry run — not saving")
        return
    
    # Save in format compatible with predictor.py
    output_dir = model_dir / "league_calibrators" / "ipl"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Build the pkl structure expected by predictor.py
    league_cal = {
        'method': 'platt',
        'league': 'ipl',
        'innings_specific': True,
        'phase_specific': True,
        'calibrators': calibrators,
        'fitted': True,
        'trained_on': 'calibrated_probs',  # Key: trained on calibrated, not raw
        'created_date': pd.Timestamp.now().isoformat(),
        'segment_metrics': seg_metrics,
        'training_samples': len(df),
    }
    
    # Save
    joblib.dump(league_cal, output_dir / "league_calibrator.pkl")
    
    # Save metrics JSON
    overall_before = float(brier_score_loss(y, calibrated))
    
    # Calculate overall after
    all_pred = np.copy(calibrated)
    phases = df['over_number'].apply(get_phase).values
    innings = df['innings'].values
    for i in range(len(df)):
        inn = int(innings[i])
        phase = phases[i]
        p = calibrated[i]
        phase_key = f"inn{inn}_{phase}"
        innings_key = f"innings_{inn}"
        if phase_key in calibrators and hasattr(calibrators[phase_key], 'predict'):
            all_pred[i] = calibrators[phase_key].predict(np.array([p]))[0]
        elif innings_key in calibrators and hasattr(calibrators[innings_key], 'predict'):
            all_pred[i] = calibrators[innings_key].predict(np.array([p]))[0]
    all_pred = np.clip(all_pred, 1e-7, 1 - 1e-7)
    overall_after = float(brier_score_loss(y, all_pred))
    
    metrics = {
        'league': 'ipl',
        'method': 'platt',
        'phase_specific': True,
        'trained_on': 'calibrated_probs',
        'fitted_at': pd.Timestamp.now().isoformat(),
        'overall': {
            'brier_before_league_cal': overall_before,
            'brier_after_league_cal': overall_after,
            'improvement_pct': (1 - overall_after / overall_before) * 100 if overall_before > 0 else 0,
            'samples': len(df),
        },
        'segments': seg_metrics,
    }
    
    with open(output_dir / "calibration_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    
    print(f"\n✅ Saved to {output_dir}")
    print(f"   Overall Brier: {overall_before:.4f} → {overall_after:.4f} ({(1 - overall_after/overall_before)*100:+.2f}%)")
    print(f"   Method: Phase×Innings Platt (trained on calibrated probs)")


if __name__ == "__main__":
    main()
