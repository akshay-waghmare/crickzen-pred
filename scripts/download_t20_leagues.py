"""
Download all T20 club/franchise leagues from Cricsheet.org
Organize into male and female folders for combined model training.

T20 Club Leagues (Male):
- Big Bash League (BBL): 654 matches
- Bangladesh Premier League (BPL): 459 matches
- Caribbean Premier League (CPL): 407 matches
- CSA T20 Challenge: 314 matches
- International League T20 (ILT20): 134 matches
- Indian Premier League (IPL): 1,169 matches
- Lanka Premier League (LPL): 119 matches
- Major League Cricket (MLC): 75 matches
- Mzansi Super League: 56 matches
- Nepal Premier League: 64 matches
- T20 Blast: 1,455 matches
- Pakistan Super League (PSL): 314 matches
- SA20: 121 matches
- Syed Mushtaq Ali Trophy: 695 matches
- Super Smash (Men): 260 matches
- The Hundred (Men): 167 matches

T20 Club Leagues (Female):
- Women's Big Bash League (WBBL): 519 matches
- Women's Premier League (WPL): 74 matches
- Women's Caribbean Premier League (WCPL): 25 matches
- Women's Cricket Super League: 95 matches
- Women's T20 Blast: 56 matches
- Women's T20 Challenge: 13 matches
- Charlotte Edwards Cup: 124 matches
- Super Smash (Women): 186 matches
- The Hundred (Women): 155 matches
- FairBreak Invitational: 39 matches
- T20 Blaze: 17 matches

Total: ~6,500+ male T20 matches, ~1,300+ female T20 matches
"""

import os
import requests
import zipfile
import shutil
from pathlib import Path

# Base URL for cricsheet downloads
BASE_URL = "https://cricsheet.org/downloads"

# Male T20 Leagues (Club/Franchise)
MALE_T20_LEAGUES = {
    # Major leagues
    'bbl': 'Big Bash League',
    'bpl': 'Bangladesh Premier League', 
    'cpl': 'Caribbean Premier League',
    'csa_t20_challenge': 'CSA T20 Challenge',
    'ilt20': 'International League T20',
    'ipl': 'Indian Premier League',
    'lpl': 'Lanka Premier League',
    'mlc': 'Major League Cricket',
    'msl': 'Mzansi Super League',
    'npl': 'Nepal Premier League',
    't20_blast': 'T20 Blast',
    'psl': 'Pakistan Super League',
    'sa20': 'SA20',
    'smat': 'Syed Mushtaq Ali Trophy',
    'super_smash_male': 'Super Smash (Men)',
    'the_hundred_male': 'The Hundred (Men)',
    # Ireland
    'ipt20': 'Cricket Ireland Inter-Provincial Twenty20 Trophy',
    # Sri Lanka
    'major_clubs_t20': 'Major Clubs T20 Tournament',
}

# Female T20 Leagues (Club/Franchise)
FEMALE_T20_LEAGUES = {
    'wbbl': "Women's Big Bash League",
    'wpl': "Women's Premier League",
    'wcpl': "Women's Caribbean Premier League",
    'wcsl': "Women's Cricket Super League",
    'wt20_blast': "Women's T20 Blast",
    'wt20_challenge': "Women's T20 Challenge",
    'charlotte_edwards': 'Charlotte Edwards Cup',
    'super_smash_female': 'Super Smash (Women)',
    'the_hundred_female': 'The Hundred (Women)',
    'fairbreak': 'FairBreak Invitational Tournament',
    't20_blaze': 'T20 Blaze',
}

# Download URLs for each league (JSON format)
DOWNLOAD_URLS = {
    # Male leagues
    'bbl': f'{BASE_URL}/bbl_json.zip',
    'bpl': f'{BASE_URL}/bpl_json.zip',
    'cpl': f'{BASE_URL}/cpl_json.zip',
    'csa_t20_challenge': f'{BASE_URL}/csa_t20_challenge_json.zip',
    'ilt20': f'{BASE_URL}/ilt20_json.zip',
    'ipl': f'{BASE_URL}/ipl_json.zip',
    'lpl': f'{BASE_URL}/lpl_json.zip',
    'mlc': f'{BASE_URL}/mlc_json.zip',
    'msl': f'{BASE_URL}/msl_json.zip',
    'npl': f'{BASE_URL}/npl_json.zip',
    't20_blast': f'{BASE_URL}/t20_blast_json.zip',
    'psl': f'{BASE_URL}/psl_json.zip',
    'sa20': f'{BASE_URL}/sa20_json.zip',
    'smat': f'{BASE_URL}/smat_json.zip',
    'super_smash_male': f'{BASE_URL}/super_smash_male_json.zip',
    'the_hundred_male': f'{BASE_URL}/the_hundred_male_json.zip',
    'ipt20': f'{BASE_URL}/ipt20_json.zip',
    'major_clubs_t20': f'{BASE_URL}/major_clubs_t20_json.zip',
    
    # Female leagues
    'wbbl': f'{BASE_URL}/wbbl_json.zip',
    'wpl': f'{BASE_URL}/wpl_json.zip',
    'wcpl': f'{BASE_URL}/wcpl_json.zip',
    'wcsl': f'{BASE_URL}/wcsl_json.zip',
    'wt20_blast': f'{BASE_URL}/wt20_blast_json.zip',
    'wt20_challenge': f'{BASE_URL}/wt20_challenge_json.zip',
    'charlotte_edwards': f'{BASE_URL}/charlotte_edwards_cup_json.zip',
    'super_smash_female': f'{BASE_URL}/super_smash_female_json.zip',
    'the_hundred_female': f'{BASE_URL}/the_hundred_female_json.zip',
    'fairbreak': f'{BASE_URL}/fairbreak_json.zip',
    't20_blaze': f'{BASE_URL}/t20_blaze_json.zip',
}


