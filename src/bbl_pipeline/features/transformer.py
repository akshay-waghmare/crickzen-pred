from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
import pandas as pd
from typing import List

class BBLFeatureTransformer(BaseEstimator, TransformerMixin):
    """
    Scikit-learn compatible transformer for BBL match data.
    Handles column selection, imputation, and encoding.
    """
    def __init__(self, numeric_features: List[str], categorical_features: List[str]):
        self.numeric_features = numeric_features
        self.categorical_features = categorical_features
        
        self.pipeline = ColumnTransformer(
            transformers=[
                ('num', Pipeline([
                    ('imputer', SimpleImputer(strategy='mean')), # Or median
                    ('scaler', StandardScaler())
                ]), numeric_features),
                ('cat', Pipeline([
                    ('imputer', SimpleImputer(strategy='constant', fill_value='missing')),
                    ('encoder', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
                ]), categorical_features)
            ],
            remainder='drop' # Drop other columns
        )

    def fit(self, X, y=None):
        self.pipeline.fit(X, y)
        return self

    def transform(self, X):
        return self.pipeline.transform(X)

    def get_feature_names_out(self):
        return self.pipeline.get_feature_names_out()
