import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import brier_score_loss, log_loss
from typing import Iterator, Tuple

class TimeSeriesCalibrationSplit:
    """
    Time-series splitter that yields Train, Calibration, and Test indices.
    Ensures strict temporal ordering: Train < Calibration < Test.
    """
    def __init__(self, n_splits: int = 5, test_size: int | float = 0.1, calibration_size: int | float = 0.1):
        self.n_splits = n_splits
        self.test_size = test_size
        self.calibration_size = calibration_size

    def split(self, X, y=None, groups=None) -> Iterator[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
        """
        Yields (train_idx, calib_idx, test_idx).
        """
        n_samples = len(X)
        indices = np.arange(n_samples)
        
        # Use TimeSeriesSplit logic but adapted for 3 splits
        # We can use TimeSeriesSplit to get Train/Test, then split Test into Calib/Test?
        # Or split Train into Train/Calib?
        
        # Let's implement a rolling window approach manually to ensure control
        
        # Determine fold sizes
        # If sizes are floats, they are fractions of the total data? Or fractions of the fold?
        # Usually TimeSeriesSplit expands the training set.
        
        # Simple approach:
        # Divide data into n_splits + 1 blocks?
        # No, let's stick to a standard expanding window.
        
        # Let's assume test_size and calibration_size are number of samples if int, or fraction if float.
        # For simplicity, let's assume they are fixed number of samples (e.g. one season) or we calculate them.
        
        # If we don't have seasons, we just use indices.
        
        fold_size = n_samples // (self.n_splits + 1) # Rough chunk size
        
        # We want the last 'n_splits' chunks to be test sets.
        # And the chunk before test to be calibration?
        
        # Let's use a simpler logic:
        # Test set is always the "future".
        # Calibration set is "recent past".
        # Train set is "distant past".
        
        tscv = TimeSeriesSplit(n_splits=self.n_splits)
        
        for train_val_idx, test_idx in tscv.split(X):
            # train_val_idx is the "past". test_idx is the "future" (Test set).
            
            # Now split train_val_idx into Train and Calibration.
            # We take the last portion of train_val_idx as Calibration.
            
            n_train_val = len(train_val_idx)
            
            if isinstance(self.calibration_size, float):
                n_calib = int(n_train_val * self.calibration_size)
            else:
                n_calib = self.calibration_size
                
            if n_calib >= n_train_val:
                raise ValueError("Calibration size is too large for the training set.")
            
            train_idx = train_val_idx[:-n_calib]
            calib_idx = train_val_idx[-n_calib:]
            
            yield train_idx, calib_idx, test_idx

def expected_calibration_error(y_true, y_prob, n_bins=10):
    """
    Calculates Expected Calibration Error (ECE).
    """
    from sklearn.calibration import calibration_curve
    
    prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=n_bins, strategy='uniform')
    
    # We need the number of samples in each bin to calculate weighted average
    # calibration_curve doesn't return counts directly.
    # We can implement it manually or use a library.
    # Simple manual implementation:
    
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    bin_lowers = bin_boundaries[:-1]
    bin_uppers = bin_boundaries[1:]
    
    ece = 0.0
    for bin_lower, bin_upper in zip(bin_lowers, bin_uppers):
        # In bin
        in_bin = (y_prob > bin_lower) & (y_prob <= bin_upper)
        prop_in_bin = np.mean(in_bin)
        
        if prop_in_bin > 0:
            accuracy_in_bin = np.mean(y_true[in_bin])
            avg_prob_in_bin = np.mean(y_prob[in_bin])
            ece += np.abs(avg_prob_in_bin - accuracy_in_bin) * prop_in_bin
            
    return ece


