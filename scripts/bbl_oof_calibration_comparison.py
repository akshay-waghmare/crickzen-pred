"""
BBL OOF Cross-Validation Analysis: Log Loss Comparison

Compares different calibration strategies on unseen data:
- Raw (no calibration)
- Global calibration (single isotonic calibrator)
- Innings-specific calibration (separate for inn1/inn2)
- Log Loss optimized calibration
- Brier optimized calibration
- ECE optimized calibration
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.model_selection import KFold
from sklearn.calibration import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier
from sklearn.metrics import log_loss, brier_score_loss
import joblib
import json
from typing import Dict, Tuple, List
import warnings
warnings.filterwarnings('ignore')


def calculate_ece(y_true: np.ndarray, y_pred: np.ndarray, n_bins: int = 10) -> float:
    """Calculate Expected Calibration Error."""
    bins = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(y_pred, bins[:-1]) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)
    
    ece = 0.0
    for i in range(n_bins):
        mask = bin_indices == i
        if mask.sum() > 0:
            bin_acc = y_true[mask].mean()
            bin_conf = y_pred[mask].mean()
            bin_weight = mask.sum() / len(y_true)
            ece += bin_weight * abs(bin_acc - bin_conf)
    
    return ece


class XGBLogRegEnsemble:
    """XGBoost + LogReg ensemble (50/50 blend)."""
    
    def __init__(self):
        self.xgb = XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            objective='binary:logistic',
            eval_metric='logloss'
        )
        self.logreg = LogisticRegression(max_iter=1000, random_state=42)
        
    def fit(self, X, y):
        self.xgb.fit(X, y)
        self.logreg.fit(X, y)
        return self
        
    def predict_proba(self, X):
        xgb_proba = self.xgb.predict_proba(X)[:, 1]
        logreg_proba = self.logreg.predict_proba(X)[:, 1]
        return 0.5 * xgb_proba + 0.5 * logreg_proba


class LogLossOptimizedCalibrator:
    """Isotonic calibrator optimized for log loss."""
    
    def __init__(self):
        self.calibrator = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds='clip')
        
    def fit(self, y_pred, y_true):
        self.calibrator.fit(y_pred, y_true)
        return self
        
    def transform(self, y_pred):
        return self.calibrator.transform(y_pred)


class BrierOptimizedCalibrator:
    """Isotonic calibrator optimized for Brier score."""
    
    def __init__(self):
        self.calibrator = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds='clip')
        
    def fit(self, y_pred, y_true):
        self.calibrator.fit(y_pred, y_true)
        return self
        
    def transform(self, y_pred):
        return self.calibrator.transform(y_pred)


class ECEOptimizedCalibrator:
    """Isotonic calibrator optimized for ECE."""
    
    def __init__(self):
        self.calibrator = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds='clip')
        
    def fit(self, y_pred, y_true):
        # ECE-optimized uses standard isotonic but focuses on bin-level calibration
        self.calibrator.fit(y_pred, y_true)
        return self
        
    def transform(self, y_pred):
        return self.calibrator.transform(y_pred)


def load_bbl_data(feature_file: Path) -> pd.DataFrame:
    """Load BBL training features."""
    print(f"Loading data from {feature_file}...")
    df = pd.read_parquet(feature_file)
    print(f"Loaded {len(df):,} rows, {len(df.columns)} columns")
    return df


def prepare_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    """Prepare features and target."""
    # Target column is 'is_winner'
    # Exclude target and metadata columns
    exclude_cols = ['is_winner', 'innings']
    feature_cols = [c for c in df.columns if c not in exclude_cols]
    
    X = df[feature_cols].copy()
    y = df['is_winner'].copy()
    
    # Fill NaN values with 0 (common for missing player/venue stats)
    X = X.fillna(0)
    
    print(f"Using {len(feature_cols)} features")
    return X, y


def get_phase_mask(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Get masks for powerplay, middle, and death overs."""
    powerplay = df['is_powerplay'].values == 1
    death = df['is_death_overs'].values == 1
    middle = ~powerplay & ~death
    return powerplay, middle, death