def download_file(url: str, dest_path: Path) -> bool:
    """Download a file from URL to destination path."""
    try:
        print(f"  Downloading {url}...")
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def extract_zip(zip_path: Path, dest_dir: Path) -> int:
    """Extract zip file and return number of JSON files."""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Get list of JSON files
            json_files = [f for f in zip_ref.namelist() if f.endswith('.json')]
            zip_ref.extractall(dest_dir)
        return len(json_files)
    except Exception as e:
        print(f"  ERROR extracting: {e}")
        return 0


def download_league(league_key: str, dest_dir: Path, temp_dir: Path) -> int:
    """Download and extract a league, return match count."""
    if league_key not in DOWNLOAD_URLS:
        print(f"  No URL for {league_key}")
        return 0
    
    url = DOWNLOAD_URLS[league_key]
    zip_path = temp_dir / f"{league_key}.zip"
    
    # Download
    if not download_file(url, zip_path):
        return 0
    
    # Extract to temp location
    extract_dir = temp_dir / league_key
    extract_dir.mkdir(exist_ok=True)
    count = extract_zip(zip_path, extract_dir)
    
    # Move JSON files to destination
    for json_file in extract_dir.rglob('*.json'):
        shutil.copy2(json_file, dest_dir / json_file.name)
    
    # Cleanup
    zip_path.unlink()
    shutil.rmtree(extract_dir)
    
    return count


def main():
    # Setup directories
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'
    
    male_dir = data_dir / 't20_male_combined_json'
    female_dir = data_dir / 't20_female_combined_json'
    temp_dir = data_dir / 'temp_downloads'
    
    male_dir.mkdir(parents=True, exist_ok=True)
    female_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("DOWNLOADING T20 CLUB/FRANCHISE LEAGUES FROM CRICSHEET")
    print("=" * 60)
    
    # Download male leagues
    print("\n" + "=" * 40)
    print("MALE T20 LEAGUES")
    print("=" * 40)
    
    male_total = 0
    for league_key, league_name in MALE_T20_LEAGUES.items():
        print(f"\n{league_name}:")
        count = download_league(league_key, male_dir, temp_dir)
        print(f"  ✓ {count} matches")
        male_total += count
    
    print(f"\n{'='*40}")
    print(f"MALE TOTAL: {male_total} matches in {male_dir}")
    
    # Download female leagues  
    print("\n" + "=" * 40)
    print("FEMALE T20 LEAGUES")
    print("=" * 40)
    
    female_total = 0
    for league_key, league_name in FEMALE_T20_LEAGUES.items():
        print(f"\n{league_name}:")
        count = download_league(league_key, female_dir, temp_dir)
        print(f"  ✓ {count} matches")
        female_total += count
    
    print(f"\n{'='*40}")
    print(f"FEMALE TOTAL: {female_total} matches in {female_dir}")
    
    # Cleanup temp
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    
    # Summary
    print("\n" + "=" * 60)
    print("DOWNLOAD COMPLETE")
    print("=" * 60)
    print(f"Male matches:   {male_total} in {male_dir}")
    print(f"Female matches: {female_total} in {female_dir}")
    print("\nNext steps:")
    print("1. Run ingestion: bbl-pipeline ingest --input-dir data/t20_male_combined_json --output-dir data/t20_male_raw")
    print("2. Run processing: bbl-pipeline process --input-dir data/t20_male_raw/matches --output-dir data/t20_male_features_v1")
    print("3. Train model: bbl-pipeline train --input-file data/t20_male_features_v1/training.parquet --output-dir models/t20_male_v1")


if __name__ == '__main__':
    main()
