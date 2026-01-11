"""WPL Female - ECE-Optimized Phase Calibrators Log Loss Analysis."""
import pandas as pd
import numpy as np
import joblib

def calculate_logloss(y_true, y_pred, eps=1e-15):
    y_pred = np.clip(y_pred, eps, 1 - eps)
    return -np.mean(y_true * np.log(y_pred) + (1 - y_true) * np.log(1 - y_pred))

def calculate_brier(y_true, y_pred):
    return np.mean((y_true - y_pred) ** 2)

def calculate_ece(y_true, y_pred, n_bins=10):
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        mask = (y_pred >= bin_boundaries[i]) & (y_pred < bin_boundaries[i + 1])
        if mask.sum() > 0:
            bin_accuracy = y_true[mask].mean()
            bin_confidence = y_pred[mask].mean()
            bin_weight = mask.sum() / len(y_true)
            ece += bin_weight * abs(bin_accuracy - bin_confidence)
    return ece

def get_phase_name(innings, over):
    """Get phase name (Powerplay, Middle, Death)."""
    if over <= 6:
        return 'powerplay'
    elif over <= 15:
        return 'middle'
    else:
        return 'death'

def main():
    # Load data
    df = pd.read_parquet('data/wpl_female_features_v1/training.parquet')
    model = joblib.load('models/wpl_female_v1/champion_model.joblib')
    existing_cal = joblib.load('models/wpl_female_v1/isotonic_calibrator.pkl')
    phase_cals = joblib.load('models/wpl_female_v1/phase_calibrators.pkl')
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
    
    # Phase calibrators (ECE-optimized) - use RAW model as input
    phase_probs = np.zeros_like(raw_model_probs)
    for idx in range(len(df)):
        inn = int(df.iloc[idx]['innings'])
        phase = get_phase_name(inn, int(df.iloc[idx]['over']))
        cal_key = f'inn{inn}_{phase}'
        
        # Phase calibrators use RAW model output as input
        cal_input = raw_model_probs[idx]
        if cal_key in phase_cals:
            cal_obj = phase_cals[cal_key]['calibrator']
            phase_probs[idx] = cal_obj.predict(np.array([cal_input]))[0]
        else:
            # Fallback to inn-specific if phase cal not found
            phase_probs[idx] = inn_specific_probs[idx]
    
    print('=' * 120)
    print('WPL FEMALE - ECE-OPTIMIZED PHASE CALIBRATOR LOG LOSS ANALYSIS')
    print('=' * 120)
    print()
    print('INNINGS 1 - PER-OVER COMPARISON (Raw vs Resource vs Inn-Specific vs Phase ECE-Opt)')
    print('=' * 120)
    print(f"{'Over':<5} | {'N':<5} | {'LL_Raw':<8} | {'LL_Res':<8} | {'LL_Inn':<8} | {'LL_Phase':<8} | {'Best':<8} | {'Worst':<8}")
    print('-' * 120)
    
    for over in range(1, 21):
        mask = (df['innings'] == 1) & (df['over'] == over)
        if mask.sum() == 0:
            continue
        n = mask.sum()
        y = y_true[mask]
        raw = raw_model_probs[mask]
        res = resource_probs[mask]
        inn = inn_specific_probs[mask]
        ph = phase_probs[mask]
        
        ll_raw = calculate_logloss(y, raw)
        ll_res = calculate_logloss(y, res)
        ll_inn = calculate_logloss(y, inn)
        ll_phase = calculate_logloss(y, ph)
        
        lls = [('Raw', ll_raw), ('Res', ll_res), ('Inn', ll_inn), ('Phase', ll_phase)]
        best = min(lls, key=lambda x: x[1])[0]
        worst = max(lls, key=lambda x: x[1])[0]
        
        print(f'{over:<5} | {n:<5} | {ll_raw:<8.4f} | {ll_res:<8.4f} | {ll_inn:<8.4f} | {ll_phase:<8.4f} | {best:<8} | {worst:<8}')
    
    print()
    print('INNINGS 2 - PER-OVER COMPARISON (Raw vs Resource vs Inn-Specific vs Phase ECE-Opt)')
    print('=' * 120)
    print(f"{'Over':<5} | {'N':<5} | {'LL_Raw':<8} | {'LL_Res':<8} | {'LL_Inn':<8} | {'LL_Phase':<8} | {'Best':<8} | {'Worst':<8}")
    print('-' * 120)
    
    for over in range(1, 21):
        mask = (df['innings'] == 2) & (df['over'] == over)
        if mask.sum() == 0:
            continue
        n = mask.sum()
        y = y_true[mask]
        raw = raw_model_probs[mask]
        res = resource_probs[mask]
        inn = inn_specific_probs[mask]
        ph = phase_probs[mask]
        
        ll_raw = calculate_logloss(y, raw)
        ll_res = calculate_logloss(y, res)
        ll_inn = calculate_logloss(y, inn)
        ll_phase = calculate_logloss(y, ph)
        
        lls = [('Raw', ll_raw), ('Res', ll_res), ('Inn', ll_inn), ('Phase', ll_phase)]
        best = min(lls, key=lambda x: x[1])[0]
        worst = max(lls, key=lambda x: x[1])[0]
        
        print(f'{over:<5} | {n:<5} | {ll_raw:<8.4f} | {ll_res:<8.4f} | {ll_inn:<8.4f} | {ll_phase:<8.4f} | {best:<8} | {worst:<8}')
    
    # Summary by phase
    print()
    print('=' * 120)
    print('SUMMARY: LOG LOSS BY PHASE (Which calibrator to trust?)')
    print('=' * 120)
    
    phases = [
        ('Powerplay', (1, 6)),
        ('Middle', (7, 15)),
        ('Death', (16, 20))
    ]
    
    for innings in [1, 2]:
        print(f"\nInnings {innings}:")
        print(f"{'Phase':<12} | {'N':<6} | {'LL_Raw':<8} | {'LL_Res':<8} | {'LL_Inn':<8} | {'LL_Phase':<8} | {'Best':<8}")
        print('-' * 80)
        
        for phase_name, (start, end) in phases:
            mask = (df['innings'] == innings) & (df['over'] >= start) & (df['over'] <= end)
            if mask.sum() == 0:
                continue
            n = mask.sum()
            y = y_true[mask]
            raw = raw_model_probs[mask]
            res = resource_probs[mask]
            inn = inn_specific_probs[mask]
            ph = phase_probs[mask]
            
            ll_raw = calculate_logloss(y, raw)
            ll_res = calculate_logloss(y, res)
            ll_inn = calculate_logloss(y, inn)
            ll_phase = calculate_logloss(y, ph)
            
            lls = [('Raw', ll_raw), ('Res', ll_res), ('Inn', ll_inn), ('Phase', ll_phase)]
            best = min(lls, key=lambda x: x[1])[0]
            
            print(f'{phase_name:<12} | {n:<6} | {ll_raw:<8.4f} | {ll_res:<8.4f} | {ll_inn:<8.4f} | {ll_phase:<8.4f} | {best:<8}')
    
    # Count wins
    print()
    print('=' * 120)
    print('TALLY: Which calibrator wins most overs for Log Loss?')
    print('=' * 120)
    
    wins = {'Raw': 0, 'Res': 0, 'Inn': 0, 'Phase': 0}
    total_overs = 0
    
    for innings in [1, 2]:
        for over in range(1, 21):
            mask = (df['innings'] == innings) & (df['over'] == over)
            if mask.sum() == 0:
                continue
            
            total_overs += 1
            y = y_true[mask]
            raw = raw_model_probs[mask]
            res = resource_probs[mask]
            inn = inn_specific_probs[mask]
            ph = phase_probs[mask]
            
            ll_raw = calculate_logloss(y, raw)
            ll_res = calculate_logloss(y, res)
            ll_inn = calculate_logloss(y, inn)
            ll_phase = calculate_logloss(y, ph)
            
            lls = [('Raw', ll_raw), ('Res', ll_res), ('Inn', ll_inn), ('Phase', ll_phase)]
            best = min(lls, key=lambda x: x[1])[0]
            wins[best] += 1
    
    print(f"Total overs analyzed: {total_overs}")
    print(f"Raw Model wins: {wins['Raw']}/{total_overs} overs ({wins['Raw']/total_overs*100:.1f}%)")
    print(f"Resource wins: {wins['Res']}/{total_overs} overs ({wins['Res']/total_overs*100:.1f}%)")
    print(f"Inn-Specific wins: {wins['Inn']}/{total_overs} overs ({wins['Inn']/total_overs*100:.1f}%)")
    print(f"Phase ECE-Opt wins: {wins['Phase']}/{total_overs} overs ({wins['Phase']/total_overs*100:.1f}%)")
    print()
    print(f"🏆 Winner: {max(wins, key=wins.get)} with {max(wins.values())} wins")

if __name__ == '__main__':
    main()
