import json
import hashlib
from pathlib import Path
from typing import Dict
import structlog

logger = structlog.get_logger()

class IngestionState:
    """
    Tracks the state of ingested files to support incremental updates.
    Uses file hashes to detect changes.
    """
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.processed_files: Dict[str, str] = {} # filename -> hash
        self.load()

    def load(self) -> None:
        """Load state from disk."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    self.processed_files = json.load(f)
            except Exception as e:
                logger.warning("Failed to load state file, starting fresh", error=str(e))
                self.processed_files = {}

    def save(self) -> None:
        """Save state to disk."""
        try:
            # Ensure directory exists
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(self.processed_files, f, indent=2)
        except Exception as e:
            logger.error("Failed to save state file", error=str(e))

    def is_processed(self, file_path: Path) -> bool:
        """Check if a file has been processed and hasn't changed."""
        if not file_path.exists():
            return False
            
        current_hash = self._compute_hash(file_path)
        stored_hash = self.processed_files.get(file_path.name)
        
        return stored_hash == current_hash

    def mark_processed(self, file_path: Path) -> None:
        """Mark a file as processed."""
        if not file_path.exists():
            return
            
        file_hash = self._compute_hash(file_path)
        self.processed_files[file_path.name] = file_hash

    def _compute_hash(self, file_path: Path) -> str:
        """Compute MD5 hash of a file."""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error("Failed to compute hash", file=str(file_path), error=str(e))
            return ""
