"""
Test calibrator-model compatibility checks.
"""
import pytest
import joblib
import hashlib
import tempfile
from pathlib import Path
from sklearn.isotonic import IsotonicRegression
import numpy as np


def test_calibrator_metadata_structure():
    """Test that calibrator metadata has correct structure."""
    # Create mock calibrator with metadata
    iso = IsotonicRegression()
    iso.fit([0.1, 0.5, 0.9], [0, 1, 1])
    
    features = ['feature_a', 'feature_b', 'feature_c']
    feature_hash = hashlib.md5('_'.join(sorted(features)).encode()).hexdigest()
    
    metadata = {
        'calibrator': iso,
        'features': features,
        'feature_hash': feature_hash,
        'n_features': 3,
    }
    
    # Verify structure
    assert 'calibrator' in metadata
    assert 'features' in metadata
    assert 'feature_hash' in metadata
    assert len(metadata['features']) == 3
    assert metadata['n_features'] == 3
    
    # Verify calibrator works
    cal = metadata['calibrator']
    result = cal.predict([0.5])
    assert 0 <= result[0] <= 1


def test_feature_hash_matching():
    """Test that identical feature lists produce same hash."""
    features_a = ['feat1', 'feat2', 'feat3']
    features_b = ['feat1', 'feat2', 'feat3']
    features_c = ['feat1', 'feat2', 'feat4']  # Different
    
    hash_a = hashlib.md5('_'.join(sorted(features_a)).encode()).hexdigest()
    hash_b = hashlib.md5('_'.join(sorted(features_b)).encode()).hexdigest()
    hash_c = hashlib.md5('_'.join(sorted(features_c)).encode()).hexdigest()
    
    assert hash_a == hash_b  # Same features -> same hash
    assert hash_a != hash_c  # Different features -> different hash


def test_feature_hash_order_invariant():
    """Test that feature order doesn't affect hash (sorted internally)."""
    features_a = ['feat1', 'feat2', 'feat3']
    features_b = ['feat3', 'feat1', 'feat2']  # Different order
    
    hash_a = hashlib.md5('_'.join(sorted(features_a)).encode()).hexdigest()
    hash_b = hashlib.md5('_'.join(sorted(features_b)).encode()).hexdigest()
    
    assert hash_a == hash_b  # Same features (sorted) -> same hash


def test_calibrator_save_load_with_metadata():
    """Test saving and loading calibrator with metadata."""
    iso = IsotonicRegression()
    iso.fit([0.1, 0.3, 0.5, 0.7, 0.9], [0, 0, 1, 1, 1])
    
    features = ['score', 'wickets', 'overs']
    feature_hash = hashlib.md5('_'.join(sorted(features)).encode()).hexdigest()
    
    metadata = {
        'calibrator': iso,
        'features': features,
        'feature_hash': feature_hash,
        'n_features': len(features),
        'created_date': '2025-12-17',
    }
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as f:
        temp_path = Path(f.name)
        joblib.dump(metadata, temp_path)
    
    try:
        # Load back
        loaded = joblib.load(temp_path)
        
        assert isinstance(loaded, dict)
        assert 'calibrator' in loaded
        assert loaded['feature_hash'] == feature_hash
        assert loaded['features'] == features
        
        # Verify calibrator still works
        cal = loaded['calibrator']
        result = cal.predict([0.6])
        assert 0 <= result[0] <= 1
        
    finally:
        temp_path.unlink()  # Clean up


def test_mismatch_detection_logic():
    """Test the logic for detecting feature mismatch."""
    # Calibrator features
    cal_features = ['feat1', 'feat2', 'feat3']
    cal_hash = hashlib.md5('_'.join(sorted(cal_features)).encode()).hexdigest()
    
    # Model features - matching
    model_features_match = ['feat1', 'feat2', 'feat3']
    model_hash_match = hashlib.md5('_'.join(sorted(model_features_match)).encode()).hexdigest()
    
    # Model features - mismatched
    model_features_mismatch = ['feat1', 'feat2', 'feat4']  # feat4 instead of feat3
    model_hash_mismatch = hashlib.md5('_'.join(sorted(model_features_mismatch)).encode()).hexdigest()
    
    # Verify detection logic
    assert cal_hash == model_hash_match  # Should match
    assert cal_hash != model_hash_mismatch  # Should NOT match


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
