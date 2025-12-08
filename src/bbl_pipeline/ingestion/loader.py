import json
from pathlib import Path
from typing import Any, Dict, Generator
import structlog

logger = structlog.get_logger()

def load_match_file(file_path: Path) -> Dict[str, Any]:
    """
    Load a single Cricsheet JSON file.
    
    Args:
        file_path: Path to the JSON file.
        
    Returns:
        Dictionary containing the match data.
        
    Raises:
        json.JSONDecodeError: If the file is not valid JSON.
        OSError: If the file cannot be read.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON", file=str(file_path), error=str(e))
        raise e
    except Exception as e:
        logger.error("Failed to read file", file=str(file_path), error=str(e))
        raise e

def iter_match_files(directory: Path) -> Generator[Path, None, None]:
    """
    Yield all JSON files in the directory.
    """
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
        
    for file_path in directory.glob("*.json"):
        yield file_path
