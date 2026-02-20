#!/usr/bin/env python3
"""Check if SSM per-over calibrators are using the correct source based on analysis."""

import joblib

calibrators = joblib.load('models/ssm_v1/per_over_calibrators.pkl')

print('SSM Per-Over Calibrator Source Check')
print('=' * 70)
print(f"{'Key':<20} {'Trained':<10} {'Expected':<10} {'Match?':<10}")
print('-' * 70)

# Based on ECE analysis:
# Inn1 all overs: Res (Resource wins ECE all 20 overs)
# Inn2 1-2: Cal (Calibrated wins)
# Inn2 3-4: Raw
# Inn2 5-11: Res
# Inn2 12-20: Raw

def expected_source(inn, over):
    if inn == 1:
        return 'res'  # Resource wins ECE all 20 overs in Inn1
    else:
        if over <= 2:
            return 'cal'  # Cal wins overs 1-2
        elif over <= 4:
            return 'raw'  # Raw wins overs 3-4
        elif over <= 11:
            return 'res'  # Res wins overs 5-11
        else:
            return 'raw'  # Raw wins overs 12-20

mismatches = []
for inn in [1, 2]:
    for over in range(1, 21):
        key = f'inn{inn}_over{over}'
        cal_info = calibrators[key]
        trained = cal_info['source']
        expected = expected_source(inn, over)
        match = '✓' if trained == expected else '✗ WRONG'
        if trained != expected:
            mismatches.append((key, trained, expected))
        print(f"{key:<20} {trained:<10} {expected:<10} {match:<10}")
    print()

print('=' * 70)
if mismatches:
    print(f'MISMATCHES FOUND: {len(mismatches)}')
    for k, t, e in mismatches:
        print(f'  {k}: trained={t}, should be={e}')
else:
    print('✅ All calibrators using correct source!')
