"""Verify the updated trainer configuration."""
from src.bbl_pipeline.training.trainer import Trainer

t = Trainer()
xgb = t.models['xgboost']
print("Trainer config updated successfully!")
print(f"XGBoost config:")
print(f"  n_estimators={xgb.n_estimators}")
print(f"  max_depth={xgb.max_depth}")
print(f"  learning_rate={xgb.learning_rate}")
print(f"  min_child_weight={xgb.min_child_weight}")
print(f"  reg_alpha={xgb.reg_alpha}")
print(f"  reg_lambda={xgb.reg_lambda}")
print(f"  subsample={xgb.subsample}")
print(f"  colsample_bytree={xgb.colsample_bytree}")