def compute_rolling_drift(
    df: pd.DataFrame,
    match_col: str,
    window: int = 50,
    overall_brier: float = None,
    drift_threshold: float = 0.02,
) -> pd.DataFrame:
    """
    T019: Compute per-match Brier/LogLoss then smooth with a rolling window.

    Args:
        df: DataFrame with columns _y_true, _y_prob, and match_col.
        match_col: Column identifying each match (match_date or match_id).
        window: Number of matches in the rolling window.
        overall_brier: Overall holdout Brier. Used for drift alert threshold.
        drift_threshold: Log WARNING when rolling_brier - overall_brier > threshold.

    Returns:
        DataFrame with columns: match_key, rolling_brier_<window>, rolling_logloss_<window>.
    """
    import structlog
    _logger = structlog.get_logger()

    records = []
    for match_key, grp in df.groupby(match_col, sort=True):
        yt = grp["_y_true"].values
        yp = grp["_y_prob"].values
        if len(yt) < 2:
            continue
        records.append({
            "match_key": str(match_key),
            "brier": brier_score_loss(yt, yp),
            "logloss": log_loss(yt, yp),
            "n_balls": len(yt),
        })

    if not records:
        return pd.DataFrame(columns=["match_key", f"rolling_brier_{window}", f"rolling_logloss_{window}"])

    per_match = pd.DataFrame(records)
    rb_col = f"rolling_brier_{window}"
    rl_col = f"rolling_logloss_{window}"
    per_match[rb_col] = per_match["brier"].rolling(window, min_periods=1).mean()
    per_match[rl_col] = per_match["logloss"].rolling(window, min_periods=1).mean()

    if overall_brier is not None:
        worst = per_match[rb_col].max()
        if worst - overall_brier > drift_threshold:
            _logger.warning(
                "Model drift detected",
                rolling_brier_peak=round(worst, 4),
                overall_brier=round(overall_brier, 4),
                degradation=round(worst - overall_brier, 4),
                threshold=drift_threshold,
                action="Consider retraining model",
            )

    return per_match[["match_key", rb_col, rl_col, "n_balls"]]


def compute_segment_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    T016: Brier/LogLoss/ECE breakdown by innings, phase, wickets_bucket, rrr_bucket.

    Expects columns in df: _y_true, _y_prob, and optionally:
        innings, over, wickets_lost, required_run_rate, current_run_rate
    Returns DataFrame with one row per non-empty segment.
    """
    def _phase(over):
        if over is None:
            return "unknown"
        o = float(over)
        if o < 6:
            return "powerplay"
        elif o < 15:
            return "middle"
        else:
            return "death"

    def _wickets_bucket(w):
        if w is None:
            return "unknown"
        w = int(w)
        if w <= 2:
            return "0-2"
        elif w <= 5:
            return "3-5"
        else:
            return "6-10"

    def _rrr_bucket(rrr):
        if rrr is None or rrr != rrr:  # NaN check
            return "N/A"
        r = float(rrr)
        if r < 7:
            return "<7"
        elif r <= 12:
            return "7-12"
        else:
            return ">12"

    def _metrics(sub):
        yt = sub["_y_true"].values
        yp = sub["_y_prob"].values
        if len(yt) < 5:
            return None
        return {
            "brier": round(brier_score_loss(yt, yp), 4),
            "logloss": round(log_loss(yt, yp), 4),
            "ece": round(expected_calibration_error(yt, yp), 4),
            "n": len(yt),
        }

    work = df.copy()
    work["_innings"] = work.get("innings", pd.Series(["?"] * len(work), index=work.index))
    work["_phase"] = work.get("over", pd.Series([None] * len(work), index=work.index)).map(_phase)
    work["_wb"] = work.get("wickets_lost", pd.Series([None] * len(work), index=work.index)).map(_wickets_bucket)
    rrr_col = "required_run_rate" if "required_run_rate" in work.columns else None
    work["_rrr"] = work[rrr_col].map(_rrr_bucket) if rrr_col else "N/A"

    rows = []
    for innings, ig in work.groupby("_innings"):
        m = _metrics(ig)
        if m:
            rows.append({"innings": innings, "phase": "all", "wickets_bucket": "all", "rrr_bucket": "all", **m})
        for phase, pg in ig.groupby("_phase"):
            m = _metrics(pg)
            if m:
                rows.append({"innings": innings, "phase": phase, "wickets_bucket": "all", "rrr_bucket": "all", **m})
            for wb, wg in pg.groupby("_wb"):
                m = _metrics(wg)
                if m:
                    rows.append({"innings": innings, "phase": phase, "wickets_bucket": wb, "rrr_bucket": "all", **m})
        if str(innings) == "2":
            for rrr_b, rg in ig.groupby("_rrr"):
                m = _metrics(rg)
                if m:
                    rows.append({"innings": innings, "phase": "all", "wickets_bucket": "all", "rrr_bucket": rrr_b, **m})

    return pd.DataFrame(rows, columns=["innings", "phase", "wickets_bucket", "rrr_bucket", "brier", "logloss", "ece", "n"])