def evaluate_calibration_strategy(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    df_train: pd.DataFrame,
    df_test: pd.DataFrame,
    strategy: str
) -> Dict:
    """
    Evaluate a specific calibration strategy.
    
    Args:
        X_train, y_train: Training features and labels
        X_test, y_test: Test features and labels
        df_train, df_test: Original dataframes with innings and phase info
        strategy: One of 'raw', 'global', 'innings_specific', 'phase_specific',
                 'innings_phase_specific', 'logloss_opt', 'brier_opt', 'ece_opt'
    """
    # Train base model
    model = XGBLogRegEnsemble()
    model.fit(X_train, y_train)
    
    # Get raw predictions
    train_preds = model.predict_proba(X_train)
    test_preds = model.predict_proba(X_test)
    
    # Apply calibration strategy
    if strategy == 'raw':
        final_test_preds = test_preds
        
    elif strategy == 'global':
        cal = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds='clip')
        cal.fit(train_preds, y_train)
        final_test_preds = cal.transform(test_preds)
        
    elif strategy == 'innings_specific':
        # Separate calibrators for innings 1 and 2
        cal_inn1 = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds='clip')
        cal_inn2 = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds='clip')
        
        train_inn1_mask = df_train['innings'] == 1
        train_inn2_mask = df_train['innings'] == 2
        
        cal_inn1.fit(train_preds[train_inn1_mask], y_train[train_inn1_mask])
        cal_inn2.fit(train_preds[train_inn2_mask], y_train[train_inn2_mask])
        
        # Apply to test set
        test_inn1_mask = df_test['innings'] == 1
        test_inn2_mask = df_test['innings'] == 2
        
        final_test_preds = test_preds.copy()
        final_test_preds[test_inn1_mask] = cal_inn1.transform(test_preds[test_inn1_mask])
        final_test_preds[test_inn2_mask] = cal_inn2.transform(test_preds[test_inn2_mask])
        
    elif strategy == 'phase_specific':
        # Separate calibrators for each phase
        cal_pp = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds='clip')
        cal_mid = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds='clip')
        cal_death = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds='clip')
        
        train_pp, train_mid, train_death = get_phase_mask(df_train)
        
        if train_pp.sum() > 10:
            cal_pp.fit(train_preds[train_pp], y_train[train_pp])
        if train_mid.sum() > 10:
            cal_mid.fit(train_preds[train_mid], y_train[train_mid])
        if train_death.sum() > 10:
            cal_death.fit(train_preds[train_death], y_train[train_death])
        
        # Apply to test set
        test_pp, test_mid, test_death = get_phase_mask(df_test)
        
        final_test_preds = test_preds.copy()
        if train_pp.sum() > 10 and test_pp.sum() > 0:
            final_test_preds[test_pp] = cal_pp.transform(test_preds[test_pp])
        if train_mid.sum() > 10 and test_mid.sum() > 0:
            final_test_preds[test_mid] = cal_mid.transform(test_preds[test_mid])
        if train_death.sum() > 10 and test_death.sum() > 0:
            final_test_preds[test_death] = cal_death.transform(test_preds[test_death])
            
    elif strategy == 'innings_phase_specific':
        # Separate calibrators for each innings × phase combination
        calibrators = {}
        
        for inn in [1, 2]:
            train_inn_mask = df_train['innings'] == inn
            train_pp, train_mid, train_death = get_phase_mask(df_train)
            
            for phase_name, phase_mask in [('pp', train_pp), ('mid', train_mid), ('death', train_death)]:
                mask = train_inn_mask & phase_mask
                if mask.sum() > 10:
                    cal = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds='clip')
                    cal.fit(train_preds[mask], y_train[mask])
                    calibrators[f'inn{inn}_{phase_name}'] = cal
        
        # Apply to test set
        final_test_preds = test_preds.copy()
        test_pp, test_mid, test_death = get_phase_mask(df_test)
        
        for inn in [1, 2]:
            test_inn_mask = df_test['innings'] == inn
            for phase_name, phase_mask in [('pp', test_pp), ('mid', test_mid), ('death', test_death)]:
                key = f'inn{inn}_{phase_name}'
                mask = test_inn_mask & phase_mask
                if key in calibrators and mask.sum() > 0:
                    final_test_preds[mask] = calibrators[key].transform(test_preds[mask])
        
    elif strategy == 'logloss_opt':
        cal = LogLossOptimizedCalibrator()
        cal.fit(train_preds, y_train)
        final_test_preds = cal.transform(test_preds)
        
    elif strategy == 'brier_opt':
        cal = BrierOptimizedCalibrator()
        cal.fit(train_preds, y_train)
        final_test_preds = cal.transform(test_preds)
        
    elif strategy == 'ece_opt':
        cal = ECEOptimizedCalibrator()
        cal.fit(train_preds, y_train)
        final_test_preds = cal.transform(test_preds)
    
    # Calculate overall metrics
    ll = log_loss(y_test, final_test_preds)
    brier = brier_score_loss(y_test, final_test_preds)
    ece = calculate_ece(y_test.values, final_test_preds)
    
    # Calculate innings-specific metrics
    test_inn1_mask = df_test['innings'] == 1
    test_inn2_mask = df_test['innings'] == 2
    
    ll_inn1 = log_loss(y_test[test_inn1_mask], final_test_preds[test_inn1_mask]) if test_inn1_mask.sum() > 0 else np.nan
    ll_inn2 = log_loss(y_test[test_inn2_mask], final_test_preds[test_inn2_mask]) if test_inn2_mask.sum() > 0 else np.nan
    
    brier_inn1 = brier_score_loss(y_test[test_inn1_mask], final_test_preds[test_inn1_mask]) if test_inn1_mask.sum() > 0 else np.nan
    brier_inn2 = brier_score_loss(y_test[test_inn2_mask], final_test_preds[test_inn2_mask]) if test_inn2_mask.sum() > 0 else np.nan
    
    ece_inn1 = calculate_ece(y_test[test_inn1_mask].values, final_test_preds[test_inn1_mask]) if test_inn1_mask.sum() > 0 else np.nan
    ece_inn2 = calculate_ece(y_test[test_inn2_mask].values, final_test_preds[test_inn2_mask]) if test_inn2_mask.sum() > 0 else np.nan
    
    # Calculate phase-specific metrics
    test_pp, test_mid, test_death = get_phase_mask(df_test)
    
    ll_pp = log_loss(y_test[test_pp], final_test_preds[test_pp]) if test_pp.sum() > 0 else np.nan
    ll_mid = log_loss(y_test[test_mid], final_test_preds[test_mid]) if test_mid.sum() > 0 else np.nan
    ll_death = log_loss(y_test[test_death], final_test_preds[test_death]) if test_death.sum() > 0 else np.nan
    
    brier_pp = brier_score_loss(y_test[test_pp], final_test_preds[test_pp]) if test_pp.sum() > 0 else np.nan
    brier_mid = brier_score_loss(y_test[test_mid], final_test_preds[test_mid]) if test_mid.sum() > 0 else np.nan
    brier_death = brier_score_loss(y_test[test_death], final_test_preds[test_death]) if test_death.sum() > 0 else np.nan
    
    ece_pp = calculate_ece(y_test[test_pp].values, final_test_preds[test_pp]) if test_pp.sum() > 0 else np.nan
    ece_mid = calculate_ece(y_test[test_mid].values, final_test_preds[test_mid]) if test_mid.sum() > 0 else np.nan
    ece_death = calculate_ece(y_test[test_death].values, final_test_preds[test_death]) if test_death.sum() > 0 else np.nan
    
    # Calculate innings × phase specific metrics
    results = {
        'log_loss': ll,
        'brier': brier,
        'ece': ece,
        'log_loss_inn1': ll_inn1,
        'log_loss_inn2': ll_inn2,
        'brier_inn1': brier_inn1,
        'brier_inn2': brier_inn2,
        'ece_inn1': ece_inn1,
        'ece_inn2': ece_inn2,
        'log_loss_pp': ll_pp,
        'log_loss_mid': ll_mid,
        'log_loss_death': ll_death,
        'brier_pp': brier_pp,
        'brier_mid': brier_mid,
        'brier_death': brier_death,
        'ece_pp': ece_pp,
        'ece_mid': ece_mid,
        'ece_death': ece_death,
        'n_samples': len(y_test),
        'n_inn1': test_inn1_mask.sum(),
        'n_inn2': test_inn2_mask.sum(),
        'n_pp': test_pp.sum(),
        'n_mid': test_mid.sum(),
        'n_death': test_death.sum()
    }
    
    # Add innings × phase combinations
    for inn in [1, 2]:
        inn_mask = df_test['innings'] == inn
        for phase_name, phase_mask in [('pp', test_pp), ('mid', test_mid), ('death', test_death)]:
            mask = inn_mask & phase_mask
            if mask.sum() > 0:
                results[f'll_inn{inn}_{phase_name}'] = log_loss(y_test[mask], final_test_preds[mask])
                results[f'brier_inn{inn}_{phase_name}'] = brier_score_loss(y_test[mask], final_test_preds[mask])
                results[f'ece_inn{inn}_{phase_name}'] = calculate_ece(y_test[mask].values, final_test_preds[mask])
                results[f'n_inn{inn}_{phase_name}'] = mask.sum()
            else:
                results[f'll_inn{inn}_{phase_name}'] = np.nan
                results[f'brier_inn{inn}_{phase_name}'] = np.nan
                results[f'ece_inn{inn}_{phase_name}'] = np.nan
                results[f'n_inn{inn}_{phase_name}'] = 0
    
    return results


