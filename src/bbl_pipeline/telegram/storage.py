"""
Append-only storage for prediction records.

Implements JSON Lines (.jsonl) storage format for immutable
prediction records. Each record is a single JSON object on its own line.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import csv
import json
import logging
import os


logger = logging.getLogger(__name__)


TRACKER_HEADERS = [
    "date",
    "match",
    "pre_match_favorite",
    "final_result",
    "confidence",
    "what_changed",
]


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
    
    def __init__(
        self,
        storage_path: Union[str, Path],
        tracker_path: Optional[Union[str, Path]] = None,
    ):
        """
        Initialize prediction storage.
        
        Args:
            storage_path: Path to the JSON Lines storage file
        """
        self.storage_path = Path(storage_path)
        self.tracker_path = Path(tracker_path) if tracker_path else self.storage_path.with_name(
            "telegram_signal_accuracy_tracker.csv"
        )
        self._ensure_storage_exists()
        self._ensure_tracker_exists()
    
    def _ensure_storage_exists(self) -> None:
        """Ensure storage directory and file exist."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self.storage_path.touch()
            logger.info(f"Created storage file: {self.storage_path}")

    def _ensure_tracker_exists(self) -> None:
        """Ensure tracker directory and CSV file exist with a header row."""
        self.tracker_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.tracker_path.exists():
            with open(self.tracker_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=TRACKER_HEADERS)
                writer.writeheader()
            logger.info(f"Created tracker file: {self.tracker_path}")
    
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

    def read_tracker_rows(self) -> List[Dict[str, str]]:
        """Read all accuracy tracker rows."""
        rows: List[Dict[str, str]] = []
        if not self.tracker_path.exists():
            return rows

        try:
            with open(self.tracker_path, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append({header: row.get(header, "") for header in TRACKER_HEADERS})
        except IOError as e:
            raise StorageError(f"Failed to read tracker storage: {e}")

        return rows

    def find_tracker_row(self, match: str, date: Optional[str] = None) -> Optional[Dict[str, str]]:
        """Find a tracker row by match, optionally scoped to a date."""
        candidates = [
            row for row in self.read_tracker_rows()
            if row.get("match") == match and (date is None or row.get("date") == date)
        ]
        return candidates[-1] if candidates else None

    def upsert_tracker_row(self, row: Dict[str, Any]) -> None:
        """Insert or update a tracker row keyed by date and match."""
        normalized = {header: str(row.get(header, "") or "") for header in TRACKER_HEADERS}
        if not normalized["date"] or not normalized["match"]:
            raise StorageError("Tracker row requires both date and match")

        rows = self.read_tracker_rows()
        replaced = False
        for index, existing in enumerate(rows):
            if existing.get("date") == normalized["date"] and existing.get("match") == normalized["match"]:
                rows[index] = normalized
                replaced = True
                break
        if not replaced:
            rows.append(normalized)

        temp_path = self.tracker_path.with_suffix(f"{self.tracker_path.suffix}.tmp")
        try:
            with open(temp_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=TRACKER_HEADERS)
                writer.writeheader()
                writer.writerows(rows)
            os.replace(temp_path, self.tracker_path)
        except IOError as e:
            raise StorageError(f"Failed to write tracker storage: {e}")
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
