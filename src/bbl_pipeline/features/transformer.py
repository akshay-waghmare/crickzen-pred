from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
import pandas as pd
from typing import List, Optional

# Default feature sets for BBL pipeline
# Core features from basic match state
CORE_NUMERIC_FEATURES = [
    'innings', 'over', 'ball', 'current_score', 'wickets_lost',
]

# Player/venue rolling stats features
STATS_FEATURES = [
    'batsman_rolling_avg', 'batsman_rolling_sr',
    'bowler_rolling_econ', 'bowler_rolling_sr',
    'venue_avg_score', 'venue_avg_wickets', 'venue_bat_first_win_rate',
]

# Resource-based hybrid features (cricket domain knowledge)
RESOURCE_FEATURES = [
    'overs_remaining', 'balls_remaining', 'wickets_remaining',
    'resource_pct',  # DLS-style resource percentage
    'current_run_rate', 'required_run_rate', 'run_rate_differential',
    'expected_final_score', 'runs_required',
    'pressure_index', 'resource_win_prob',
]

# Phase indicator features (binary)
PHASE_FEATURES = [
    'is_powerplay', 'is_middle_overs', 'is_death_overs',
]

# All numeric features combined
DEFAULT_NUMERIC_FEATURES = CORE_NUMERIC_FEATURES + STATS_FEATURES + RESOURCE_FEATURES + PHASE_FEATURES

# Default categorical features (for team encoding if used)
DEFAULT_CATEGORICAL_FEATURES = []


class BBLFeatureTransformer(BaseEstimator, TransformerMixin):
    """
    Scikit-learn compatible transformer for BBL match data.
    Handles column selection, imputation, and encoding.
    
    Enhanced to support resource-based hybrid features that combine
    cricket domain knowledge with data-driven learning.
    """
    def __init__(self, 
                 numeric_features: Optional[List[str]] = None, 
                 categorical_features: Optional[List[str]] = None,
                 include_resource_features: bool = True):
        """
        Initialize the feature transformer.
        
        Args:
            numeric_features: List of numeric feature names. If None, uses defaults.
            categorical_features: List of categorical feature names. If None, uses defaults.
            include_resource_features: Whether to include resource-based features (default True).
        """
        if numeric_features is None:
            if include_resource_features:
                self.numeric_features = DEFAULT_NUMERIC_FEATURES
            else:
                self.numeric_features = CORE_NUMERIC_FEATURES + STATS_FEATURES
        else:
            self.numeric_features = numeric_features
            
        if categorical_features is None:
            self.categorical_features = DEFAULT_CATEGORICAL_FEATURES
        else:
            self.categorical_features = categorical_features
        
        self.include_resource_features = include_resource_features
        self._build_pipeline()
    
    def _build_pipeline(self):
        """Build the column transformer pipeline."""
        transformers = [
            ('num', Pipeline([
                ('imputer', SimpleImputer(strategy='mean')),
                ('scaler', StandardScaler())
            ]), self.numeric_features),
        ]
        
        # Only add categorical transformer if we have categorical features
        if self.categorical_features:
            transformers.append(
                ('cat', Pipeline([
                    ('imputer', SimpleImputer(strategy='constant', fill_value='missing')),
                    ('encoder', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
                ]), self.categorical_features)
            )
        
        self.pipeline = ColumnTransformer(
            transformers=transformers,
            remainder='drop'  # Drop other columns
        )

    def fit(self, X, y=None):
        self.pipeline.fit(X, y)
        return self

    def transform(self, X):
        return self.pipeline.transform(X)

    def get_feature_names_out(self):
        return self.pipeline.get_feature_names_out()
    
    def get_feature_list(self) -> List[str]:
        """Return the list of features expected by this transformer."""
        return self.numeric_features + self.categorical_features

