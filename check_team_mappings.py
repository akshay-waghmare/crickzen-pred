#!/usr/bin/env python
"""Check team abbreviation mappings for conflicts."""
from src.bbl_pipeline.features.store import InMemoryFeatureStore

abbr = InMemoryFeatureStore.TEAM_ABBREVIATIONS

print("=" * 60)
print("TEAM ABBREVIATION MAPPING CHECK")
print("=" * 60)
print(f"Total abbreviations: {len(abbr)}")

# Check BBL teams
bbl_teams = ['Sydney Sixers', 'Sydney Thunder', 'Brisbane Heat', 'Melbourne Stars', 
             'Melbourne Renegades', 'Perth Scorchers', 'Adelaide Strikers', 'Hobart Hurricanes']

print("\n--- BBL Team Mappings ---")
for code, team in sorted(abbr.items()):
    if team in bbl_teams:
        print(f"  {code:10} → {team}")

# Check ILT20 teams  
ilt20_teams = ['Dubai Capitals', 'Abu Dhabi Knight Riders', 'Sharjah Warriors',
               'Desert Vipers', 'Gulf Giants', 'MI Emirates']

print("\n--- ILT20 Team Mappings ---")
for code, team in sorted(abbr.items()):
    if team in ilt20_teams:
        print(f"  {code:10} → {team}")

# Check SSM teams
ssm_teams = ['Otago', 'Northern Districts', 'Auckland', 'Central Districts', 
             'Canterbury', 'Wellington']

print("\n--- SSM (Super Smash) Team Mappings ---")
for code, team in sorted(abbr.items()):
    if team in ssm_teams:
        print(f"  {code:10} → {team}")

# Check for conflicts
print("\n--- Potential Cross-League Conflicts ---")
expected_mappings = [
    ('SYS', 'Sydney Sixers', 'BBL - should NOT be Sylhet Sunrisers'),
    ('DC', 'Dubai Capitals', 'ILT20 - should NOT be Dhaka Capitals'),
    ('CK', 'Canterbury', 'SSM - should NOT be Chittagong Kings'),
    ('SS', 'Sylhet Strikers', 'BPL - unique'),
    ('RR', 'Rangpur Riders', 'BPL - unique'),
]

all_ok = True
for code, expected, desc in expected_mappings:
    actual = abbr.get(code, 'NOT FOUND')
    if actual == expected:
        status = '✅ OK'
    else:
        status = f'❌ CONFLICT - got {actual}'
        all_ok = False
    print(f"  {code:5} : {expected:25} ({desc}) {status}")

print("\n" + "=" * 60)
if all_ok:
    print("✅ ALL TEAM MAPPINGS ARE CORRECT!")
else:
    print("❌ SOME CONFLICTS FOUND - NEEDS FIXING")
print("=" * 60)