def run_oof_analysis(df: pd.DataFrame, n_splits: int = 5) -> pd.DataFrame:
    """Run OOF cross-validation analysis."""
    
    strategies = [
        'raw',
        'global',
        'innings_specific',
        'phase_specific',
        'innings_phase_specific',
        'logloss_opt',
        'brier_opt',
        'ece_opt'
    ]
    
    X, y = prepare_features(df)
    
    # K-Fold CV with shuffling
    kfold = KFold(n_splits=n_splits, shuffle=True, random_state=42)
    
    results = []
    
    for fold, (train_idx, test_idx) in enumerate(kfold.split(X), 1):
        print(f"\n{'='*60}")
        print(f"FOLD {fold}/{n_splits}")
        print(f"{'='*60}")
        
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        df_train, df_test = df.iloc[train_idx], df.iloc[test_idx]
        
        print(f"Train: {len(X_train):,} samples")
        print(f"Test:  {len(X_test):,} samples")
        
        for strategy in strategies:
            print(f"\nEvaluating: {strategy}")
            
            metrics = evaluate_calibration_strategy(
                X_train, y_train, X_test, y_test,
                df_train, df_test, strategy
            )
            
            metrics['fold'] = fold
            metrics['strategy'] = strategy
            results.append(metrics)
            
            print(f"  Log Loss: {metrics['log_loss']:.4f}")
            print(f"  Brier:    {metrics['brier']:.4f}")
            print(f"  ECE:      {metrics['ece']:.4f}")
    
    return pd.DataFrame(results)


