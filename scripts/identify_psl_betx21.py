"""Identify PSL match IDs in betx21 data directory."""
import gzip
import json
from pathlib import Path

BASE = Path(r"C:\Users\ADMINS\Documents\projects\betx21.live\ipl_matches_download")

IPL_IDS = {
    "35436411", "35436433", "35439742", "35445130", "35448572", "35449675",
    "35452229", "35452241", "35460131", "35464806", "35460133", "35468493",
    "35472691", "35475078", "35479213", "35479923", "35483421", "35483422",
    "35491266", "35495679",
}

PSL_TEAMS_LOWER = {
    "islamabad united", "lahore qalandars", "karachi kings", "peshawar zalmi",
    "multan sultans", "quetta gladiators",
}

def first_record(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                return json.loads(line)
    return {}


all_matches: dict[str, dict] = {}

for date_dir in sorted(BASE.iterdir()):
    if not date_dir.is_dir():
        continue
    for f in sorted(date_dir.glob("*_scores.jsonl.gz")):
        match_id = f.name.split("_")[0]
        try:
            rec = first_record(f)
            t1 = rec.get("t1", "")
            t2 = rec.get("t2", "")
            all_matches[match_id] = {
                "date": date_dir.name,
                "t1": t1,
                "t2": t2,
            }
        except Exception as e:
            print(f"  Error {f.name}: {e}")

print(f"\nTotal unique matches found: {len(all_matches)}")
print(f"Known IPL matches: {len(IPL_IDS)}\n")

print("=== NON-IPL MATCHES ===")
psl_matches = {}
for mid, info in sorted(all_matches.items(), key=lambda x: (x[1]["date"], x[0])):
    if mid in IPL_IDS:
        continue
    t1_lower = info["t1"].lower()
    t2_lower = info["t2"].lower()
    is_psl = any(team in t1_lower or team in t2_lower for team in PSL_TEAMS_LOWER)
    flag = " *** PSL ***" if is_psl else ""
    print(f"  {mid} ({info['date']}): {info['t1']} vs {info['t2']}{flag}")
    if is_psl:
        psl_matches[mid] = info

print(f"\n=== PSL MATCHES ({len(psl_matches)} found) ===")
for mid, info in sorted(psl_matches.items()):
    print(f"  '{mid}': {{date: '{info['date']}', t1: '{info['t1']}', t2: '{info['t2']}'}}")
