"""Check ILT20 data structure."""
import os
import json

folder = 'international_league_data/ilt_male_json'
json_files = [f for f in os.listdir(folder) if f.endswith('.json')]
print(f'Total JSON files: {len(json_files)}')

# Check one file structure
with open(f'{folder}/{json_files[0]}', 'r') as f:
    data = json.load(f)
    
print(f'Keys: {list(data.keys())}')
print(f'Info keys: {list(data["info"].keys())}')
print(f'Event: {data["info"].get("event", {})}')
print(f'Teams: {list(data["info"]["players"].keys())}')
print(f'Number of innings: {len(data.get("innings", []))}')

# Check venues
venues = set()
for f in json_files:
    with open(f'{folder}/{f}', 'r') as file:
        d = json.load(file)
        venue = d["info"].get("venue", "Unknown")
        venues.add(venue)
        
print(f'\nUnique venues ({len(venues)}):')
for v in sorted(venues):
    print(f'  - {v}')