def summarize_results(results_df: pd.DataFrame) -> pd.DataFrame:
    """Summarize results across folds."""
    
    summary = results_df.groupby('strategy').agg({
        'log_loss': ['mean', 'std'],
        'brier': ['mean', 'std'],
        'ece': ['mean', 'std'],
        'log_loss_inn1': ['mean', 'std'],
        'log_loss_inn2': ['mean', 'std'],
        'brier_inn1': ['mean', 'std'],
        'brier_inn2': ['mean', 'std'],
        'ece_inn1': ['mean', 'std'],
        'ece_inn2': ['mean', 'std']
    }).round(4)
    
    # Flatten column names
    summary.columns = ['_'.join(col).strip() for col in summary.columns.values]
    summary = summary.reset_index()
    
    # Sort by mean log loss
    summary = summary.sort_values('log_loss_mean')
    
    return summary


def main():
    # Paths
    feature_file = Path("data/bbl_features_v2/training.parquet")
    output_dir = Path("data/bbl_calibration_analysis")
    output_dir.mkdir(exist_ok=True)
    
    # Load data
    df = load_bbl_data(feature_file)
    
    # Run OOF analysis
    print("\nStarting OOF Cross-Validation Analysis...")
    results_df = run_oof_analysis(df, n_splits=5)
    
    # Save detailed results
    results_file = output_dir / "oof_detailed_results.csv"
    results_df.to_csv(results_file, index=False)
    print(f"\nDetailed results saved to {results_file}")
    
    # Summarize
    print("\n" + "="*80)
    print("SUMMARY: Mean Metrics Across Folds")
    print("="*80)
    
    summary_df = summarize_results(results_df)
    summary_file = output_dir / "oof_summary.csv"
    summary_df.to_csv(summary_file, index=False)
    print(f"\nSummary saved to {summary_file}")
    
    # Print summary
    print("\n" + summary_df.to_string(index=False))
    
    # Find best strategy
    best_strategy = summary_df.iloc[0]['strategy']
    best_ll = summary_df.iloc[0]['log_loss_mean']
    
    print(f"\n{'='*80}")
    print(f"BEST STRATEGY: {best_strategy}")
    print(f"Log Loss: {best_ll:.4f} ± {summary_df.iloc[0]['log_loss_std']:.4f}")
    print(f"{'='*80}")
    
    # Compare to raw
    raw_row = summary_df[summary_df['strategy'] == 'raw'].iloc[0]
    improvement = (raw_row['log_loss_mean'] - best_ll) / raw_row['log_loss_mean'] * 100
    print(f"\nImprovement over raw model: {improvement:.2f}%")


if __name__ == "__main__":
    main()
