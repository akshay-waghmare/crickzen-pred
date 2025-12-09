import numpy as np
from sklearn.model_selection import TimeSeriesSplit
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


