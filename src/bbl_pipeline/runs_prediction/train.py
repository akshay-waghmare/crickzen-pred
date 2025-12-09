import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
import joblib
from pathlib import Path
import structlog

logger = structlog.get_logger()

def train_runs_model(data_path: str, model_path: str):
    logger.info("Loading training data", path=data_path)
    df = pd.read_parquet(data_path)
    
    target = 'target_runs'
    features = [c for c in df.columns if c != target]
    
    X = df[features]
    y = df[target]
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    logger.info(f"Training XGBoost Regressor on {len(X_train)} samples")
    
    model = xgb.XGBRegressor(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=5,
        subsample=0.8,
        colsample_bytree=0.8,
        objective='reg:squarederror',
        n_jobs=-1
    )
    
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
    
    # Evaluation
    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    mse = mean_squared_error(y_test, preds)
    rmse = mse ** 0.5
    
    logger.info("Model Evaluation", mae=mae, rmse=rmse)
    
    # Save model
    Path(model_path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    logger.info(f"Model saved to {model_path}")
    
    # Feature Importance
    importance = pd.DataFrame({
        'feature': features,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print("\nTop 10 Features:")
    print(importance.head(10))

if __name__ == "__main__":
    structlog.configure(processors=[structlog.processors.JSONRenderer()])
    train_runs_model(
        data_path="data/runs_prediction_training.parquet",
        model_path="models/runs_prediction/xgb_regressor.joblib"
    )
