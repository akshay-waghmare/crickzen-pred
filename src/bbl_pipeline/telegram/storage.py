"""
Append-only storage for prediction records.

Implements JSON Lines (.jsonl) storage format for immutable
prediction records. Each record is a single JSON object on its own line.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import json
import logging
import os


logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Raised when storage operation fails."""
    pass


@dataclass
class StoredRecord:
    """Base class for stored prediction records."""
    
    match_id: str
    post_type: str
    telegram_message_id: int
    telegram_timestamp: str  # ISO8601 format
    posted_at_utc: str  # ISO8601 format
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary for JSON serialization."""
        return asdict(self)


class PredictionStorage:
    """Append-only storage for prediction records."""
    
    def __init__(self, storage_path: Union[str, Path]):
        """
        Initialize prediction storage.
        
        Args:
            storage_path: Path to the JSON Lines storage file
        """
        self.storage_path = Path(storage_path)
        self._ensure_storage_exists()
    
    def _ensure_storage_exists(self) -> None:
        """Ensure storage directory and file exist."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self.storage_path.touch()
            logger.info(f"Created storage file: {self.storage_path}")
    
    def append_record(self, record: Dict[str, Any]) -> None:
        """
        Append a record to storage.
        
        This operation is atomic - either the full record is written
        or nothing is written. Uses file locking on Unix systems.
        
        Args:
            record: Dictionary containing the record data
            
        Raises:
            StorageError: If write operation fails
        """
        # Add system timestamp if not present
        if "posted_at_utc" not in record:
            record["posted_at_utc"] = datetime.now(timezone.utc).isoformat()
        
        # Serialize to single line JSON
        json_line = json.dumps(record, ensure_ascii=False) + "\n"
        
        try:
            with open(self.storage_path, "a", encoding="utf-8") as f:
                # File locking for atomic writes (Unix only)
                if os.name != 'nt':
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.write(json_line)
                    f.flush()
                    os.fsync(f.fileno())  # Ensure write to disk
                finally:
                    if os.name != 'nt':
                        import fcntl
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                        
            logger.info(
                "Record appended to storage",
                extra={"match_id": record.get("match_id"), "post_type": record.get("post_type")}
            )
            
        except IOError as e:
            raise StorageError(f"Failed to write record: {e}")
    
    def read_all_records(self) -> List[Dict[str, Any]]:
        """
        Read all records from storage.
        
        Returns:
            List of all stored records as dictionaries
        """
        records = []
        
        if not self.storage_path.exists():
            return records
        
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        logger.warning(f"Skipping invalid JSON at line {line_num}: {e}")
                        
        except IOError as e:
            raise StorageError(f"Failed to read storage: {e}")
        
        return records
    
    def find_by_match_id(self, match_id: str) -> List[Dict[str, Any]]:
        """
        Find all records for a specific match.
        
        Args:
            match_id: Match identifier to search for
            
        Returns:
            List of records matching the match_id
        """
        records = self.read_all_records()
        return [r for r in records if r.get("match_id") == match_id]
    
    def find_prediction_by_match_id(self, match_id: str) -> Optional[Dict[str, Any]]:
        """
        Find the pre-match prediction for a specific match.
        
        Args:
            match_id: Match identifier to search for
            
        Returns:
            Pre-match prediction record or None if not found
        """
        records = self.find_by_match_id(match_id)
        predictions = [r for r in records if r.get("post_type") == "pre_match"]
        return predictions[0] if predictions else None
    
    def count_records(self, post_type: Optional[str] = None) -> int:
        """
        Count records in storage.
        
        Args:
            post_type: Optional filter by post type
            
        Returns:
            Number of records
        """
        records = self.read_all_records()
        if post_type:
            records = [r for r in records if r.get("post_type") == post_type]
        return len(records)
    
    def get_recent_records(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get most recent records.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of recent records (newest first)
        """
        records = self.read_all_records()
        # Sort by posted_at_utc descending
        records.sort(key=lambda r: r.get("posted_at_utc", ""), reverse=True)
        return records[:limit]
