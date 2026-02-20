"""WPL Female - Per-Over Log Loss Analysis by Innings."""
import pandas as pd
import numpy as np
import joblib

def calculate_logloss(y_true, y_pred, eps=1e-15):
    y_pred = np.clip(y_pred, eps, 1 - eps)
    return -np.mean(y_true * np.log(y_pred) + (1 - y_true) * np.log(1 - y_pred))

def calculate_brier(y_true, y_pred):
    return np.mean((y_true - y_pred) ** 2)

def main():
    # Load data
    df = pd.read_parquet('data/wpl_female_features_v1/training.parquet')
    model = joblib.load('models/wpl_female_v1/champion_model.joblib')
    existing_cal = joblib.load('models/wpl_female_v1/isotonic_calibrator.pkl')
    features = model.selected_features_
    
    df['over'] = (20 - df['overs_remaining']).clip(1, 20).astype(int)
    y_true = df['is_winner'].values
    resource_probs = df['resource_win_prob'].values
    
    # Raw model predictions
    X = df[features]
    raw_model_probs = model.predict_proba(X)[:, 1]
    
    # Inn-specific calibrated
    inn_specific_probs = np.zeros_like(raw_model_probs)
    inn1_mask = df['innings'] == 1
    inn2_mask = df['innings'] == 2
    inn_specific_probs[inn1_mask] = existing_cal['calibrator_innings1'].predict(raw_model_probs[inn1_mask])
    inn_specific_probs[inn2_mask] = existing_cal['calibrator_innings2'].predict(raw_model_probs[inn2_mask])
    
    print('=' * 100)
    print('WPL FEMALE - PER-OVER LOG LOSS ANALYSIS')
    print('=' * 100)
    print()
    print('INNINGS 1 - PER-OVER LOG LOSS ANALYSIS')
    print('=' * 100)
    print(f"{'Over':<5} | {'N':<5} | {'LL_Raw':<8} | {'LL_Res':<8} | {'LL_Inn':<8} | {'B_Raw':<8} | {'B_Res':<8} | {'Best_LL':<8}")
    print('-' * 100)
    
    for over in range(1, 21):
        mask = (df['innings'] == 1) & (df['over'] == over)
        if mask.sum() == 0:
            continue
        n = mask.sum()
        y = y_true[mask]
        raw = raw_model_probs[mask]
        res = resource_probs[mask]
        inn = inn_specific_probs[mask]
        
        ll_raw = calculate_logloss(y, raw)
        ll_res = calculate_logloss(y, res)
        ll_inn = calculate_logloss(y, inn)
        b_raw = calculate_brier(y, raw)
        b_res = calculate_brier(y, res)
        
        best_ll = 'Raw' if ll_raw <= ll_res and ll_raw <= ll_inn else ('Res' if ll_res <= ll_inn else 'Inn')
        
        print(f'{over:<5} | {n:<5} | {ll_raw:<8.4f} | {ll_res:<8.4f} | {ll_inn:<8.4f} | {b_raw:<8.4f} | {b_res:<8.4f} | {best_ll:<8}')
    
    print()
    print('INNINGS 2 - PER-OVER LOG LOSS ANALYSIS')
    print('=' * 100)
    print(f"{'Over':<5} | {'N':<5} | {'LL_Raw':<8} | {'LL_Res':<8} | {'LL_Inn':<8} | {'B_Raw':<8} | {'B_Res':<8} | {'Best_LL':<8}")
    print('-' * 100)
    
    for over in range(1, 21):
        mask = (df['innings'] == 2) & (df['over'] == over)
        if mask.sum() == 0:
            continue
        n = mask.sum()
        y = y_true[mask]
        raw = raw_model_probs[mask]
        res = resource_probs[mask]
        inn = inn_specific_probs[mask]
        
        ll_raw = calculate_logloss(y, raw)
        ll_res = calculate_logloss(y, res)
        ll_inn = calculate_logloss(y, inn)
        b_raw = calculate_brier(y, raw)
        b_res = calculate_brier(y, res)
        
        best_ll = 'Raw' if ll_raw <= ll_res and ll_raw <= ll_inn else ('Res' if ll_res <= ll_inn else 'Inn')
        
        print(f'{over:<5} | {n:<5} | {ll_raw:<8.4f} | {ll_res:<8.4f} | {ll_inn:<8.4f} | {b_raw:<8.4f} | {b_res:<8.4f} | {best_ll:<8}')
    
    # Summary by phase
    print()
    print('=' * 100)
    print('SUMMARY: BEST LOG LOSS PREDICTOR BY PHASE')
    print('=' * 100)
    
    phases = [
        ('Powerplay', (1, 6)),
        ('Middle', (7, 15)),
        ('Death', (16, 20))
    ]
    
    for innings in [1, 2]:
        print(f"\nInnings {innings}:")
        print(f"{'Phase':<12} | {'N':<6} | {'LL_Raw':<8} | {'LL_Res':<8} | {'LL_Inn':<8} | {'Best':<8}")
        print('-' * 60)
        
        for phase_name, (start, end) in phases:
            mask = (df['innings'] == innings) & (df['over'] >= start) & (df['over'] <= end)
            if mask.sum() == 0:
                continue
            n = mask.sum()
            y = y_true[mask]
            raw = raw_model_probs[mask]
            res = resource_probs[mask]
            inn = inn_specific_probs[mask]
            
            ll_raw = calculate_logloss(y, raw)
            ll_res = calculate_logloss(y, res)
            ll_inn = calculate_logloss(y, inn)
            
            best = 'Raw' if ll_raw <= ll_res and ll_raw <= ll_inn else ('Res' if ll_res <= ll_inn else 'Inn')
            
            print(f'{phase_name:<12} | {n:<6} | {ll_raw:<8.4f} | {ll_res:<8.4f} | {ll_inn:<8.4f} | {best:<8}')

if __name__ == '__main__':
    main()
