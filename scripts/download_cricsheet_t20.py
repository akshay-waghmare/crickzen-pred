import os
import requests
import zipfile
import io
from pathlib import Path
from tqdm import tqdm
import structlog

# Convert print to structured logging for better consistency
logger = structlog.get_logger()

# Data configuration
DATA_DIR = Path("data")
URL_TEMPLATE = "https://cricsheet.org/downloads/{slug}_json.zip"

# NOTE: Cricsheet uses specific slugs that don't always match league abbreviations
# Check https://cricsheet.org/downloads/ for current slugs
MALE_LEAGUES = [
    "bbl",                      # Big Bash League (654 matches)
    "ipl",                      # Indian Premier League (1169 matches)
    "psl",                      # Pakistan Super League (314 matches)
    "cpl",                      # Caribbean Premier League (407 matches)
    "sat",                      # SA20 (121 matches) - slug is "sat" not "sa20"
    "bpl",                      # Bangladesh Premier League (459 matches)
    "lpl",                      # Lanka Premier League (119 matches)
    "ilt",                      # International League T20 (134 matches) - slug is "ilt" not "ilt20"
    "mlc",                      # Major League Cricket (75 matches)
    "super_smash",              # Super Smash (446 total, mixed gender - will filter)
    "ntb",                      # T20 Blast (1455 matches) - slug is "ntb"
    "smat",                     # Syed Mushtaq Ali Trophy (695 matches)
    "csa_t20_challenge",        # CSA T20 Challenge (314 matches)
]

FEMALE_LEAGUES = [
    "wbbl",                     # Women's Big Bash League (519 matches)
    "wpl",                      # Women's Premier League (74 matches)
    "super_smash",              # Super Smash (female portion - 186 matches)
    "wcpl",                     # Women's Caribbean Premier League (25 matches)
]

def download_and_extract(slug: str, gender: str):
    """
    Download zip for a league and extract to data/t20_{gender}_json/{slug}/
    """
    url = URL_TEMPLATE.format(slug=slug)
    output_dir = DATA_DIR / f"t20_{gender}_json" / slug
    
    # Check if we should skip (simple logic: check if dir exists and has JSONs)
    # Actually, for data freshness, we might want to overwrite. 
    # But let's verify if URL exists first.
    
    logger.info("downloading_league", slug=slug, gender=gender, url=url)
    
    try:
        response = requests.get(url, stream=True)
        if response.status_code != 200:
            logger.error("download_failed", status=response.status_code, slug=slug)
            return

        total_size = int(response.headers.get('content-length', 0))
        
        # Download in memory (these Zips are not huge, usually < 50MB)
        # For very large files, we'd stream to disk first.
        content = io.BytesIO()
        with tqdm(total=total_size, unit='B', unit_scale=True, desc=f"{slug}") as pbar:
            for chunk in response.iter_content(chunk_size=8192):
                content.write(chunk)
                pbar.update(len(chunk))
        
        logger.info("extracting_files", target_dir=str(output_dir))
        with zipfile.ZipFile(content) as z:
            os.makedirs(output_dir, exist_ok=True)
            z.extractall(path=output_dir)
            
        file_count = len(list(output_dir.glob("*.json")))
        logger.info("league_processed", slug=slug, files_extracted=file_count)
        
    except Exception as e:
        logger.error("process_failed", slug=slug, error=str(e))

def main():
    print(f"Starting Unified T20 Data Download...")
    print(f"Target Directory: {DATA_DIR.absolute()}")
    
    # Process Male Leagues
    print("\nProcessing Male Leagues:")
    for league in MALE_LEAGUES:
        download_and_extract(league, "male")
        
    # Process Female Leagues
    print("\nProcessing Female Leagues:")
    for league in FEMALE_LEAGUES:
        download_and_extract(league, "female")
        
    print("\nDownload Complete.")

if __name__ == "__main__":
    main()
